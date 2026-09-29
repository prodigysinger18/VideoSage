"""把行为或异常查询结果转换为播放器片段。"""

from __future__ import annotations

from typing import Any


class ClipTool:
    def __init__(self, padding_before: float = 2.0, padding_after: float = 2.0) -> None:
        self.padding_before = max(0.0, float(padding_before))
        self.padding_after = max(0.0, float(padding_after))

    def build(
        self,
        video_id: int,
        records: Any,
        reason: str | None,
        video_duration: float | None = None,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        if not isinstance(records, list):
            return []
        clips = []
        for record in records:
            if "start_time" not in record or "end_time" not in record:
                continue
            if float(record.get("confidence") or 0.0) < float(min_confidence):
                continue
            start = max(0.0, float(record["start_time"]) - self.padding_before)
            end = max(start, float(record["end_time"]) + self.padding_after)
            if video_duration is not None:
                end = min(end, max(0.0, float(video_duration)))
            clips.append({
                "video_id": int(video_id),
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "event_time": round(float(record["start_time"]), 3),
                "reason": reason or record.get("action") or record.get("event") or "result",
                "person_id": record.get("person_id"),
                "confidence": record.get("confidence"),
            })
        clips.sort(key=lambda item: (item["start_time"], item["end_time"]))
        merged = []
        for clip in clips:
            if (
                merged
                and merged[-1]["video_id"] == clip["video_id"]
                and merged[-1].get("person_id") == clip.get("person_id")
                and merged[-1]["reason"] == clip["reason"]
                and clip["start_time"] <= merged[-1]["end_time"] + 0.5
            ):
                previous = merged[-1]
                previous["end_time"] = max(previous["end_time"], clip["end_time"])
                confidences = [value for value in (previous.get("confidence"), clip.get("confidence")) if value is not None]
                previous["confidence"] = round(sum(confidences) / len(confidences), 4) if confidences else None
            else:
                merged.append(clip)
        return merged[:20]
