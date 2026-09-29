"""应用层 Pose 估计器。

负责把第一阶段跟踪结果(bbox + person_id)交给 YOLO11 Pose,
并返回与 person_id 关联的姿态结果。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from detection.yolo_pose import YOLOPose


class PoseEstimator:
    """封装 YOLOPose, 为每个人物输出关键点结果。"""

    def __init__(self, pose_model: YOLOPose, keypoint_conf_threshold: float = 0.3) -> None:
        self.pose_model = pose_model
        self.keypoint_conf_threshold = float(keypoint_conf_threshold)

    def estimate(
        self,
        frame: Any,
        bbox: Sequence[float],
        person_id: int,
        timestamp: float,
    ) -> Dict[str, Any]:
        """对单个跟踪人物执行姿态估计。"""
        pose_detections = self.pose_model.detect(frame, bbox=bbox)
        if not pose_detections:
            return {
                "person_id": person_id,
                "timestamp": timestamp,
                "bbox": [float(value) for value in bbox],
                "confidence": 0.0,
                "keypoints": [],
            }

        detection = pose_detections[0]
        return {
            "person_id": person_id,
            "timestamp": timestamp,
            "bbox": detection.get("bbox", list(bbox)),
            "confidence": float(detection.get("confidence", 0.0)),
            "keypoints": detection.get("keypoints", []),
        }
