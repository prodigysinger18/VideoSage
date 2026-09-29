"""按输入视频组织分析结果目录。"""

from __future__ import annotations

import os
import re
from typing import Dict


def create_video_result_paths(video_path: str, results_root: str) -> Dict[str, str]:
    """创建 ``results/{video_name}`` 目录并返回各结果文件路径。"""
    video_name = _safe_video_name(video_path)
    result_dir = os.path.abspath(os.path.join(results_root, video_name))
    poses_dir = os.path.join(result_dir, "poses")
    behaviors_dir = os.path.join(result_dir, "behaviors")
    appearance_dir = os.path.join(result_dir, "appearance")

    for directory in (result_dir, poses_dir, behaviors_dir, appearance_dir):
        os.makedirs(directory, exist_ok=True)

    return {
        "result_dir": result_dir,
        "video_info_file": os.path.join(result_dir, "video_info.json"),
        "video_info_zh_file": os.path.join(result_dir, "video_info_zh.json"),
        "performance_file": os.path.join(result_dir, "performance.json"),
        "performance_zh_file": os.path.join(result_dir, "performance_zh.json"),
        "pose_results_file": os.path.join(poses_dir, "person_poses.json"),
        "pose_results_zh_file": os.path.join(poses_dir, "person_poses_zh.json"),
        "behavior_results_file": os.path.join(behaviors_dir, "behavior_segments.json"),
        "behavior_results_zh_file": os.path.join(behaviors_dir, "behavior_segments_zh.json"),
        "anomaly_results_file": os.path.join(behaviors_dir, "anomaly_segments.json"),
        "anomaly_results_zh_file": os.path.join(behaviors_dir, "anomaly_segments_zh.json"),
        "activity_results_file": os.path.join(behaviors_dir, "activity_segments.json"),
        "activity_results_zh_file": os.path.join(behaviors_dir, "activity_segments_zh.json"),
        "outfit_results_file": os.path.join(appearance_dir, "outfit_profiles.json"),
        "outfit_results_zh_file": os.path.join(appearance_dir, "outfit_profiles_zh.json"),
    }


def _safe_video_name(video_path: str) -> str:
    stem = os.path.splitext(os.path.basename(os.path.abspath(video_path)))[0].strip()
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).rstrip(". ")
    return safe_name or "video"
