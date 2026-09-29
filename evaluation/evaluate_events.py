"""Compare labeled behavior or anomaly intervals with pipeline output."""

from __future__ import annotations

import argparse
import os

from evaluation.report_builder import load_json, save_report


def interval_iou(first: dict, second: dict) -> float:
    overlap = max(0.0, min(first["end_time"], second["end_time"]) - max(first["start_time"], second["start_time"]))
    union = max(first["end_time"], second["end_time"]) - min(first["start_time"], second["start_time"])
    return overlap / union if union > 0 else 0.0


def _records(data: object, label_key: str) -> list[dict]:
    if not isinstance(data, list):
        raise ValueError("标注和预测均须为 JSON 数组")
    rows = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or label_key not in item or "start_time" not in item or "end_time" not in item:
            raise ValueError(f"第 {index + 1} 条记录缺少 {label_key}/start_time/end_time")
        start = float(item["start_time"])
        end = float(item["end_time"])
        if start < 0 or end <= start:
            raise ValueError(f"第 {index + 1} 条记录的时间范围无效")
        rows.append({label_key: str(item[label_key]), "person_id": item.get("person_id"), "start_time": start, "end_time": end})
    return rows


def evaluate_events(ground_truth: list, predictions: list, label_key: str = "event", iou_threshold: float = 0.3, match_person: bool = True) -> dict:
    if label_key not in {"event", "action"}:
        raise ValueError("label_key 只能是 event 或 action")
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold 须在 (0, 1] 内")
    truth = _records(ground_truth, label_key)
    predicted = _records(predictions, label_key)
    if match_person and any(row["person_id"] is None for row in truth + predicted):
        raise ValueError("按人物匹配时，每条记录必须包含 person_id")

    candidates = []
    for truth_index, reference in enumerate(truth):
        for prediction_index, result in enumerate(predicted):
            if reference[label_key] != result[label_key]:
                continue
            if match_person and str(reference["person_id"]) != str(result["person_id"]):
                continue
            score = interval_iou(reference, result)
            if score >= iou_threshold:
                candidates.append((score, truth_index, prediction_index))
    matched_truth = set()
    matched_prediction = set()
    matches = []
    for score, truth_index, prediction_index in sorted(candidates, reverse=True):
        if truth_index in matched_truth or prediction_index in matched_prediction:
            continue
        matched_truth.add(truth_index)
        matched_prediction.add(prediction_index)
        matches.append((score, truth_index, prediction_index))

    labels = sorted({row[label_key] for row in truth + predicted})
    per_class = {}
    for label in labels:
        true_count = sum(truth[index][label_key] == label for _, index, _ in matches)
        predicted_count = sum(row[label_key] == label for row in predicted)
        ground_truth_count = sum(row[label_key] == label for row in truth)
        per_class[label] = _scores(true_count, predicted_count - true_count, ground_truth_count - true_count)
    onset_errors = [abs(truth[truth_index]["start_time"] - predicted[prediction_index]["start_time"]) for _, truth_index, prediction_index in matches]
    duration_errors = [abs(
        (truth[truth_index]["end_time"] - truth[truth_index]["start_time"])
        - (predicted[prediction_index]["end_time"] - predicted[prediction_index]["start_time"])
    ) for _, truth_index, prediction_index in matches]
    report = _scores(len(matches), len(predicted) - len(matches), len(truth) - len(matches))
    report.update({
        "has_ground_truth": bool(truth),
        "label_key": label_key,
        "iou_threshold": iou_threshold,
        "match_person_id": match_person,
        "per_class": per_class,
        "mean_onset_error_seconds": round(sum(onset_errors) / len(onset_errors), 4) if onset_errors else None,
        "mean_duration_error_seconds": round(sum(duration_errors) / len(duration_errors), 4) if duration_errors else None,
    })
    return report


def _scores(true_positive: int, false_positive: int, false_negative: int) -> dict:
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="使用人工标注评估行为或异常时间段")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label-key", choices=("event", "action"), default="event")
    parser.add_argument("--iou-threshold", type=float, default=0.3)
    parser.add_argument("--ignore-person-id", action="store_true")
    args = parser.parse_args()
    report = evaluate_events(load_json(args.ground_truth), load_json(args.predictions), args.label_key, args.iou_threshold, not args.ignore_person_id)
    report["ground_truth_file"] = os.path.abspath(args.ground_truth)
    report["prediction_file"] = os.path.abspath(args.predictions)
    save_report(args.output, report)
    print(f"precision={report['precision']} recall={report['recall']} f1={report['f1']}")
    print(f"output={os.path.abspath(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
