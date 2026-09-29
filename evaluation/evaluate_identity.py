"""Count observed identity switches against frame-level person annotations."""

from __future__ import annotations

import argparse
import os
from collections import defaultdict

from evaluation.report_builder import load_json, save_report


def bbox_iou(first: list[float], second: list[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _records(data: object) -> dict[int, list[dict]]:
    if not isinstance(data, list):
        raise ValueError("标注和预测均须为 JSON 数组")
    by_frame = defaultdict(list)
    for index, item in enumerate(data):
        if not isinstance(item, dict) or any(item.get(field) is None for field in ("frame_id", "person_id", "bbox")):
            raise ValueError(f"第 {index + 1} 条记录缺少 frame_id/person_id/bbox")
        bbox = item["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"第 {index + 1} 条 bbox 不是四个坐标")
        bbox = [float(value) for value in bbox]
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError(f"第 {index + 1} 条 bbox 无效")
        by_frame[int(item["frame_id"])].append({"person_id": str(item["person_id"]), "bbox": bbox})
    return by_frame


def evaluate_identity(ground_truth: list, predictions: list, iou_threshold: float = 0.5) -> dict:
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold 须在 (0, 1] 内")
    truth = _records(ground_truth)
    predicted = _records(predictions)
    last_prediction_by_person = {}
    switches_by_person = defaultdict(int)
    matches = 0
    annotated_boxes = sum(len(rows) for rows in truth.values())
    for frame_id in sorted(truth):
        references = truth[frame_id]
        detections = predicted.get(frame_id, [])
        candidates = []
        for reference_index, reference in enumerate(references):
            for prediction_index, detection in enumerate(detections):
                score = bbox_iou(reference["bbox"], detection["bbox"])
                if score >= iou_threshold:
                    candidates.append((score, reference_index, prediction_index))
        used_reference = set()
        used_prediction = set()
        for _, reference_index, prediction_index in sorted(candidates, reverse=True):
            if reference_index in used_reference or prediction_index in used_prediction:
                continue
            used_reference.add(reference_index)
            used_prediction.add(prediction_index)
            identity = references[reference_index]["person_id"]
            predicted_identity = detections[prediction_index]["person_id"]
            if identity in last_prediction_by_person and last_prediction_by_person[identity] != predicted_identity:
                switches_by_person[identity] += 1
            last_prediction_by_person[identity] = predicted_identity
            matches += 1
    return {
        "iou_threshold": iou_threshold,
        "annotated_boxes": annotated_boxes,
        "predicted_boxes_on_annotated_frames": sum(len(predicted.get(frame_id, [])) for frame_id in truth),
        "matched_boxes": matches,
        "matched_box_recall": round(matches / annotated_boxes, 4) if annotated_boxes else None,
        "identity_switches": sum(switches_by_person.values()),
        "switches_by_person": dict(sorted(switches_by_person.items())),
        "note": "仅统计匹配框上的 ID 切换；不是 MOTA 或 IDF1。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="使用逐帧人工标注统计人物 ID 切换")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()
    report = evaluate_identity(load_json(args.ground_truth), load_json(args.predictions), args.iou_threshold)
    report["ground_truth_file"] = os.path.abspath(args.ground_truth)
    report["prediction_file"] = os.path.abspath(args.predictions)
    save_report(args.output, report)
    print(f"matched_boxes={report['matched_boxes']} identity_switches={report['identity_switches']}")
    print(f"output={os.path.abspath(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
