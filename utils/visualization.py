"""可视化工具: 在视频帧上绘制跟踪框与 person_id。"""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np


def id_to_bgr(person_id: int) -> tuple[int, int, int]:
    """根据 person_id 生成稳定的 BGR 颜色。"""
    hue = (int(person_id) * 47) % 180
    hsv = np.uint8([[[hue, 220, 255]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0][0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def draw_tracks(
    frame: Any,
    tracks: Sequence[Any],
    box_color: Sequence[int] = (0, 255, 0),
    text_color: Sequence[int] = (255, 255, 255),
    use_id_color: bool = True,
    draw_confidence: bool = True,
    box_thickness: int = 2,
    text_thickness: int = 2,
    font_scale: float = 0.7,
) -> Any:
    """在 frame 上绘制跟踪结果, 返回标注后的帧。"""
    height, width = frame.shape[:2]

    for track in tracks:
        x1, y1, x2, y2 = (int(round(value)) for value in track.bbox)
        x1 = max(0, min(width - 1, x1))
        x2 = max(x1 + 1, min(width, x2))
        y1 = max(0, min(height - 1, y1))
        y2 = max(y1 + 1, min(height, y2))

        color = id_to_bgr(track.person_id) if use_id_color else tuple(int(value) for value in box_color)
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            color,
            thickness=box_thickness,
        )

        label = f"ID:{track.person_id}"
        if draw_confidence:
            label += f" {track.confidence:.2f}"

        text_x, text_y = x1, max(20, y1 - 8)
        (text_width, text_height), baseline = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            text_thickness,
        )
        cv2.rectangle(
            frame,
            (text_x, text_y - text_height - baseline),
            (text_x + text_width, text_y + baseline),
            color,
            thickness=-1,
        )
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            tuple(int(value) for value in text_color),
            thickness=text_thickness,
            lineType=cv2.LINE_AA,
        )

    return frame
