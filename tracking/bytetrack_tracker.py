
from types import SimpleNamespace
from typing import Any

import numpy as np
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker


class TrackResult(dict):
    """项目内部跟踪结果, 同时支持字典和属性访问。"""

    def __init__(self, track_id, bbox, confidence, class_id=0):
        super().__init__(
            track_id=int(track_id),
            bbox=[float(value) for value in bbox],
            confidence=float(confidence),
            class_id=int(class_id),
        )

    @property
    def track_id(self):
        return self["track_id"]

    @property
    def bbox(self):
        return self["bbox"]

    @property
    def confidence(self):
        return self["confidence"]

    @property
    def person_id(self):
        return self["person_id"]

    @property
    def identity_confidence(self):
        return self.get("identity_confidence", 0.0)


class ByteTrackTracker:
    """
    ByteTrack 跟踪器封装。

    输入：
        detections = [
            [x1, y1, x2, y2, confidence],
            ...
        ]

    输出：
        [
            {
                "track_id": int,
                "bbox": [x1, y1, x2, y2],
                "confidence": float,
            },
            ...
        ]
    """

    def __init__(
        self,
        track_high_thresh=0.5,
        track_low_thresh=0.1,
        new_track_thresh=0.6,
        track_buffer=30,
        match_thresh=0.8,
        frame_rate=30,
        fuse_score=True,
        min_box_area=400,
        min_box_area_ratio=0.001,
        **_: Any,
    ):
        # Ultralytics 当前版本的 BYTETracker 需要 args
        args = SimpleNamespace(
            track_high_thresh=track_high_thresh,
            track_low_thresh=track_low_thresh,
            new_track_thresh=new_track_thresh,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            fuse_score=bool(fuse_score),
        )

        self.tracker = BYTETracker(args)
        self.min_box_area = max(0.0, float(min_box_area))
        self.min_box_area_ratio = max(0.0, float(min_box_area_ratio))

    def update(self, detections, frame=None):
        """
        更新 ByteTrack。

        参数：
            detections:
                [
                    [x1, y1, x2, y2, confidence],
                    ...
                ]

            frame:
                当前视频帧。
                当前 ByteTrack 主要使用检测结果，因此保留该参数
                方便后续兼容现有 pipeline。

        返回：
            [
                {
                    "track_id": int,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float,
                },
                ...
            ]
        """

        detections = self._to_boxes(detections, frame)

        # 当前 Ultralytics BYTETracker.update() 使用检测结果
        tracks = self.tracker.update(detections, frame)

        results = []

        array = np.asarray(tracks, dtype=np.float32)
        if array.ndim == 1 and array.size:
            array = array.reshape(1, -1)
        for row in array if array.size else []:
            if len(row) < 5:
                continue
            results.append(TrackResult(row[4], row[:4], row[5] if len(row) > 5 else 0.0, row[6] if len(row) > 6 else 0))

        return results

    def _to_boxes(self, detections, frame=None):
        orig_shape = (1, 1)
        if frame is not None and hasattr(frame, "shape"):
            orig_shape = (int(frame.shape[0]), int(frame.shape[1]))
        if detections is None:
            return Boxes(np.empty((0, 6), dtype=np.float32), orig_shape)
        if isinstance(detections, Boxes):
            return self._filter_boxes(detections)
        if hasattr(detections, "boxes"):
            detections = [detections]
        if isinstance(detections, (list, tuple)) and detections and hasattr(detections[0], "boxes"):
            arrays = []
            for result in detections:
                if getattr(result, "orig_shape", None) is not None:
                    orig_shape = tuple(int(value) for value in result.orig_shape[:2])
                boxes = getattr(result, "boxes", None)
                if boxes is not None and len(boxes):
                    arrays.append(boxes.cpu().numpy().data[:, :6])
            data = np.concatenate(arrays, axis=0) if arrays else np.empty((0, 6), dtype=np.float32)
            return self._filter_boxes(Boxes(data, orig_shape))
        array = np.asarray(detections, dtype=np.float32)
        if array.size == 0:
            array = np.empty((0, 6), dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.shape[1] == 5:
            array = np.column_stack((array, np.zeros(len(array), dtype=np.float32)))
        return self._filter_boxes(Boxes(array[:, :6], orig_shape))

    def _filter_boxes(self, boxes):
        if len(boxes) == 0:
            return boxes
        height, width = boxes.orig_shape
        threshold = max(self.min_box_area, float(height * width) * self.min_box_area_ratio)
        xyxy = np.asarray(boxes.xyxy, dtype=np.float32)
        areas = np.maximum(0.0, xyxy[:, 2] - xyxy[:, 0]) * np.maximum(0.0, xyxy[:, 3] - xyxy[:, 1])
        return boxes[areas >= threshold]

