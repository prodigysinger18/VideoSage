"""基于人物框和姿态关键点的轻量穿搭分析。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Sequence

import cv2
import numpy as np

from analysis.pose.pose_utils import get_keypoint


class OutfitAnalyzer:
    """定期采样服装区域，并按 person_id 聚合稳定结果。"""

    def __init__(self, sample_interval_frames: int = 15, min_keypoint_conf: float = 0.3) -> None:
        self.sample_interval_frames = max(1, int(sample_interval_frames))
        self.min_keypoint_conf = float(min_keypoint_conf)
        self._observations: Dict[int, list[Dict[str, Any]]] = defaultdict(list)

    def update(
        self,
        frame: np.ndarray,
        person_id: int,
        frame_id: int,
        timestamp: float,
        bbox: Sequence[float],
        keypoints: Sequence[Sequence[float]],
        detection_confidence: float = 1.0,
    ) -> Dict[str, Any] | None:
        if frame_id % self.sample_interval_frames != 0:
            return None

        observation = self._analyze(
            frame,
            person_id,
            timestamp,
            bbox,
            keypoints,
            detection_confidence,
        )
        if observation is not None:
            self._observations[int(person_id)].append(observation)
        return observation

    def build_profiles(self) -> list[Dict[str, Any]]:
        profiles = []
        for person_id, observations in sorted(self._observations.items()):
            if not observations:
                continue
            upper_sleeve, sleeve_consistency = _weighted_vote(observations, "upper", "sleeve")
            upper_color, upper_color_consistency = _weighted_vote(observations, "upper", "color")
            upper_type, upper_type_consistency = _weighted_vote(observations, "upper", "type")
            lower_length, length_consistency = _weighted_vote(observations, "lower", "length")
            lower_color, lower_color_consistency = _weighted_vote(observations, "lower", "color")
            lower_type, lower_type_consistency = _weighted_vote(observations, "lower", "type")
            consistencies = [
                sleeve_consistency,
                upper_color_consistency,
                upper_type_consistency,
                length_consistency,
                lower_color_consistency,
                lower_type_consistency,
            ]
            valid_consistencies = [value for value in consistencies if value > 0.0]
            consistency = sum(valid_consistencies) / len(valid_consistencies) if valid_consistencies else 0.0
            quality = sum(item.get("sample_weight", 0.0) for item in observations) / len(observations)
            sample_factor = min(1.0, (len(observations) / 8.0) ** 0.5)
            profiles.append(
                {
                    "person_id": person_id,
                    "upper": {
                        "sleeve": upper_sleeve,
                        "color": upper_color,
                        "type": upper_type,
                    },
                    "lower": {
                        "length": lower_length,
                        "color": lower_color,
                        "type": lower_type,
                    },
                    "confidence": round(min(0.95, consistency * quality * sample_factor), 4),
                    "sample_count": len(observations),
                }
            )
        return profiles

    def _analyze(
        self,
        frame: np.ndarray,
        person_id: int,
        timestamp: float,
        bbox: Sequence[float],
        keypoints: Sequence[Sequence[float]],
        detection_confidence: float,
    ) -> Dict[str, Any] | None:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = _clip_bbox(bbox, width, height)
        if x2 - x1 < 12 or y2 - y1 < 24:
            return None

        box_height = y2 - y1
        upper_roi = _pose_region(
            frame,
            keypoints,
            ("left_shoulder", "right_shoulder", "left_hip", "right_hip"),
            self.min_keypoint_conf,
            frame[y1 + int(0.18 * box_height) : y1 + int(0.52 * box_height), x1:x2],
        )
        lower_roi = _pose_region(
            frame,
            keypoints,
            ("left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"),
            self.min_keypoint_conf,
            frame[y1 + int(0.52 * box_height) : y1 + int(0.9 * box_height), x1:x2],
        )
        upper_color = _dominant_color(upper_roi)
        lower_color = _dominant_color(lower_roi)

        sleeve = self._classify_sleeve(frame, keypoints, upper_color)
        lower_type, lower_length = self._classify_lower(frame, bbox, keypoints, lower_color)
        visible = sum(
            get_keypoint(keypoints, name, self.min_keypoint_conf) is not None
            for name in ("left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_hip", "right_hip", "left_knee", "right_knee")
        )
        bbox_area_ratio = ((x2 - x1) * (y2 - y1)) / max(width * height, 1)
        sharpness = _sharpness_quality(frame[y1:y2, x1:x2])
        detection_quality = max(0.0, min(1.0, float(detection_confidence)))
        sample_weight = (
            max(0.05, min(1.0, bbox_area_ratio * 12.0))
            * (visible / 8.0)
            * sharpness
            * detection_quality
        )
        if visible < 4 or sample_weight < 0.08:
            return None
        confidence = min(0.9, (0.4 + visible * 0.06) * min(1.0, 0.5 + sample_weight))

        return {
            "person_id": int(person_id),
            "timestamp": round(float(timestamp), 4),
            "upper": {
                "sleeve": sleeve,
                "color": upper_color,
                "type": "long_sleeve_top" if sleeve == "long_sleeve" else "short_sleeve_top" if sleeve == "short_sleeve" else "unknown",
            },
            "lower": {"length": lower_length, "color": lower_color, "type": lower_type},
            "confidence": round(confidence, 4),
            "sample_weight": round(sample_weight, 4),
        }

    def _classify_sleeve(self, frame: np.ndarray, keypoints: Sequence[Sequence[float]], torso_color: str) -> str:
        votes = []
        for side in ("left", "right"):
            elbow = get_keypoint(keypoints, f"{side}_elbow", self.min_keypoint_conf)
            wrist = get_keypoint(keypoints, f"{side}_wrist", self.min_keypoint_conf)
            if elbow is None or wrist is None:
                continue
            forearm_color = _point_color(frame, _midpoint(elbow, wrist))
            votes.append("long_sleeve" if forearm_color == torso_color else "short_sleeve")
        return Counter(votes).most_common(1)[0][0] if votes else "unknown"

    def _classify_lower(
        self,
        frame: np.ndarray,
        bbox: Sequence[float],
        keypoints: Sequence[Sequence[float]],
        lower_color: str,
    ) -> tuple[str, str]:
        knee_colors = []
        ankles_visible = 0
        for side in ("left", "right"):
            knee = get_keypoint(keypoints, f"{side}_knee", self.min_keypoint_conf)
            ankle = get_keypoint(keypoints, f"{side}_ankle", self.min_keypoint_conf)
            if knee is not None:
                knee_colors.append(_point_color(frame, knee))
            if ankle is not None:
                ankles_visible += 1

        matching_knees = sum(color == lower_color for color in knee_colors)
        length = "long" if matching_knees >= 1 else "short" if knee_colors else "unknown"

        x1, _, x2, _ = (float(value) for value in bbox)
        left_knee = get_keypoint(keypoints, "left_knee", self.min_keypoint_conf)
        right_knee = get_keypoint(keypoints, "right_knee", self.min_keypoint_conf)
        if left_knee is not None and right_knee is not None:
            knee_gap_ratio = abs(left_knee[0] - right_knee[0]) / max(x2 - x1, 1.0)
            if knee_gap_ratio < 0.18 and matching_knees == 0:
                return "skirt", "short"
        if length == "long" and ankles_visible:
            return "pants", "long"
        if length == "short":
            return "shorts", "short"
        return "unknown", length


def _clip_bbox(bbox: Sequence[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (int(round(float(value))) for value in bbox)
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)


def _midpoint(first: Sequence[float], second: Sequence[float]) -> tuple[float, float]:
    return (float(first[0] + second[0]) / 2.0, float(first[1] + second[1]) / 2.0)


def _point_color(frame: np.ndarray, point: Sequence[float]) -> str:
    x, y = int(point[0]), int(point[1])
    radius = 4
    return _dominant_color(frame[max(0, y - radius) : y + radius + 1, max(0, x - radius) : x + radius + 1])


def _pose_region(
    frame: np.ndarray,
    keypoints: Sequence[Sequence[float]],
    names: Sequence[str],
    min_confidence: float,
    fallback: np.ndarray,
) -> np.ndarray:
    points = [get_keypoint(keypoints, name, min_confidence) for name in names]
    valid = [point for point in points if point is not None]
    if len(valid) < max(3, len(names) // 2):
        return fallback
    frame_height, frame_width = frame.shape[:2]
    xs = [point[0] for point in valid]
    ys = [point[1] for point in valid]
    padding_x = max(4, int((max(xs) - min(xs)) * 0.12))
    padding_y = max(4, int((max(ys) - min(ys)) * 0.08))
    left = max(0, int(min(xs)) - padding_x)
    top = max(0, int(min(ys)) - padding_y)
    right = min(frame_width, int(max(xs)) + padding_x)
    bottom = min(frame_height, int(max(ys)) + padding_y)
    roi = frame[top:bottom, left:right]
    return roi if roi.size else fallback


def _sharpness_quality(roi: np.ndarray) -> float:
    if roi.size == 0:
        return 0.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return max(0.15, min(1.0, variance / 120.0))


def _dominant_color(roi: np.ndarray) -> str:
    if roi.size == 0:
        return "unknown"
    roi = cv2.GaussianBlur(roi, (5, 5), 0)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    hsv = hsv[(hsv[:, 1] > 20) | (hsv[:, 2] < 220)]
    if len(hsv) == 0:
        return "unknown"
    hue, saturation, value = np.median(hsv, axis=0)
    if value < 45:
        return "black"
    if saturation < 35 and value > 190:
        return "white"
    if saturation < 45:
        return "gray"
    if hue < 8 or hue >= 172:
        return "red"
    if hue < 20:
        return "orange"
    if hue < 35:
        return "yellow"
    if hue < 85:
        return "green"
    if hue < 105:
        return "blue"
    if hue < 135:
        return "purple"
    if hue < 172:
        return "pink"
    return "unknown"


def _weighted_vote(
    observations: Sequence[Dict[str, Any]],
    section: str,
    field: str,
) -> tuple[str, float]:
    votes = Counter()
    for item in observations:
        value = item[section][field]
        if value != "unknown":
            votes[value] += max(0.1, float(item.get("sample_weight", 1.0)))
    if not votes:
        return "unknown", 0.0
    value, winning_weight = votes.most_common(1)[0]
    return value, float(winning_weight / max(sum(votes.values()), 1e-6))
