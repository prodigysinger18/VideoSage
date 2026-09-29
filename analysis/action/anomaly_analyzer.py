"""基于姿态与轨迹时间序列的危险/异常行为分析。"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any, Deque, Dict

from analysis.pose.pose_features import PoseFeatures


class AnomalyAnalyzer:
    """逐人分析 fall、lying、running 等可解释事件。"""

    def __init__(
        self,
        window_seconds: float = 2.0,
        running_speed_threshold: float = 0.8,
        sudden_down_threshold: float = 0.25,
        lying_aspect_ratio: float = 1.15,
        lying_torso_angle: float = 55.0,
        stationary_seconds: float = 10.0,
        stationary_displacement: float = 0.08,
        abnormal_speed_threshold: float = 1.8,
        confirmation_frames: int = 3,
        abnormal_max_seconds: float = 2.0,
        movement_deadzone: float = 0.03,
        direction_confirmation_frames: int = 2,
        abnormal_path_ratio: float = 2.5,
        abnormal_min_path: float = 0.25,
        scene_cut_displacement: float = 0.8,
        scene_cut_size_change: float = 0.35,
        abnormal_cooldown_seconds: float = 1.0,
        fall_confirmation_frames: int = 4,
        fall_min_vertical_drop: float = 0.3,
        fall_min_vertical_speed: float = 0.18,
        fall_upright_torso_angle: float = 35.0,
        fall_cooldown_seconds: float = 2.5,
        fall_window_seconds: float = 0.8,
        fall_active_seconds: float = 0.6,
    ) -> None:
        self.window_seconds = max(0.5, float(window_seconds))
        self.running_speed_threshold = float(running_speed_threshold)
        self.sudden_down_threshold = float(sudden_down_threshold)
        self.lying_aspect_ratio = float(lying_aspect_ratio)
        self.lying_torso_angle = float(lying_torso_angle)
        self.stationary_seconds = float(stationary_seconds)
        self.stationary_displacement = float(stationary_displacement)
        self.abnormal_speed_threshold = float(abnormal_speed_threshold)
        self.confirmation_frames = max(2, int(confirmation_frames))
        self.abnormal_max_seconds = max(0.5, float(abnormal_max_seconds))
        self.movement_deadzone = max(0.0, float(movement_deadzone))
        self.direction_confirmation_frames = max(1, int(direction_confirmation_frames))
        self.abnormal_path_ratio = max(1.0, float(abnormal_path_ratio))
        self.abnormal_min_path = max(0.0, float(abnormal_min_path))
        self.scene_cut_displacement = max(0.0, float(scene_cut_displacement))
        self.scene_cut_size_change = max(0.0, float(scene_cut_size_change))
        self.abnormal_cooldown_seconds = max(0.0, float(abnormal_cooldown_seconds))
        self.fall_confirmation_frames = max(2, int(fall_confirmation_frames))
        self.fall_min_vertical_drop = max(0.0, float(fall_min_vertical_drop))
        self.fall_min_vertical_speed = max(0.0, float(fall_min_vertical_speed))
        self.fall_upright_torso_angle = max(0.0, float(fall_upright_torso_angle))
        self.fall_cooldown_seconds = max(0.0, float(fall_cooldown_seconds))
        self.fall_window_seconds = max(0.3, float(fall_window_seconds))
        self.fall_active_seconds = max(0.2, float(fall_active_seconds))
        history_seconds = max(self.window_seconds, self.stationary_seconds)
        self._histories: Dict[int, Deque[tuple[float, PoseFeatures]]] = defaultdict(deque)
        self._history_seconds = history_seconds
        self._condition_counts: Dict[int, Dict[str, int]] = defaultdict(dict)
        self._fall_active_until: Dict[int, float] = {}
        self._fall_cooldown_until: Dict[int, float] = {}
        self._fall_candidate_started: Dict[int, float] = {}
        self._fall_event_start_pending: Dict[int, float] = {}
        self._abnormal_started: Dict[int, float] = {}
        self._abnormal_cooldown_until: Dict[int, float] = {}

    def analyze(
        self,
        person_id: int,
        timestamp: float,
        features: PoseFeatures,
        base_action: str = "unknown",
    ) -> list[Dict[str, Any]]:
        history = self._histories[int(person_id)]
        if history and _is_scene_discontinuity(
            history[-1][1],
            features,
            self.scene_cut_displacement,
            self.scene_cut_size_change,
        ):
            history.clear()
            self._condition_counts.pop(int(person_id), None)
            self._abnormal_started.pop(int(person_id), None)
        history.append((float(timestamp), features))
        while history and timestamp - history[0][0] > self._history_seconds:
            history.popleft()

        recent = [(time, item) for time, item in history if timestamp - time <= self.window_seconds]
        speed, vertical_drop, displacement = _motion(recent)
        fall_recent = [
            (time, item)
            for time, item in recent
            if timestamp - time <= self.fall_window_seconds
        ]
        _, vertical_drop, _ = _motion(fall_recent)
        vertical_speed = _vertical_speed(fall_recent)
        aspect_ratio = features.bbox_width / max(features.bbox_height, 1e-6)
        torso_angle = features.torso_angle or 0.0
        pose_reliable = features.keypoint_visible_ratio >= 0.35 and features.keypoint_mean_confidence >= 0.28
        horizontal = aspect_ratio >= self.lying_aspect_ratio and torso_angle >= self.lying_torso_angle
        sudden_down = vertical_drop >= self.sudden_down_threshold
        had_upright_pose = _had_upright_pose(
            recent,
            self.fall_upright_torso_angle,
            min_duration=0.2,
        )
        fall_candidate = (
            pose_reliable
            and vertical_drop >= max(self.sudden_down_threshold, self.fall_min_vertical_drop)
            and vertical_speed >= self.fall_min_vertical_speed
            and (horizontal or torso_angle >= self.lying_torso_angle)
            and had_upright_pose
        )
        if fall_candidate:
            self._fall_candidate_started.setdefault(int(person_id), float(timestamp))
        else:
            self._fall_candidate_started.pop(int(person_id), None)
        fall_confirmed = self._confirmed(
            person_id,
            "fall",
            fall_candidate,
            self.fall_confirmation_frames,
        )
        fall_triggered = fall_confirmed and timestamp >= self._fall_cooldown_until.get(
            int(person_id), -1.0
        )
        if fall_triggered:
            self._fall_active_until[int(person_id)] = (
                float(timestamp) + self.fall_active_seconds
            )
            self._fall_event_start_pending[int(person_id)] = self._fall_candidate_started.pop(
                int(person_id), float(timestamp)
            )
            self._fall_cooldown_until[int(person_id)] = (
                float(timestamp) + self.fall_cooldown_seconds
            )

        fall_active = timestamp <= self._fall_active_until.get(int(person_id), -1.0)
        lying = self._confirmed(
            person_id,
            "lying",
            pose_reliable and horizontal,
            max(4, self.confirmation_frames),
        )
        running = self._confirmed(
            person_id,
            "running",
            pose_reliable and speed >= self.running_speed_threshold and not horizontal and not sudden_down,
            self.confirmation_frames,
        )
        long_stationary = _long_stationary(history, self.stationary_seconds, self.stationary_displacement)
        direction_changes, path_ratio, path_length = _erratic_motion(
            recent,
            self.movement_deadzone,
            self.direction_confirmation_frames,
        )
        abnormal_condition = (
            pose_reliable
            and not horizontal
            and base_action not in {"walking", "running"}
            and not sudden_down
            and direction_changes >= 2
            and path_ratio >= self.abnormal_path_ratio
            and path_length >= self.abnormal_min_path
            and timestamp >= self._abnormal_cooldown_until.get(int(person_id), -1.0)
        )
        abnormal = self._confirmed(person_id, "abnormal_movement", abnormal_condition, self.confirmation_frames)

        event = None
        confidence = 0.0
        if fall_active:
            event = "fall"
            confidence = min(0.98, 0.55 + vertical_drop + min(speed, 1.0) * 0.1)
        elif lying:
            event = "lying"
            confidence = min(0.95, 0.55 + max(aspect_ratio - 1.0, 0.0) * 0.4)
        elif running:
            event = "running"
            confidence = min(0.95, 0.55 + speed * 0.2)
        elif long_stationary:
            event = "long_stationary"
            confidence = 0.85
        elif abnormal and self._allow_abnormal(person_id, timestamp):
            event = "abnormal_movement"
            confidence = min(0.9, 0.55 + min(speed, self.abnormal_speed_threshold) * 0.1)
        elif not abnormal_condition or not abnormal:
            self._abnormal_started.pop(int(person_id), None)

        if event is None:
            return []
        event_timestamp = float(timestamp)
        if event == "fall":
            event_timestamp = self._fall_event_start_pending.pop(
                int(person_id), event_timestamp
            )
        return [{"person_id": int(person_id), "timestamp": event_timestamp, "event": event, "confidence": round(confidence, 4)}]

    def _confirmed(self, person_id: int, event: str, condition: bool, required: int) -> bool:
        counters = self._condition_counts[int(person_id)]
        counters[event] = counters.get(event, 0) + 1 if condition else 0
        return counters[event] >= required

    def _allow_abnormal(self, person_id: int, timestamp: float) -> bool:
        person_id = int(person_id)
        started = self._abnormal_started.setdefault(person_id, float(timestamp))
        if timestamp - started > self.abnormal_max_seconds:
            self._abnormal_started.pop(person_id, None)
            self._abnormal_cooldown_until[person_id] = float(timestamp) + self.abnormal_cooldown_seconds
            return False
        return True


def _motion(history: list[tuple[float, PoseFeatures]]) -> tuple[float, float, float]:
    if len(history) < 2:
        return 0.0, 0.0, 0.0
    first_time, first = history[0]
    last_time, last = history[-1]
    duration = max(last_time - first_time, 1e-6)
    scale = max((first.bbox_height + last.bbox_height) / 2.0, 1.0)
    dx = last.person_center[0] - first.person_center[0]
    dy = last.person_center[1] - first.person_center[1]
    displacement = math.hypot(dx, dy) / scale
    return displacement / duration, max(0.0, dy / scale), displacement


def _vertical_speed(history: list[tuple[float, PoseFeatures]]) -> float:
    """返回窗口内人物中心向下移动的归一化速度。"""
    if len(history) < 2:
        return 0.0
    first_time, first = history[0]
    last_time, last = history[-1]
    duration = max(last_time - first_time, 1e-6)
    scale = max((first.bbox_height + last.bbox_height) / 2.0, 1.0)
    downward_distance = max(0.0, last.person_center[1] - first.person_center[1])
    return (downward_distance / scale) / duration


def _had_upright_pose(
    history: list[tuple[float, PoseFeatures]],
    torso_angle_threshold: float,
    min_duration: float,
) -> bool:
    """确认当前倒地前的窗口里出现过可靠的直立姿态。"""
    if len(history) < 2:
        return False
    last_time = history[-1][0]
    for timestamp, features in history[:-1]:
        if last_time - timestamp < min_duration:
            continue
        torso_angle = features.torso_angle
        if (
            features.keypoint_visible_ratio >= 0.35
            and features.keypoint_mean_confidence >= 0.28
            and torso_angle is not None
            and torso_angle <= torso_angle_threshold
        ):
            return True
    return False


def _long_stationary(history: Deque[tuple[float, PoseFeatures]], seconds: float, threshold: float) -> bool:
    if len(history) < 2 or history[-1][0] - history[0][0] < seconds:
        return False
    _, _, displacement = _motion(list(history))
    return displacement <= threshold


def _erratic_motion(
    history: list[tuple[float, PoseFeatures]],
    deadzone: float,
    confirmation_frames: int,
) -> tuple[int, float, float]:
    if len(history) < 3:
        return 0, 0.0, 0.0

    normalized_steps = []
    path_length = 0.0
    for (_, previous), (_, current) in zip(history, history[1:]):
        scale = max((previous.bbox_height + current.bbox_height) / 2.0, 1.0)
        dx = (current.person_center[0] - previous.person_center[0]) / scale
        dy = (current.person_center[1] - previous.person_center[1]) / scale
        path_length += math.hypot(dx, dy)
        normalized_steps.append(1 if dx >= deadzone else -1 if dx <= -deadzone else 0)

    confirmed_directions = []
    current_sign = 0
    run_length = 0
    for sign in normalized_steps:
        if sign == 0:
            continue
        if sign == current_sign:
            run_length += 1
        else:
            current_sign = sign
            run_length = 1
        if run_length == confirmation_frames:
            confirmed_directions.append(sign)

    changes = sum(
        first != second
        for first, second in zip(confirmed_directions, confirmed_directions[1:])
    )
    first = history[0][1]
    last = history[-1][1]
    scale = max((first.bbox_height + last.bbox_height) / 2.0, 1.0)
    net_displacement = math.hypot(
        last.person_center[0] - first.person_center[0],
        last.person_center[1] - first.person_center[1],
    ) / scale
    path_ratio = path_length / max(net_displacement, 0.05)
    return changes, path_ratio, path_length


def _is_scene_discontinuity(
    previous: PoseFeatures,
    current: PoseFeatures,
    displacement_threshold: float,
    size_change_threshold: float,
) -> bool:
    scale = max((previous.bbox_height + current.bbox_height) / 2.0, 1.0)
    displacement = math.hypot(
        current.person_center[0] - previous.person_center[0],
        current.person_center[1] - previous.person_center[1],
    ) / scale
    size_change = abs(current.bbox_height - previous.bbox_height) / max(previous.bbox_height, 1.0)
    return (
        displacement >= displacement_threshold
        and size_change >= size_change_threshold
    ) or displacement >= displacement_threshold * 1.75


class AnomalySegmentBuilder:
    """把多标签异常观察转换为独立事件时间段。"""

    def __init__(
        self,
        max_gap_seconds: float = 0.3,
        min_duration_seconds: float = 0.3,
        related_event_gap_seconds: float = 1.0,
    ) -> None:
        self.max_gap_seconds = float(max_gap_seconds)
        self.min_duration_seconds = float(min_duration_seconds)
        self.related_event_gap_seconds = max(0.0, float(related_event_gap_seconds))
        self._segments: Dict[tuple[int, str], list[Dict[str, Any]]] = defaultdict(list)

    def add(self, observation: Dict[str, Any]) -> None:
        key = (int(observation["person_id"]), str(observation["event"]))
        timestamp = float(observation["timestamp"])
        confidence = float(observation["confidence"])
        segments = self._segments[key]
        if segments and timestamp - segments[-1]["end_time"] <= self.max_gap_seconds:
            segments[-1]["end_time"] = timestamp
            segments[-1]["_confidences"].append(confidence)
        else:
            segments.append({"person_id": key[0], "event": key[1], "start_time": timestamp, "end_time": timestamp, "_confidences": [confidence]})

    def build_all(self) -> list[Dict[str, Any]]:
        output = []
        for segments in self._segments.values():
            for segment in segments:
                duration = segment["end_time"] - segment["start_time"]
                if duration < self.min_duration_seconds:
                    continue
                output.append(
                    {
                        "person_id": segment["person_id"],
                        "event": segment["event"],
                        "start_time": round(segment["start_time"], 4),
                        "end_time": round(segment["end_time"], 4),
                        "confidence": round(sum(segment["_confidences"]) / len(segment["_confidences"]), 4),
                    }
                )
        output = sorted(output, key=lambda item: (item["person_id"], item["start_time"], item["end_time"]))
        output = self._merge_related_events(output)
        for segment in output:
            segment["severity"] = _event_severity(segment["event"])
        return sorted(output, key=lambda item: (item["start_time"], item["person_id"], item["event"]))

    def _merge_related_events(self, segments: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """把 sudden_down -> fall -> lying 归并为单个 fall 事件。"""
        if len(segments) <= 1:
            return segments

        merged: list[Dict[str, Any]] = []
        for segment in segments:
            current = dict(segment)
            if not merged:
                merged.append(current)
                continue

            previous = merged[-1]
            gap = float(current["start_time"]) - float(previous["end_time"])
            if (
                previous["person_id"] == current["person_id"]
                and gap <= self.related_event_gap_seconds
                and _is_fall_sequence(previous["event"], current["event"])
            ):
                previous["event"] = "fall"
                previous["end_time"] = max(previous["end_time"], current["end_time"])
                previous["confidence"] = round(
                    (float(previous["confidence"]) + float(current["confidence"])) / 2.0,
                    4,
                )
            else:
                merged.append(current)
        return merged


def _is_fall_sequence(previous_event: str, current_event: str) -> bool:
    return (previous_event, current_event) in {
        ("sudden_down", "fall"),
        ("sudden_down", "lying"),
        ("fall", "lying"),
    }


def _event_severity(event: str) -> str:
    if event == "fall":
        return "high"
    if event in {"abnormal_movement", "sudden_down"}:
        return "warning"
    return "normal"
