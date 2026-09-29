"""多视频稳定性测试入口。"""

from __future__ import annotations

import os
import time
import traceback
from typing import Any, Dict, Optional

from pipeline.analysis_pipeline import run_analysis_pipeline
from utils.config_loader import get_value, load_config, resolve_path
from utils.performance import save_json
from utils.json_localizer import localize_json
from video_processing.video_reader import VideoReader


def run_batch_analysis(
    video_dir: Optional[str] = None,
    config_path: str = "config.yaml",
    max_frames: Optional[int] = None,
) -> Dict[str, Any]:
    """顺序分析目录内全部视频，单个失败不终止整个批次。"""
    config = load_config(config_path)
    source_dir = video_dir or get_value(config, "paths.video_dir", "data/videos")
    source_dir = resolve_path(config, source_dir)
    if not os.path.isdir(source_dir):
        raise NotADirectoryError(f"视频目录不存在: {source_dir}")

    videos = [
        os.path.join(source_dir, name)
        for name in sorted(os.listdir(source_dir))
        if os.path.isfile(os.path.join(source_dir, name))
        and os.path.splitext(name)[1].lower() in VideoReader.SUPPORTED_EXTENSIONS
    ]
    if not videos:
        raise FileNotFoundError(f"视频目录中没有支持的视频文件: {source_dir}")

    batch_started = time.perf_counter()
    items = []
    for index, video_path in enumerate(videos, start=1):
        print(f"[Batch] {index}/{len(videos)} 开始: {video_path}")
        started = time.perf_counter()
        try:
            result = run_analysis_pipeline(config_path, video_path, max_frames)
            items.append(
                {
                    "video_path": os.path.abspath(video_path),
                    "status": "success",
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                    "result_dir": result.get("result_dir"),
                    "performance": result.get("performance", {}),
                }
            )
        except Exception as exc:
            items.append(
                {
                    "video_path": os.path.abspath(video_path),
                    "status": "failed",
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            print(f"[Batch] 失败: {video_path}: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    summary = {
        "video_dir": os.path.abspath(source_dir),
        "total_videos": len(videos),
        "successful_videos": sum(item["status"] == "success" for item in items),
        "failed_videos": sum(item["status"] == "failed" for item in items),
        "total_elapsed_seconds": round(time.perf_counter() - batch_started, 2),
        "videos": items,
    }
    results_root = resolve_path(config, get_value(config, "paths.results_dir", "data/results"))
    summary_file = os.path.join(results_root, "batch_summary.json")
    save_json(summary_file, summary)
    save_json(os.path.join(results_root, "batch_summary_zh.json"), localize_json(summary))
    print(f"[Batch] 汇总: {summary_file}")
    return summary
