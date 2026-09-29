"""基于 OpenCV 的轻量人物外观特征。"""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np


def extract_appearance_feature(
    frame: Any,
    bbox: Sequence[float],
) -> np.ndarray | None:
    """提取人物主体区域的上下半身 HSV 直方图。"""
    frame_height, frame_width = frame.shape[:2]
    x1, y1, x2, y2 = (float(value) for value in bbox)
    x1 = max(0, min(frame_width - 1, int(round(x1))))
    y1 = max(0, min(frame_height - 1, int(round(y1))))
    x2 = max(x1 + 1, min(frame_width, int(round(x2))))
    y2 = max(y1 + 1, min(frame_height, int(round(y2))))

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 8:
        return None

    # 收窄到人物框中央, 降低背景和边缘特效对颜色模板的影响。
    height, width = crop.shape[:2]
    crop = crop[
        int(height * 0.08) : max(int(height * 0.92), 1),
        int(width * 0.18) : max(int(width * 0.82), 1),
    ]
    if crop.size == 0:
        return None

    split = max(1, crop.shape[0] // 2)
    upper = crop[:split]
    lower = crop[split:]
    if lower.size == 0:
        lower = upper

    feature = np.concatenate(
        (
            _hsv_histogram(upper),
            _hsv_histogram(lower),
        )
    ).astype(np.float32)
    norm = float(np.linalg.norm(feature))
    return feature / norm if norm > 1e-6 else None


def appearance_similarity(
    first: np.ndarray | None,
    second: np.ndarray | None,
) -> float:
    """返回 0-1 的余弦相似度。"""
    if first is None or second is None or first.shape != second.shape:
        return 0.0
    similarity = float(np.dot(first, second))
    return max(0.0, min(1.0, similarity))


def _hsv_histogram(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist(
        [hsv],
        [0, 1],
        None,
        [24, 16],
        [0, 180, 0, 256],
    )
    cv2.normalize(histogram, histogram, norm_type=cv2.NORM_L2)
    return histogram.reshape(-1)
