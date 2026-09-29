"""Lightweight ONNX person ReID feature extractor."""

from __future__ import annotations

import os
from typing import Any, Sequence

import cv2
import numpy as np


class ReIDExtractor:
    """Extract normalized person embeddings with an OpenCV DNN ONNX model."""

    def __init__(
        self,
        model_path: str | None,
        input_width: int = 128,
        input_height: int = 256,
        use_cuda: bool = True,
    ) -> None:
        self.available = bool(model_path and os.path.isfile(model_path))
        self.net = None
        self.input_size = (max(1, int(input_width)), max(1, int(input_height)))
        if not self.available:
            return

        try:
            self.net = cv2.dnn.readNetFromONNX(str(model_path))
            if use_cuda and cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA_FP16)
        except (cv2.error, OSError):
            self.net = None
            self.available = False

    def extract(self, frame: Any, bbox: Sequence[float]) -> np.ndarray | None:
        if not self.available or self.net is None:
            return None

        crop = _crop_person(frame, bbox)
        if crop is None:
            return None

        blob = cv2.dnn.blobFromImage(
            crop,
            scalefactor=1.0 / 255.0,
            size=self.input_size,
            mean=(0.0, 0.0, 0.0),
            swapRB=True,
            crop=False,
        )

        try:
            self.net.setInput(blob)
            embedding = self.net.forward().reshape(-1).astype(np.float32)
        except cv2.error:
            return None

        norm = float(np.linalg.norm(embedding))
        return embedding / norm if norm > 1e-6 else None


def _crop_person(frame: Any, bbox: Sequence[float]) -> np.ndarray | None:
    if frame is None or not hasattr(frame, "shape"):
        return None
    frame_height, frame_width = frame.shape[:2]
    x1, y1, x2, y2 = (float(value) for value in bbox)
    x1 = max(0, min(frame_width - 1, int(round(x1))))
    y1 = max(0, min(frame_height - 1, int(round(y1))))
    x2 = max(x1 + 1, min(frame_width, int(round(x2))))
    y2 = max(y1 + 1, min(frame_height, int(round(y2))))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 16:
        return None
    return crop
