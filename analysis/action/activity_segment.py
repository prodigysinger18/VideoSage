"""融合基础行为与异常事件时间段。"""

from __future__ import annotations

from typing import Any, Dict, Sequence


def merge_activity_segments(
    behavior_segments: Sequence[Dict[str, Any]],
    anomaly_segments: Sequence[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """使用异常事件替换同一人物重叠的 unknown 基础行为段。"""
    anomalies_by_person: Dict[int, list[Dict[str, Any]]] = {}
    for segment in anomaly_segments:
        anomalies_by_person.setdefault(int(segment["person_id"]), []).append(segment)

    output: list[Dict[str, Any]] = []
    for behavior in behavior_segments:
        if behavior["action"] != "unknown":
            output.append(dict(behavior))
            continue

        replacements = _overlapping_anomalies(
            behavior,
            anomalies_by_person.get(int(behavior["person_id"]), []),
        )
        if not replacements:
            output.append(dict(behavior))
            continue
        output.extend(_replace_unknown_segment(behavior, replacements))

    return _merge_adjacent(sorted(output, key=_sort_key))


def _overlapping_anomalies(
    behavior: Dict[str, Any],
    anomalies: Sequence[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    return [
        segment
        for segment in anomalies
        if float(segment["end_time"]) >= float(behavior["start_time"])
        and float(segment["start_time"]) <= float(behavior["end_time"])
    ]


def _replace_unknown_segment(
    behavior: Dict[str, Any],
    anomalies: Sequence[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    start = float(behavior["start_time"])
    end = float(behavior["end_time"])
    cursor = start
    result = []

    for anomaly in sorted(anomalies, key=lambda item: float(item["start_time"])):
        anomaly_start = max(start, float(anomaly["start_time"]))
        anomaly_end = min(end, float(anomaly["end_time"]))
        if anomaly_end < anomaly_start:
            continue
        if anomaly_start > cursor:
            result.append(_slice(behavior, "unknown", cursor, anomaly_start, behavior["confidence"]))
        result.append(
            _slice(
                behavior,
                str(anomaly["event"]),
                anomaly_start,
                anomaly_end,
                anomaly["confidence"],
            )
        )
        cursor = max(cursor, anomaly_end)

    if cursor < end:
        result.append(_slice(behavior, "unknown", cursor, end, behavior["confidence"]))
    return result


def _slice(
    source: Dict[str, Any],
    action: str,
    start_time: float,
    end_time: float,
    confidence: float,
) -> Dict[str, Any]:
    return {
        "person_id": int(source["person_id"]),
        "action": action,
        "start_time": round(float(start_time), 4),
        "end_time": round(float(end_time), 4),
        "confidence": round(float(confidence), 4),
    }


def _merge_adjacent(segments: Sequence[Dict[str, Any]]) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    for segment in segments:
        if not merged:
            merged.append(dict(segment))
            continue
        previous = merged[-1]
        if (
            previous["person_id"] == segment["person_id"]
            and previous["action"] == segment["action"]
            and float(segment["start_time"]) - float(previous["end_time"]) <= 0.2
        ):
            previous["end_time"] = segment["end_time"]
            previous["confidence"] = round(
                (float(previous["confidence"]) + float(segment["confidence"])) / 2.0,
                4,
            )
        else:
            merged.append(dict(segment))
    return merged


def _sort_key(segment: Dict[str, Any]) -> tuple[int, float, float]:
    return (
        int(segment["person_id"]),
        float(segment["start_time"]),
        float(segment["end_time"]),
    )
