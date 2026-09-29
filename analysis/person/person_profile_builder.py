"""将 Pose、行为、穿搭和异常事件聚合为人物档案。"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from typing import Any, Dict, Iterable, Optional


DEFAULT_POSES_FILE = "data/results/poses/person_poses.json"
DEFAULT_BEHAVIORS_FILE = "data/results/behaviors/behavior_segments.json"
DEFAULT_OUTFITS_FILE = "data/results/appearance/outfit_profiles.json"
DEFAULT_ANOMALIES_FILE = "data/results/behaviors/anomaly_segments.json"
DEFAULT_OUTPUT_FILE = "data/results/person_profiles/person_profiles.json"


def build_person_profiles(
    poses_file: str = DEFAULT_POSES_FILE,
    behaviors_file: str = DEFAULT_BEHAVIORS_FILE,
    outfits_file: str = DEFAULT_OUTFITS_FILE,
    anomalies_file: str = DEFAULT_ANOMALIES_FILE,
    output_file: Optional[str] = DEFAULT_OUTPUT_FILE,
) -> list[Dict[str, Any]]:
    """读取已有 JSON，并按照 person_id 构建统一人物档案。"""
    poses = _load_list(poses_file)
    behaviors = _load_list(behaviors_file)
    outfits = _load_list(outfits_file)
    anomalies = _load_list(anomalies_file)

    person_ids = _collect_person_ids(poses, behaviors, outfits, anomalies)
    track_ids: Dict[int, set[int]] = defaultdict(set)
    behavior_by_person: Dict[int, list[Dict[str, Any]]] = defaultdict(list)
    appearance_by_person: Dict[int, Dict[str, Any]] = {}
    danger_by_person: Dict[int, list[Dict[str, Any]]] = defaultdict(list)

    for record in poses:
        person_id = _person_id(record)
        track_id = record.get("track_id")
        if person_id is not None and track_id is not None:
            track_ids[person_id].add(int(track_id))

    for segment in behaviors:
        person_id = _person_id(segment)
        if person_id is not None:
            behavior_by_person[person_id].append(_behavior_record(segment))

    for profile in outfits:
        person_id = _person_id(profile)
        if person_id is not None:
            appearance_by_person[person_id] = _appearance_record(profile)

    for segment in anomalies:
        person_id = _person_id(segment)
        if person_id is not None:
            danger_by_person[person_id].append(_danger_record(segment))

    profiles = []
    for person_id in sorted(person_ids):
        profiles.append(
            {
                "person_id": person_id,
                "identity": {
                    "track_ids": sorted(track_ids.get(person_id, set())),
                },
                "behavior": sorted(
                    behavior_by_person.get(person_id, []),
                    key=lambda item: (item["start_time"], item["end_time"]),
                ),
                "appearance": appearance_by_person.get(person_id, {}),
                "danger_events": sorted(
                    danger_by_person.get(person_id, []),
                    key=lambda item: (item["start_time"], item["end_time"]),
                ),
            }
        )

    if output_file:
        _save_json(output_file, profiles)
    return profiles


def _load_list(path: str) -> list[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"JSON 顶层必须为数组: {path}")
    return [item for item in data if isinstance(item, dict)]


def _collect_person_ids(*collections: Iterable[Dict[str, Any]]) -> set[int]:
    person_ids = set()
    for collection in collections:
        for record in collection:
            person_id = _person_id(record)
            if person_id is not None:
                person_ids.add(person_id)
    return person_ids


def _person_id(record: Dict[str, Any]) -> Optional[int]:
    value = record.get("person_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _behavior_record(segment: Dict[str, Any]) -> Dict[str, Any]:
    return _select_fields(
        segment,
        ("action", "start_time", "end_time", "confidence"),
    )


def _appearance_record(profile: Dict[str, Any]) -> Dict[str, Any]:
    return _select_fields(
        profile,
        ("upper", "lower", "confidence", "sample_count"),
    )


def _danger_record(segment: Dict[str, Any]) -> Dict[str, Any]:
    record = _select_fields(
        segment,
        ("event", "severity", "start_time", "end_time", "confidence"),
    )
    record.setdefault("severity", _severity(str(record.get("event", ""))))
    return record


def _select_fields(source: Dict[str, Any], fields: tuple[str, ...]) -> Dict[str, Any]:
    return {field: source[field] for field in fields if field in source}


def _severity(event: str) -> str:
    if event == "fall":
        return "high"
    if event in {"abnormal_movement", "sudden_down"}:
        return "warning"
    return "normal"


def _save_json(path: str, data: Any) -> None:
    absolute_path = os.path.abspath(path)
    parent = os.path.dirname(absolute_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(absolute_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 VideoSage 人物档案")
    parser.add_argument("--poses", default=DEFAULT_POSES_FILE)
    parser.add_argument("--behaviors", default=DEFAULT_BEHAVIORS_FILE)
    parser.add_argument("--outfits", default=DEFAULT_OUTFITS_FILE)
    parser.add_argument("--anomalies", default=DEFAULT_ANOMALIES_FILE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args()

    profiles = build_person_profiles(
        poses_file=args.poses,
        behaviors_file=args.behaviors,
        outfits_file=args.outfits,
        anomalies_file=args.anomalies,
        output_file=args.output,
    )
    print(f"人物档案已保存: {os.path.abspath(args.output)} ({len(profiles)} 人)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
