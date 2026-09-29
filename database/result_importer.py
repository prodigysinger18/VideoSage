"""将 VideoSage JSON 分析结果导入 SQL Server。"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

from database.sqlserver_manager import SQLServerManager


class ResultImporter:
    """按视频和逻辑 person_id 导入人物、行为、穿搭与异常事件。"""

    def __init__(self, manager: SQLServerManager, result_dir: str) -> None:
        self.manager = manager
        self.result_dir = os.path.abspath(result_dir)

    def import_results(self) -> Dict[str, int]:
        video_info = _load_dict(os.path.join(self.result_dir, "video_info.json"))
        profiles = _load_list(
            os.path.join(self.result_dir, "person_profiles", "person_profiles.json")
        )
        behaviors = _load_list(
            os.path.join(self.result_dir, "behaviors", "behavior_segments.json")
        )
        anomalies = _load_list(
            os.path.join(self.result_dir, "behaviors", "anomaly_segments.json")
        )
        outfits = _load_list(
            os.path.join(self.result_dir, "appearance", "outfit_profiles.json")
        )
        if not behaviors:
            behaviors = _profile_segments(profiles, "behavior")
        if not anomalies:
            anomalies = _profile_segments(profiles, "danger_events")
        if not outfits:
            outfits = _profile_appearances(profiles)

        self.manager.create_tables()
        video_id = self._upsert_video(video_info)
        person_sources = _collect_person_sources(profiles, behaviors, anomalies, outfits)
        person_rows = {}
        for logical_person_id, source in sorted(person_sources.items()):
            person_rows[logical_person_id] = self._upsert_person(
                video_id,
                logical_person_id,
                source,
            )

        behavior_count = 0
        for segment in behaviors:
            logical_person_id = _as_int(segment.get("person_id"))
            if logical_person_id in person_rows and self._insert_behavior(
                person_rows[logical_person_id], segment
            ):
                behavior_count += 1

        anomaly_count = 0
        for segment in anomalies:
            logical_person_id = _as_int(segment.get("person_id"))
            if logical_person_id in person_rows and self._insert_anomaly(
                person_rows[logical_person_id], segment
            ):
                anomaly_count += 1

        self.manager.connection.commit()
        return {
            "video_id": video_id,
            "persons": len(person_rows),
            "behaviors_inserted": behavior_count,
            "anomalies_inserted": anomaly_count,
        }

    def _upsert_video(self, video_info: Dict[str, Any]) -> int:
        video_path = str(video_info.get("path") or self.result_dir)
        cursor = self.manager.execute(
            "SELECT video_id FROM dbo.videos WHERE video_path = ?",
            (video_path,),
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return int(row[0])

        cursor = self.manager.execute(
            """
            INSERT INTO dbo.videos
                (video_name, video_path, fps, width, height, duration)
            OUTPUT INSERTED.video_id
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                os.path.basename(video_path),
                video_path,
                _as_float(video_info.get("fps")),
                _as_int(video_info.get("width")),
                _as_int(video_info.get("height")),
                _as_float(video_info.get("duration_sec")),
            ),
        )
        video_id = int(cursor.fetchone()[0])
        cursor.close()
        return video_id

    def _upsert_person(
        self,
        video_id: int,
        logical_person_id: int,
        source: Dict[str, Any],
    ) -> int:
        first_seen, last_seen = _time_range(source)
        appearance = source.get("appearance") or {}
        appearance_json = json.dumps(appearance, ensure_ascii=False) if appearance else None
        cursor = self.manager.execute(
            "SELECT id FROM dbo.persons WHERE video_id = ? AND person_id = ?",
            (video_id, logical_person_id),
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            database_person_id = int(row[0])
            cursor = self.manager.execute(
                """
                UPDATE dbo.persons
                SET first_seen = COALESCE(?, first_seen),
                    last_seen = COALESCE(?, last_seen),
                    appearance_json = COALESCE(?, appearance_json)
                WHERE id = ?
                """,
                (first_seen, last_seen, appearance_json, database_person_id),
            )
            cursor.close()
            return database_person_id

        cursor = self.manager.execute(
            """
            INSERT INTO dbo.persons
                (video_id, person_id, first_seen, last_seen, appearance_json)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?)
            """,
            (video_id, logical_person_id, first_seen, last_seen, appearance_json),
        )
        database_person_id = int(cursor.fetchone()[0])
        cursor.close()
        return database_person_id

    def _insert_behavior(self, database_person_id: int, segment: Dict[str, Any]) -> bool:
        action = segment.get("action")
        start_time = _as_float(segment.get("start_time"))
        end_time = _as_float(segment.get("end_time"))
        if not action or start_time is None or end_time is None:
            return False
        if self._segment_exists("behaviors", database_person_id, "action", action, start_time, end_time):
            return False
        cursor = self.manager.execute(
            "INSERT INTO dbo.behaviors (person_id, action, start_time, end_time, confidence) VALUES (?, ?, ?, ?, ?)",
            (database_person_id, str(action), start_time, end_time, _as_float(segment.get("confidence"))),
        )
        cursor.close()
        return True

    def _insert_anomaly(self, database_person_id: int, segment: Dict[str, Any]) -> bool:
        event = segment.get("event")
        start_time = _as_float(segment.get("start_time"))
        end_time = _as_float(segment.get("end_time"))
        if not event or start_time is None or end_time is None:
            return False
        if self._segment_exists("anomalies", database_person_id, "event", event, start_time, end_time):
            return False
        cursor = self.manager.execute(
            """
            INSERT INTO dbo.anomalies
                (person_id, event, severity, start_time, end_time, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                database_person_id,
                str(event),
                str(segment.get("severity") or _severity(str(event))),
                start_time,
                end_time,
                _as_float(segment.get("confidence")),
            ),
        )
        cursor.close()
        return True

    def _segment_exists(
        self,
        table: str,
        person_id: int,
        label_column: str,
        label: str,
        start_time: float,
        end_time: float,
    ) -> bool:
        if table not in {"behaviors", "anomalies"} or label_column not in {"action", "event"}:
            raise ValueError("不允许的数据库表或字段")
        cursor = self.manager.execute(
            f"SELECT 1 FROM dbo.{table} WHERE person_id = ? AND {label_column} = ? AND start_time = ? AND end_time = ?",
            (person_id, str(label), start_time, end_time),
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists


def _collect_person_sources(*collections: list[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    sources: Dict[int, Dict[str, Any]] = {}
    for collection in collections:
        for record in collection:
            person_id = _as_int(record.get("person_id"))
            if person_id is None:
                continue
            source = sources.setdefault(
                person_id,
                {"appearance": {}, "times": []},
            )
            if record.get("appearance"):
                source["appearance"] = record["appearance"]
            elif record.get("upper") or record.get("lower"):
                source["appearance"] = {
                    key: record[key]
                    for key in ("upper", "lower", "confidence", "sample_count")
                    if key in record
                }
            for key in ("start_time", "end_time", "timestamp"):
                value = _as_float(record.get(key))
                if value is not None:
                    source["times"].append(value)
    return sources


def _profile_segments(
    profiles: list[Dict[str, Any]],
    field: str,
) -> list[Dict[str, Any]]:
    segments = []
    for profile in profiles:
        person_id = _as_int(profile.get("person_id"))
        values = profile.get(field)
        if person_id is None or not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                segments.append({"person_id": person_id, **value})
    return segments


def _profile_appearances(profiles: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    appearances = []
    for profile in profiles:
        person_id = _as_int(profile.get("person_id"))
        appearance = profile.get("appearance")
        if person_id is not None and isinstance(appearance, dict) and appearance:
            appearances.append({"person_id": person_id, **appearance})
    return appearances


def _time_range(source: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    times = source.get("times") or []
    return (min(times), max(times)) if times else (None, None)


def _load_list(path: str) -> list[Dict[str, Any]]:
    data = _load_json(path, [])
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _load_dict(path: str) -> Dict[str, Any]:
    data = _load_json(path, {})
    return data if isinstance(data, dict) else {}


def _load_json(path: str, default: Any) -> Any:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _severity(event: str) -> str:
    if event == "fall":
        return "high"
    if event in {"abnormal_movement", "sudden_down"}:
        return "warning"
    return "normal"


def import_result_root(
    manager: SQLServerManager,
    results_root: str,
) -> Dict[str, Any]:
    """批量导入 results_root 下所有包含 video_info.json 的视频结果目录。"""
    absolute_root = os.path.abspath(results_root)
    if not os.path.isdir(absolute_root):
        raise NotADirectoryError(f"结果根目录不存在: {absolute_root}")

    result_dirs = [
        os.path.join(absolute_root, name)
        for name in sorted(os.listdir(absolute_root))
        if os.path.isdir(os.path.join(absolute_root, name))
        and os.path.isfile(os.path.join(absolute_root, name, "video_info.json"))
    ]

    items = []
    for result_dir in result_dirs:
        try:
            summary = ResultImporter(manager, result_dir).import_results()
            items.append(
                {
                    "result_dir": result_dir,
                    "status": "success",
                    **summary,
                }
            )
        except Exception as exc:
            if manager.connection is not None:
                manager.connection.rollback()
            items.append(
                {
                    "result_dir": result_dir,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    return {
        "results_root": absolute_root,
        "total_directories": len(result_dirs),
        "successful_imports": sum(item["status"] == "success" for item in items),
        "failed_imports": sum(item["status"] == "failed" for item in items),
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 VideoSage 分析结果到 SQL Server")
    parser.add_argument("--config", default="config.yaml")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--result-dir")
    source_group.add_argument("--results-root")
    args = parser.parse_args()

    from utils.config_loader import get_section, load_config

    config = load_config(args.config)
    database_config = get_section(config, "database")
    with SQLServerManager(database_config) as manager:
        if args.results_root:
            summary = import_result_root(manager, args.results_root)
        else:
            summary = ResultImporter(manager, args.result_dir).import_results()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary.get("failed_imports", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
