"""姿态特征计算。

本模块只负责把 YOLO Pose 关键点转换成行为分析可用的数值特征,
不判断 standing / walking / sitting。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from analysis.pose.pose_utils import (
    angle_between,
    get_keypoint,
    midpoint,
    normalize_point,
    normalize_point_to_frame,
    valid_keypoint_count,
)


def _round(value: Optional[float], digits: int = 3) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _round_point(point: Optional[Tuple[float, float]], digits: int = 3) -> Optional[Tuple[float, float]]:
    if point is None:
        return None
    return round(float(point[0]), digits), round(float(point[1]), digits)


@dataclass
class PoseFeatures:
    """单人单帧姿态特征。"""

    person_center: Optional[Tuple[float, float]]
    person_center_frame_norm: Optional[Tuple[float, float]]
    shoulder_center: Optional[Tuple[float, float]]
    hip_center: Optional[Tuple[float, float]]
    hip_center_norm: Optional[Tuple[float, float]]
    left_knee_angle: Optional[float]
    right_knee_angle: Optional[float]
    torso_angle: Optional[float]
    left_ankle: Optional[Tuple[float, float]]
    right_ankle: Optional[Tuple[float, float]]
    left_ankle_frame_norm: Optional[Tuple[float, float]]
    right_ankle_frame_norm: Optional[Tuple[float, float]]
    bbox_height: float
    bbox_width: float
    bbox_height_norm: float
    bbox_width_norm: float
    keypoint_visible_ratio: float
    keypoint_mean_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """转成 JSON 友好的字典。"""
        return {
            "person_center": list(self.person_center) if self.person_center else None,
            "person_center_frame_norm": list(self.person_center_frame_norm)
            if self.person_center_frame_norm
            else None,
            "shoulder_center": list(self.shoulder_center) if self.shoulder_center else None,
            "hip_center": list(self.hip_center) if self.hip_center else None,
            "hip_center_norm": list(self.hip_center_norm) if self.hip_center_norm else None,
            "left_knee_angle": _round(self.left_knee_angle),
            "right_knee_angle": _round(self.right_knee_angle),
            "torso_angle": _round(self.torso_angle),
            "left_ankle": list(self.left_ankle) if self.left_ankle else None,
            "right_ankle": list(self.right_ankle) if self.right_ankle else None,
            "left_ankle_frame_norm": list(self.left_ankle_frame_norm)
            if self.left_ankle_frame_norm
            else None,
            "right_ankle_frame_norm": list(self.right_ankle_frame_norm)
            if self.right_ankle_frame_norm
            else None,
            "bbox_height": round(self.bbox_height, 3),
            "bbox_width": round(self.bbox_width, 3),
            "bbox_height_norm": round(self.bbox_height_norm, 3),
            "bbox_width_norm": round(self.bbox_width_norm, 3),
            "keypoint_visible_ratio": round(self.keypoint_visible_ratio, 3),
            "keypoint_mean_confidence": round(self.keypoint_mean_confidence, 3),
        }


def extract_features(
    keypoints: Sequence[Sequence[float]],
    bbox: Sequence[float],
    frame_width: int,
    frame_height: int,
    keypoint_min_conf: float = 0.3,
) -> PoseFeatures:
    """从关键点与 bbox 提取姿态特征。"""
    x1, y1, x2, y2 = (float(value) for value in bbox)
    bbox_width = max(1e-3, x2 - x1)
    bbox_height = max(1e-3, y2 - y1)

    person_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    person_center_frame_norm = normalize_point_to_frame(person_center, frame_width, frame_height)

    left_shoulder = get_keypoint(keypoints, "left_shoulder", keypoint_min_conf)
    right_shoulder = get_keypoint(keypoints, "right_shoulder", keypoint_min_conf)
    left_hip = get_keypoint(keypoints, "left_hip", keypoint_min_conf)
    right_hip = get_keypoint(keypoints, "right_hip", keypoint_min_conf)
    left_knee = get_keypoint(keypoints, "left_knee", keypoint_min_conf)
    right_knee = get_keypoint(keypoints, "right_knee", keypoint_min_conf)
    left_ankle = get_keypoint(keypoints, "left_ankle", keypoint_min_conf)
    right_ankle = get_keypoint(keypoints, "right_ankle", keypoint_min_conf)

    shoulder_center = midpoint(left_shoulder, right_shoulder)
    hip_center = midpoint(left_hip, right_hip)
    hip_center_norm = (
        normalize_point(hip_center, (x1, y1, bbox_width, bbox_height))
        if hip_center is not None
        else None
    )

    left_knee_angle = (
        angle_between(left_hip, left_knee, left_ankle)
        if all(point is not None for point in (left_hip, left_knee, left_ankle))
        else None
    )
    right_knee_angle = (
        angle_between(right_hip, right_knee, right_ankle)
        if all(point is not None for point in (right_hip, right_knee, right_ankle))
        else None
    )

    torso_angle = None
    if shoulder_center is not None and hip_center is not None:
        dx = hip_center[0] - shoulder_center[0]
        dy = hip_center[1] - shoulder_center[1]
        torso_angle = _vector_angle_degrees((dx, dy), (0.0, 1.0))

    left_ankle_raw = (left_ankle[0], left_ankle[1]) if left_ankle is not None else None
    right_ankle_raw = (right_ankle[0], right_ankle[1]) if right_ankle is not None else None
    left_ankle_frame_norm = (
        normalize_point_to_frame(left_ankle_raw, frame_width, frame_height)
        if left_ankle_raw is not None
        else None
    )
    right_ankle_frame_norm = (
        normalize_point_to_frame(right_ankle_raw, frame_width, frame_height)
        if right_ankle_raw is not None
        else None
    )

    total_keypoints = max(1, len(keypoints))
    visible_count = valid_keypoint_count(keypoints, keypoint_min_conf)
    keypoint_mean_confidence = _mean_keypoint_confidence(keypoints)

    return PoseFeatures(
        person_center=person_center,
        person_center_frame_norm=person_center_frame_norm,
        shoulder_center=shoulder_center,
        hip_center=hip_center,
        hip_center_norm=hip_center_norm,
        left_knee_angle=left_knee_angle,
        right_knee_angle=right_knee_angle,
        torso_angle=torso_angle,
        left_ankle=left_ankle_raw,
        right_ankle=right_ankle_raw,
        left_ankle_frame_norm=left_ankle_frame_norm,
        right_ankle_frame_norm=right_ankle_frame_norm,
        bbox_height=bbox_height,
        bbox_width=bbox_width,
        bbox_height_norm=bbox_height / max(frame_height, 1e-6),
        bbox_width_norm=bbox_width / max(frame_width, 1e-6),
        keypoint_visible_ratio=visible_count / total_keypoints,
        keypoint_mean_confidence=keypoint_mean_confidence,
    )


def _vector_angle_degrees(
    vector_a: Tuple[float, float],
    vector_b: Tuple[float, float],
) -> float:
    import math

    norm_a = math.hypot(*vector_a)
    norm_b = math.hypot(*vector_b)
    if norm_a < 1e-6 or norm_b < 1e-6:
        return float("nan")
    cosine = (vector_a[0] * vector_b[0] + vector_a[1] * vector_b[1]) / (norm_a * norm_b)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _mean_keypoint_confidence(keypoints: Sequence[Sequence[float]]) -> float:
    if not keypoints:
        return 0.0
    confidences = [float(point[2]) for point in keypoints if len(point) >= 3]
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)
