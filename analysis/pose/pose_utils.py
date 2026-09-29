"""人体关键点基础工具。

只处理关键点索引、有效性判断、坐标提取、角度计算与归一化,
不做行为判断。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


KEYPOINT_INDEX = {
    "nose": 0,
    "left_eye": 1,
    "right_eye": 2,
    "left_ear": 3,
    "right_ear": 4,
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_elbow": 7,
    "right_elbow": 8,
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
    "left_knee": 13,
    "right_knee": 14,
    "left_ankle": 15,
    "right_ankle": 16,
}


def get_keypoint(
    keypoints: Sequence[Sequence[float]],
    name: str,
    min_conf: float = 0.0,
) -> Optional[Tuple[float, float, float]]:
    """按名称获取关键点; 置信度不足或索引越界时返回 None。"""
    index = KEYPOINT_INDEX.get(name)
    if index is None:
        return None
    return get_keypoint_by_index(keypoints, index, min_conf)


def get_keypoint_by_index(
    keypoints: Sequence[Sequence[float]],
    index: int,
    min_conf: float = 0.0,
) -> Optional[Tuple[float, float, float]]:
    """按索引获取关键点。"""
    if index < 0 or index >= len(keypoints):
        return None
    point = keypoints[index]
    x, y, confidence = (float(point[0]), float(point[1]), float(point[2]))
    if not math.isfinite(x) or not math.isfinite(y) or not math.isfinite(confidence):
        return None
    if confidence < min_conf:
        return None
    return x, y, confidence


def valid_keypoint_count(
    keypoints: Sequence[Sequence[float]],
    min_conf: float = 0.0,
) -> int:
    """统计有效关键点数量。"""
    count = 0
    for index in range(len(keypoints)):
        if get_keypoint_by_index(keypoints, index, min_conf) is not None:
            count += 1
    return count


def angle_between(
    point_a: Sequence[float],
    point_b: Sequence[float],
    point_c: Sequence[float],
) -> float:
    """计算以 point_b 为顶点的角度, 返回 0-180 度。"""
    vector_ba = (
        float(point_a[0]) - float(point_b[0]),
        float(point_a[1]) - float(point_b[1]),
    )
    vector_bc = (
        float(point_c[0]) - float(point_b[0]),
        float(point_c[1]) - float(point_b[1]),
    )

    norm_ba = math.hypot(*vector_ba)
    norm_bc = math.hypot(*vector_bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return float("nan")

    cosine = (vector_ba[0] * vector_bc[0] + vector_ba[1] * vector_bc[1]) / (norm_ba * norm_bc)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def midpoint(
    point_a: Optional[Sequence[float]],
    point_b: Optional[Sequence[float]],
) -> Optional[Tuple[float, float]]:
    """计算两点中点, 任一点无效时返回 None。"""
    if point_a is None or point_b is None:
        return None
    return (
        (float(point_a[0]) + float(point_b[0])) / 2.0,
        (float(point_a[1]) + float(point_b[1])) / 2.0,
    )


def normalize_point(
    point: Sequence[float],
    reference: Sequence[float],
) -> Tuple[float, float]:
    """把点相对 bbox 归一化到 0-1。reference 为 [x1, y1, width, height]。"""
    x = (float(point[0]) - float(reference[0])) / max(float(reference[2]), 1e-6)
    y = (float(point[1]) - float(reference[1])) / max(float(reference[3]), 1e-6)
    return x, y


def normalize_point_to_frame(
    point: Sequence[float],
    frame_width: int,
    frame_height: int,
) -> Tuple[float, float]:
    """把点相对整帧归一化到 0-1。"""
    return (
        float(point[0]) / max(float(frame_width), 1e-6),
        float(point[1]) / max(float(frame_height), 1e-6),
    )


def keypoints_to_list(
    keypoints: Sequence[Sequence[float]],
    min_conf: float = 0.0,
) -> List[List[float]]:
    """将关键点统一为 [x, y, confidence] 列表。"""
    normalized: List[List[float]] = []
    for index in range(len(keypoints)):
        point = get_keypoint_by_index(keypoints, index, min_conf)
        if point is None:
            normalized.append([0.0, 0.0, 0.0])
        else:
            normalized.append([point[0], point[1], point[2]])
    return normalized
