"""汇总多个事件评测报告，生成可用于项目总结的总体指标。"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any

from evaluation.report_builder import save_report


def aggregate_reports(paths: list[str]) -> dict[str, Any]:
    reports = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
        if not isinstance(report, dict):
            raise ValueError(f"评测报告必须是对象: {path}")
        required = ("tp", "fp", "fn")
        if any(key not in report for key in required):
            raise ValueError(f"报告缺少 tp/fp/fn: {path}")
        reports.append((path, report))

    if not reports:
        raise ValueError("没有找到可汇总的评测报告")

    tp = sum(int(report["tp"]) for _, report in reports)
    fp = sum(int(report["fp"]) for _, report in reports)
    fn = sum(int(report["fn"]) for _, report in reports)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    onset = _weighted_mean(reports, "mean_onset_error_seconds")
    duration = _weighted_mean(reports, "mean_duration_error_seconds")
    return {
        "report_count": len(reports),
        "reports": [os.path.abspath(path) for path, _ in reports],
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "weighted_mean_onset_error_seconds": onset,
        "weighted_mean_duration_error_seconds": duration,
        "aggregation": "micro_average_by_event_count",
    }


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _weighted_mean(reports: list[tuple[str, dict]], key: str) -> float | None:
    values = []
    for _, report in reports:
        value = report.get(key)
        weight = int(report.get("tp", 0))
        if value is not None and weight > 0:
            values.append((float(value), weight))
    if not values:
        return None
    return round(sum(value * weight for value, weight in values) / sum(weight for _, weight in values), 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总多个事件评测 JSON 报告")
    parser.add_argument("--reports", nargs="+", required=True, help="报告路径或 glob")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = []
    for pattern in args.reports:
        matches = glob.glob(pattern)
        paths.extend(matches or [pattern])
    report = aggregate_reports(sorted(set(paths)))
    save_report(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
