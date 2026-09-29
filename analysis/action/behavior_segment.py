"""把逐帧行为结果合并为时间段。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence


class BehaviorSegmentBuilder:
    """按 person_id 聚合行为观察, 输出行为时间段。"""

    def __init__(self, min_segment_seconds: float = 0.5) -> None:
        self.min_segment_seconds = max(0.0, float(min_segment_seconds))
        self._observations: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

    def add_observation(
        self,
        person_id: int,
        timestamp: float,
        action: str,
        confidence: float,
    ) -> None:
        self._observations[int(person_id)].append(
            {
                "timestamp": float(timestamp),
                "action": str(action),
                "confidence": float(confidence),
            }
        )

    def build_all(self) -> List[Dict[str, Any]]:
        """为所有人构建时间段。"""
        segments: List[Dict[str, Any]] = []
        for person_id, observations in sorted(self._observations.items()):
            if not observations:
                continue
            observations.sort(key=lambda item: item["timestamp"])
            person_segments = self._build_person_segments(person_id, observations)
            segments.extend(person_segments)
        return segments

    def _build_person_segments(
        self,
        person_id: int,
        observations: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """把单人的有序观察合并成时间段。"""
        merged: List[Dict[str, Any]] = []

        for observation in observations:
            if not merged:
                merged.append(self._new_segment(person_id, observation))
                continue

            current = merged[-1]
            if current["action"] == observation["action"]:
                current["end_time"] = observation["timestamp"]
                current["_confidences"].append(observation["confidence"])
            else:
                merged.append(self._new_segment(person_id, observation))

        merged = self._merge_short_segments(merged)
        merged = self._merge_nearby_same_action_segments(merged, max_gap_seconds=0.2)

        final_segments: List[Dict[str, Any]] = []
        for segment in merged:
            confidences = segment.pop("_confidences", [segment["confidence"]])
            average_confidence = sum(confidences) / len(confidences)
            final_segments.append(
                {
                    "person_id": int(person_id),
                    "action": segment["action"],
                    "start_time": round(segment["start_time"], 4),
                    "end_time": round(segment["end_time"], 4),
                    "confidence": round(float(average_confidence), 4),
                }
            )

        return final_segments

    @staticmethod
    def _new_segment(person_id: int, observation: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "person_id": int(person_id),
            "action": observation["action"],
            "start_time": observation["timestamp"],
            "end_time": observation["timestamp"],
            "confidence": observation["confidence"],
            "_confidences": [observation["confidence"]],
        }

    def _merge_short_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把过短的行为段合并到相邻段, 减少碎片。"""
        if len(segments) <= 1:
            return segments

        changed = True
        while changed:
            changed = False
            shortest_index = -1
            shortest_duration = self.min_segment_seconds

            for index, segment in enumerate(segments):
                duration = segment["end_time"] - segment["start_time"]
                if duration < shortest_duration:
                    shortest_duration = duration
                    shortest_index = index

            if shortest_index < 0:
                break

            target_index = self._merge_target(segments, shortest_index)
            if target_index is None:
                break

            self._merge_into(segments[target_index], segments[shortest_index])
            del segments[shortest_index]
            changed = True

        return segments

    @staticmethod
    def _merge_nearby_same_action_segments(
        segments: List[Dict[str, Any]],
        max_gap_seconds: float,
    ) -> List[Dict[str, Any]]:
        """合并同一人物、同一行为且间隔不超过阈值的相邻时间段。"""
        if len(segments) <= 1:
            return segments

        merged = [segments[0]]
        for segment in segments[1:]:
            previous = merged[-1]
            gap = segment["start_time"] - previous["end_time"]

            if (
                previous["person_id"] == segment["person_id"]
                and previous["action"] == segment["action"]
                and gap <= max_gap_seconds
            ):
                previous_confidence = sum(previous["_confidences"]) / len(previous["_confidences"])
                segment_confidence = sum(segment["_confidences"]) / len(segment["_confidences"])
                previous["end_time"] = segment["end_time"]
                previous["_confidences"] = [previous_confidence, segment_confidence]
            else:
                merged.append(segment)

        return merged

    def _merge_target(self, segments: List[Dict[str, Any]], index: int) -> int | None:
        """选择短段应合并到的相邻段。"""
        left = index - 1
        right = index + 1

        if left < 0 and right >= len(segments):
            return None
        if left < 0:
            return right
        if right >= len(segments):
            return left

        left_duration = segments[left]["end_time"] - segments[left]["start_time"]
        right_duration = segments[right]["end_time"] - segments[right]["start_time"]
        return left if left_duration >= right_duration else right

    @staticmethod
    def _merge_into(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        target["start_time"] = min(target["start_time"], source["start_time"])
        target["end_time"] = max(target["end_time"], source["end_time"])
        target["_confidences"].extend(source["_confidences"])
