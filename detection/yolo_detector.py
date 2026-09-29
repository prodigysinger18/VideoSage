from typing import Any, Dict, Optional, Sequence

from ultralytics import YOLO


class YOLODetector:


    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        conf_threshold: float = 0.2,
        iou_threshold: float = 0.7,
        imgsz: int = 640,
        max_det: int = 300,
        device: Any = 0,
        quantize: Optional[int] = 16,
        classes: Optional[Sequence[int]] = None,
        class_names: Optional[Dict[int, str]] = None,
    ):

        self.model = YOLO(
            model_path
        )
        self.conf_threshold = float(conf_threshold)
        self.iou_threshold = float(iou_threshold)
        self.imgsz = int(imgsz)
        self.max_det = int(max_det)
        self.device = device
        self.quantize = int(quantize) if quantize is not None else 32
        self.classes = list(classes) if classes is not None else [0]
        self.class_names = class_names or {0: "person"}


    def detect(self, frame):

        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            max_det=self.max_det,
            device=self.device,
            quantize=self.quantize,
            classes=self.classes,
            verbose=False,
        )


        return results
