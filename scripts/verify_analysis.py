"""Read-only acceptance check for one analyzed video."""

from __future__ import annotations

import argparse
import json
import os

from core.config_loader import get_section, get_value, load_config, resolve_path
from database.sqlserver_manager import SQLServerManager


def _load_json(path: str):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def verify(video_id: int, config_path: str = "config.yaml") -> dict:
    config = load_config(config_path)
    with SQLServerManager(get_section(config, "database")) as manager:
        cursor = manager.execute("SELECT video_path FROM dbo.videos WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return {"video_id": video_id, "passed": False, "checks": {"database_video": False}}
        video_path = os.path.abspath(str(row[0]))
        cursor = manager.execute("""SELECT
            (SELECT COUNT(*) FROM dbo.persons WHERE video_id = ?) AS persons,
            (SELECT COUNT(*) FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id WHERE p.video_id = ?) AS behaviors,
            (SELECT COUNT(*) FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id WHERE p.video_id = ?) AS anomalies""", (video_id, video_id, video_id))
        counts = cursor.fetchone()
        cursor.close()

    results_root = resolve_path(config, get_value(config, "paths.results_dir", "data/results"))
    result_dir = os.path.join(results_root, os.path.splitext(os.path.basename(video_path))[0])
    video_info = _load_json(os.path.join(result_dir, "video_info.json"))
    poses = _load_json(os.path.join(result_dir, "poses", "person_poses.json"))
    behaviors = _load_json(os.path.join(result_dir, "behaviors", "behavior_segments.json"))
    performance = _load_json(os.path.join(result_dir, "performance.json"))
    job = _load_json(os.path.join(results_root, ".jobs", f"{video_id}.json"))
    checks = {
        "video_file": os.path.isfile(video_path),
        "video_info_matches": isinstance(video_info, dict) and os.path.normcase(os.path.abspath(str(video_info.get("path", "")))) == os.path.normcase(video_path),
        "pose_records": isinstance(poses, list) and len(poses) > 0,
        "behavior_segments": isinstance(behaviors, list) and len(behaviors) > 0,
        "persons_imported": int(counts[0]) > 0,
        "behaviors_imported": int(counts[1]) > 0,
        "performance_recorded": isinstance(performance, dict) and performance.get("processed_frames", 0) > 0,
    }
    if job is not None:
        checks["job_completed"] = job.get("status") == "completed"
    return {
        "video_id": video_id,
        "video_path": video_path,
        "result_dir": result_dir,
        "database_counts": {"persons": int(counts[0]), "behaviors": int(counts[1]), "anomalies": int(counts[2])},
        "job_status": job.get("status") if isinstance(job, dict) else None,
        "job_error": job.get("error") if isinstance(job, dict) else None,
        "performance": performance,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="只读检查一个视频的分析和入库结果")
    parser.add_argument("--video-id", type=int, required=True)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    report = verify(args.video_id, args.config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
