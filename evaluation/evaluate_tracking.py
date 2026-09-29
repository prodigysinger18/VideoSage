"""评估已有 person_poses.json 的身份和轨迹稳定性。

示例:
    python -m evaluation.evaluate_tracking \
      --poses data/results/<video>/poses/person_poses.json \
      --output data/evaluation/reports/tracking_report.json \
      --fps 23.976
"""

from __future__ import annotations

import argparse
import os

from evaluation.metrics import tracking_statistics
from evaluation.report_builder import load_json, save_report


def evaluate(poses_path: str, output_path: str, fps: float | None = None) -> dict:
    records = load_json(poses_path)
    if not isinstance(records, list):
        raise ValueError("Pose 结果必须是 JSON 数组")
    report = tracking_statistics(records, fps=fps)
    report["source_file"] = os.path.abspath(poses_path)
    save_report(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 VideoSage 人物身份与轨迹稳定性")
    parser.add_argument("--poses", required=True, help="person_poses.json 路径")
    parser.add_argument("--output", required=True, help="评估报告输出路径")
    parser.add_argument("--fps", type=float, default=None)
    args = parser.parse_args()
    report = evaluate(args.poses, args.output, args.fps)
    print(f"unique_person_ids={report['unique_person_ids']}")
    print(f"raw_track_count={report['raw_track_count']}")
    print(f"track_fragmentation_count={report['track_fragmentation_count']}")
    print(f"output={os.path.abspath(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
