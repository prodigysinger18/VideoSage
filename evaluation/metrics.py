"""跟踪结果的客观统计指标。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def tracking_statistics(records: Iterable[dict[str, Any]], fps: float | None = None) -> dict[str, Any]:
    rows = [row for row in records if _valid_record(row)]
    by_person: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_person[int(row["person_id"])].append(row)
        by_track[int(row["track_id"])].append(row)

    profiles = []
    for person_id, person_rows in sorted(by_person.items()):
        person_rows.sort(key=lambda row: (float(row["timestamp"]), int(row["frame_id"])))
        track_ids = _unique_in_order(row["track_id"] for row in person_rows)
        confidence = [float(row.get("identity_confidence", 0.0)) for row in person_rows]
        timestamps = [float(row["timestamp"]) for row in person_rows]
        profiles.append({
            "person_id": person_id,
            "record_count": len(person_rows),
            "track_ids": track_ids,
            "track_fragment_count": max(0, len(track_ids) - 1),
            "first_seen": round(min(timestamps), 4),
            "last_seen": round(max(timestamps), 4),
            "duration_seconds": round(max(timestamps) - min(timestamps), 4),
            "average_identity_confidence": round(sum(confidence) / len(confidence), 4),
        })

    track_durations = []
    for track_id, track_rows in by_track.items():
        timestamps = [float(row["timestamp"]) for row in track_rows]
        track_durations.append({
            "track_id": track_id,
            "first_seen": round(min(timestamps), 4),
            "last_seen": round(max(timestamps), 4),
            "duration_seconds": round(max(timestamps) - min(timestamps), 4),
            "record_count": len(track_rows),
        })

    switches = sum(profile["track_fragment_count"] for profile in profiles)
    return {
        "record_count": len(rows),
        "unique_person_ids": len(by_person),
        "raw_track_count": len(by_track),
        "track_fragmentation_count": switches,
        "average_track_duration_seconds": _average(item["duration_seconds"] for item in track_durations),
        "average_person_identity_confidence": _average(
            item["average_identity_confidence"] for item in profiles
        ),
        "fps": fps,
        "persons": profiles,
        "tracks": sorted(track_durations, key=lambda item: item["track_id"]),
        "ground_truth_metrics": None,
        "ground_truth_note": "未提供人工标注，未计算 MOTA、IDF1 或真实 ID Switch。",
    }


def _valid_record(row: dict[str, Any]) -> bool:
    required = ("person_id", "track_id", "timestamp", "frame_id")
    return all(key in row and row[key] is not None for key in required)


def _unique_in_order(values: Iterable[Any]) -> list[int]:
    seen: set[int] = set()
    result = []
    for value in values:
        number = int(value)
        if number not in seen:
            seen.add(number)
            result.append(number)
    return result


def _average(values: Iterable[float]) -> float:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else 0.0
