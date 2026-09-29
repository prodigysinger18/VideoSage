"""基础行为分析。

第一阶段只实现 standing / walking / sitting。
Walking 必须结合连续多帧的人物中心位移与脚踝运动, 避免单帧抖动误判。
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Sequence

from analysis.pose.pose_features import PoseFeatures


class ActionAnalyzer:
    """基于姿态特征和时间序列的规则行为分析器。"""

    def __init__(
        self,
        walking_window_size: int = 10,
        standing_knee_angle_thresh: float = 140.0,
        standing_torso_angle_thresh: float = 20.0,
        standing_max_center_displacement: float = 0.08,
        standing_max_ankle_motion: float = 0.06,
        sitting_knee_angle_thresh: float = 110.0,
        walking_min_center_displacement: float = 0.25,
        walking_min_ankle_motion: float = 0.12,
        min_keypoint_visible_ratio: float = 0.35,
        min_keypoint_confidence: float = 0.28,
    ) -> None:
        self.walking_window_size = max(3, int(walking_window_size))
        self.standing_knee_angle_thresh = float(standing_knee_angle_thresh)
        self.standing_torso_angle_thresh = float(standing_torso_angle_thresh)
        self.standing_max_center_displacement = float(standing_max_center_displacement)
        self.standing_max_ankle_motion = float(standing_max_ankle_motion)
        self.sitting_knee_angle_thresh = float(sitting_knee_angle_thresh)
        self.walking_min_center_displacement = float(walking_min_center_displacement)
        self.walking_min_ankle_motion = float(walking_min_ankle_motion)
        self.min_keypoint_visible_ratio = float(min_keypoint_visible_ratio)
        self.min_keypoint_confidence = float(min_keypoint_confidence)

        self._histories: Dict[int, Deque[PoseFeatures]] = defaultdict(
            lambda: deque(maxlen=self.walking_window_size)
        )
        self._timestamps: Dict[int, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.walking_window_size)
        )

    def analyze(
        self,
        person_id: int,
        timestamp: float,
        features: PoseFeatures,
    ) -> Dict[str, Any]:
        """对单帧姿态特征进行行为判断。"""
        history = self._histories[int(person_id)]
        history.append(features)
        timestamps = self._timestamps[int(person_id)]
        timestamps.append(float(timestamp))

        if not self._quality_is_sufficient(features):
            action = "unknown"
            confidence = min(0.45, max(0.0, features.keypoint_mean_confidence))
        elif self._looks_sitting(history):
            action = "sitting"
            confidence = self._sitting_confidence(features)
        elif self._looks_walking(history, timestamps):
            action = "walking"
            center_disp, ankle_motion, center_speed, _ = self._movement(history, timestamps)
            confidence = self._walking_confidence(center_disp, ankle_motion, center_speed)
        elif self._looks_standing(history, timestamps):
            action = "standing"
            center_disp, ankle_motion, _, _ = self._movement(history, timestamps)
            confidence = self._standing_confidence(features, center_disp, ankle_motion)
        else:
            action = "unknown"
            confidence = min(0.5, features.keypoint_mean_confidence)

        return {
            "person_id": int(person_id),
            "timestamp": float(timestamp),
            "action": action,
            "confidence": round(float(confidence), 4),
        }

    def _quality_is_sufficient(self, features: PoseFeatures) -> bool:
        return features.keypoint_visible_ratio >= self.min_keypoint_visible_ratio and features.keypoint_mean_confidence >= self.min_keypoint_confidence

    def _looks_sitting(self, history: Sequence[PoseFeatures]) -> bool:
        """坐姿判断: 主要看膝盖弯曲和髋部在 bbox 中偏低。"""
        features = history[-1]
        recent = list(history)[-min(5, len(history)):]
        knee_angles = [
            angle
            for angle in (features.left_knee_angle, features.right_knee_angle)
            if angle is not None
        ]
        if len(knee_angles) >= 2:
            confirmations = sum(
                1 for item in recent
                if item.left_knee_angle is not None
                and item.right_knee_angle is not None
                and max(item.left_knee_angle, item.right_knee_angle) < self.sitting_knee_angle_thresh
            )
            hip_y = features.hip_center_norm[1] if features.hip_center_norm else None
            aspect_ratio = features.bbox_width / max(features.bbox_height, 1e-6)
            torso_supported = features.torso_angle is None or features.torso_angle < 55.0
            posture_supported = (hip_y is not None and hip_y > 0.5) or aspect_ratio > 0.55
            return (
                max(knee_angles) < self.sitting_knee_angle_thresh
                and confirmations >= max(2, len(recent) // 2)
                and posture_supported
                and torso_supported
            )

        hip_y = features.hip_center_norm[1] if features.hip_center_norm else None
        return hip_y is not None and hip_y > 0.58 and len(recent) >= 3

    def _looks_walking(
        self,
        history: Sequence[PoseFeatures],
        timestamps: Sequence[float],
    ) -> bool:
        """行走判断: 必须基于时间窗口。"""
        if len(history) < self.walking_window_size:
            return False

        center_disp, ankle_motion, center_speed, height_change = self._movement(history, timestamps)
        return (
            center_disp >= self.walking_min_center_displacement
            and ankle_motion >= self.walking_min_ankle_motion
            and center_speed >= self.walking_min_center_displacement
            and height_change <= 0.3
        )

    def _looks_standing(self, history: Sequence[PoseFeatures], timestamps: Sequence[float]) -> bool:
        features = history[-1]
        center_disp, ankle_motion, _, height_change = self._movement(history, timestamps)
        knee_angles = [angle for angle in (features.left_knee_angle, features.right_knee_angle) if angle is not None]
        knees_straight = bool(knee_angles) and min(knee_angles) >= self.standing_knee_angle_thresh
        torso_vertical = features.torso_angle is not None and features.torso_angle <= self.standing_torso_angle_thresh
        return (
            knees_straight
            and torso_vertical
            and center_disp <= self.standing_max_center_displacement
            and ankle_motion <= self.standing_max_ankle_motion
            and height_change <= 0.15
        )

    def _movement(self, history: Sequence[PoseFeatures], timestamps: Sequence[float]) -> tuple[float, float, float, float]:
        """计算窗口内的人物中心位移和平均脚踝运动, 用 bbox 高度归一化。"""
        if not history:
            return 0.0, 0.0, 0.0, 0.0

        history_list = list(history)
        heights = [features.bbox_height for features in history_list]
        average_height = sum(heights) / len(heights)
        if average_height <= 1e-6:
            return 0.0, 0.0, 0.0, 0.0

        centers = [features.person_center for features in history_list]
        first_center = centers[0]
        last_center = centers[-1]
        center_disp = math.hypot(
            last_center[0] - first_center[0],
            last_center[1] - first_center[1],
        ) / average_height

        ankle_motion_sum = 0.0
        pair_count = 0
        for previous, current in zip(history_list, history_list[1:]):
            left_delta = _point_delta(previous.left_ankle, current.left_ankle)
            right_delta = _point_delta(previous.right_ankle, current.right_ankle)
            if left_delta is not None:
                ankle_motion_sum += left_delta
                pair_count += 1
            if right_delta is not None:
                ankle_motion_sum += right_delta
                pair_count += 1

        ankle_motion = (ankle_motion_sum / max(1, pair_count)) / average_height
        timestamp_list = list(timestamps)
        duration = max(timestamp_list[-1] - timestamp_list[0], 1e-6) if len(timestamp_list) >= 2 else 0.0
        center_speed = center_disp / duration if duration > 0 else 0.0
        height_change = (max(heights) - min(heights)) / average_height
        return center_disp, ankle_motion, center_speed, height_change

    def _sitting_confidence(self, features: PoseFeatures) -> float:
        angles = [
            angle
            for angle in (features.left_knee_angle, features.right_knee_angle)
            if angle is not None
        ]
        angle_confidence = 0.65
        if angles:
            distance = max(0.0, self.sitting_knee_angle_thresh - min(angles))
            angle_confidence = min(0.95, 0.65 + distance * 0.03)
        return angle_confidence * max(0.5, features.keypoint_mean_confidence)

    def _walking_confidence(self, center_disp: float, ankle_motion: float, center_speed: float) -> float:
        center_ratio = min(
            1.0,
            center_disp / max(self.walking_min_center_displacement * 2.0, 1e-6),
        )
        ankle_ratio = min(
            1.0,
            ankle_motion / max(self.walking_min_ankle_motion * 2.0, 1e-6),
        )
        speed_ratio = min(1.0, center_speed / max(self.walking_min_center_displacement * 2.0, 1e-6))
        return min(0.95, 0.5 + 0.4 * (center_ratio + ankle_ratio + speed_ratio) / 3.0)

    def _standing_confidence(
        self,
        features: PoseFeatures,
        center_disp: float,
        ankle_motion: float,
    ) -> float:
        confidence = 0.65

        if features.torso_angle is not None:
            confidence += min(0.1, max(0.0, self.standing_torso_angle_thresh - features.torso_angle) * 0.01)
        if features.left_knee_angle is not None and features.right_knee_angle is not None:
            min_knee = min(features.left_knee_angle, features.right_knee_angle)
            confidence += min(0.1, max(0.0, min_knee - self.standing_knee_angle_thresh) * 0.005)

        confidence -= min(0.2, max(0.0, center_disp - self.standing_max_center_displacement) * 0.4)
        confidence -= min(0.2, max(0.0, ankle_motion - self.standing_max_ankle_motion) * 0.4)
        return max(0.5, min(0.95, confidence))


def _point_delta(
    previous: tuple[float, float] | None,
    current: tuple[float, float] | None,
) -> float | None:
    if previous is None or current is None:
        return None
    return math.hypot(current[0] - previous[0], current[1] - previous[1])
