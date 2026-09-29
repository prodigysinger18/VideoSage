"""YOLO11 Pose 人体关键点检测模块。

职责:
    加载一次 YOLO11 Pose 模型, 对单帧或单人裁剪区域执行姿态估计,
    输出 17 个 COCO 关键点及其置信度。

本模块不负责:
    - 人物跟踪
    - 行为判断
    - 结果落盘
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np
from ultralytics import YOLO


COCO_KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


class YOLOPose:
    """YOLO11 Pose 模型封装。"""

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.7,
        imgsz: int = 640,
        max_det: int = 1,
        device: Any = 0,
        quantize: Optional[int] = 16,
    ) -> None:
        self.model_path = os.path.abspath(model_path)
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"YOLO Pose 模型文件不存在: {self.model_path}")

        self.conf_threshold = float(conf_threshold)
        self.iou_threshold = float(iou_threshold)
        self.imgsz = int(imgsz)
        self.max_det = int(max_det)
        self.quantize = int(quantize) if quantize is not None else 32
        self.device = self._resolve_device(device)
        self.half = self.quantize == 16 and str(self.device) != "cpu"
        self.model = YOLO(self.model_path)

    @staticmethod
    def _resolve_device(device: Any) -> Any:
        if str(device).lower() == "cpu":
            return "cpu"

        try:
            import torch

            if not torch.cuda.is_available():
                print("[YOLOPose] CUDA 不可用, 自动回退到 CPU")
                return "cpu"
        except Exception as exc:
            print(f"[YOLOPose] CUDA 检测失败, 自动回退到 CPU: {exc}")
            return "cpu"

        return device

    def detect(self, frame: Any, bbox: Optional[Sequence[float]] = None) -> List[Dict[str, Any]]:
        """对图像执行姿态估计。

        Args:
            frame: 完整 BGR 帧。
            bbox: 可选 [x1, y1, x2, y2], 传入时只推理该人物裁剪区域,
                  关键点坐标会映射回原图坐标。

        Returns:
            列表, 每项为:
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float,
                    "keypoints": [[x, y, conf], ...],
                }
        """
        input_image = frame
        offset_x = 0.0
        offset_y = 0.0

        if bbox is not None:
            x1, y1, x2, y2 = (float(value) for value in bbox)
            frame_height, frame_width = frame.shape[:2]
            x1 = max(0.0, min(float(frame_width) - 1.0, x1))
            y1 = max(0.0, min(float(frame_height) - 1.0, y1))
            x2 = max(x1 + 1.0, min(float(frame_width), x2))
            y2 = max(y1 + 1.0, min(float(frame_height), y2))

            crop = frame[int(round(y1)) : int(round(y2)), int(round(x1)) : int(round(x2))]
            if crop.size == 0:
                return []
            input_image = np.ascontiguousarray(crop)
            offset_x = x1
            offset_y = y1

        predictions = self.model.predict(
            source=input_image,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            max_det=self.max_det,
            device=self.device,
            quantize=16 if self.half else 32,
            verbose=False,
        )

        if not predictions:
            return []

        result = predictions[0]
        if result.keypoints is None or len(result.keypoints) == 0:
            return []

        keypoints_data = result.keypoints.data.cpu().numpy()
        boxes_data = None
        confidences = [1.0] * len(keypoints_data)

        if result.boxes is not None and len(result.boxes) > 0:
            boxes_data = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy().tolist()

        pose_results: List[Dict[str, Any]] = []
        for index, keypoints in enumerate(keypoints_data):
            keypoints = np.asarray(keypoints, dtype=np.float32).reshape(-1, 3)
            if offset_x or offset_y:
                keypoints[:, 0] += offset_x
                keypoints[:, 1] += offset_y

            if boxes_data is not None and index < len(boxes_data):
                box = [float(value) for value in boxes_data[index]]
                box[0] += offset_x
                box[1] += offset_y
                box[2] += offset_x
                box[3] += offset_y
            else:
                box = list(bbox) if bbox is not None else [0.0, 0.0, float(frame.shape[1]), float(frame.shape[0])]

            pose_results.append(
                {
                    "bbox": [round(float(value), 2) for value in box],
                    "confidence": float(confidences[index]) if index < len(confidences) else 1.0,
                    "keypoints": keypoints.round(2).tolist(),
                }
            )

        return pose_results
