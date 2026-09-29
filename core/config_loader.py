"""配置加载模块。

规范: agent.md 第 7 节要求禁止硬编码模型路径 / 参数 / 文件路径, 统一由 config.yaml 提供。
本模块负责:
    1. 读取 config.yaml 并与内置默认值深度合并, 保证缺省字段不会导致崩溃;
    2. 提供点号取值、路径解析工具。

用法:
    from utils.config_loader import load_config, get_value, resolve_path

    config = load_config("config.yaml")
    imgsz = get_value(config, "detection.imgsz", 640)
    model_path = resolve_path(config, get_value(config, "paths.model_path"))
"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG_PATH = "config.yaml"

# 内置默认值: 与 config.yaml 结构保持一致, 缺失字段回退到这里
DEFAULT_CONFIG: Dict[str, Any] = {
    "project": {
        "name": "VideoSage",
        "stage": 2,
    },
    "logging": {"level": "INFO"},
    "security": {"api_key": ""},
    "paths": {
        "model_path": "models/yolo11n.pt",
        "pose_model_path": "models/yolo/yolo11n-pose.pt",
        "video_dir": "data/videos",
        "video_path": None,
        "results_dir": "data/results",
        "tracks_file": "data/results/tracks.json",
        "performance_file": "data/results/performance.json",
        "annotated_video_dir": "data/results/videos",
        "pose_results_file": "data/results/poses/person_poses.json",
        "behavior_results_file": "data/results/behaviors/behavior_segments.json",
        "outfit_results_file": "data/results/appearance/outfit_profiles.json",
        "anomaly_results_file": "data/results/behaviors/anomaly_segments.json",
        "activity_results_file": "data/results/behaviors/activity_segments.json",
    },
    "video": {
        "frame_start": 0,
        "frame_stride": 1,
        "max_frames": 0,
    },
    "detection": {
        "conf_threshold": 0.3,
        "iou_threshold": 0.6,
        "imgsz": 640,
        "max_det": 100,
        "device": 0,
        "quantize": 16,
        "classes": [0],
        "class_names": {0: "person"},
    },
    "tracking": {
        "track_high_thresh": 0.5,
        "track_low_thresh": 0.1,
        "new_track_thresh": 0.5,
        "min_hits": 2,
        "track_buffer": 120,
        "match_thresh": 0.8,
        "second_match_thresh": 0.5,
        "unconfirmed_match_thresh": 0.7,
        "min_box_area": 400,
        "min_box_area_ratio": 0.001,
        "fuse_score": True,
        "kalman": {
            "std_weight_position": 0.05,
            "std_weight_velocity": 0.00625,
        },
        "frame_rate": None,
    },
    "identity": {
        "max_persons": 0,
        "appearance_weight": 0.75,
        "position_weight": 0.2,
        "size_weight": 0.05,
        "appearance_match_threshold": 0.4,
        "appearance_match_margin": 0.02,
        "reid_feature_weight": 0.65,
        "global_merge_threshold": 0.4,
        "position_time_window": 2.0,
        "template_update_alpha": 0.05,
        "template_update_min_confidence": 0.45,
        "confirmation_frames": 5,
        "min_pending_features": 3,
        "pending_ttl_seconds": 3.0,
        "reid_model_path": "models/reid/person_reid_youtu_2021nov.onnx",
        "reid_input_width": 128,
        "reid_input_height": 256,
        "reid_use_cuda": True,
        "max_appearance_templates": 8,
        "reid_update_interval": 15,
    },
    "visualization": {
        "box_thickness": 2,
        "text_thickness": 2,
        "font_scale": 0.7,
        "box_color": [0, 255, 0],
        "text_color": [255, 255, 255],
        "use_id_color": True,
    },
    "output": {
        "show_window": True,
        "save_annotated_video": True,
        "draw_confidence": True,
        "window_name": "VideoSage - Person Tracking",
    },
    "performance": {
        "warmup_frames": 10,
        "gpu_sample_interval": 30,
    },
    "pose": {
        "conf_threshold": 0.25,
        "iou_threshold": 0.7,
        "imgsz": 640,
        "max_det": 1,
        "device": 0,
        "quantize": 16,
        "keypoint_conf_threshold": 0.3,
    },
    "action": {
        "smoothing_window_size": 7,
        "switch_confirmations": 3,
        "walking_window_size": 10,
        "min_segment_seconds": 0.5,
        "standing_knee_angle_thresh": 140,
        "standing_torso_angle_thresh": 20,
        "standing_max_center_displacement": 0.08,
        "standing_max_ankle_motion": 0.06,
        "sitting_knee_angle_thresh": 110,
        "walking_min_center_displacement": 0.25,
        "walking_min_ankle_motion": 0.12,
        "min_keypoint_visible_ratio": 0.35,
        "min_keypoint_confidence": 0.28,
    },
    "appearance": {
        "sample_interval_frames": 15,
        "min_keypoint_confidence": 0.3,
    },
    "anomaly": {
        "window_seconds": 2.0,
        "running_speed_threshold": 0.8,
        "sudden_down_threshold": 0.25,
        "lying_aspect_ratio": 1.15,
        "lying_torso_angle": 55.0,
        "stationary_seconds": 10.0,
        "stationary_displacement": 0.08,
        "abnormal_speed_threshold": 1.8,
        "confirmation_frames": 3,
        "abnormal_max_seconds": 2.0,
        "movement_deadzone": 0.03,
        "direction_confirmation_frames": 2,
        "abnormal_path_ratio": 2.5,
        "abnormal_min_path": 0.25,
        "scene_cut_displacement": 0.8,
        "scene_cut_size_change": 0.35,
        "abnormal_cooldown_seconds": 1.0,
        "fall_min_vertical_drop": 0.2,
        "fall_min_vertical_speed": 0.08,
        "fall_window_seconds": 1.0,
        "fall_active_seconds": 0.6,
        "max_gap_seconds": 0.3,
        "min_duration_seconds": 0.3,
        "related_event_gap_seconds": 1.0,
    },
    "database": {
        "enabled": True,
        "driver": "ODBC Driver 17 for SQL Server",
        "server": "localhost",
        "database": "VideoSageDB",
        "username": "",
        "password": "",
    },
    "llm": {
        "enabled": False,
        "api_key": "",
        "base_url": "",
        "model": "",
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并字典, override 中的值覆盖 base, 不修改入参。"""
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件。

    Args:
        config_path: 配置文件路径, 为 None 时使用项目根目录的 config.yaml。

    Returns:
        合并内置默认值后的配置字典, 额外附带:
            "_config_path": 配置文件绝对路径
            "_project_root": 项目根目录(配置文件所在目录), 用于解析相对路径
    """
    path = os.path.abspath(config_path or DEFAULT_CONFIG_PATH)

    file_config: Dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            file_config = yaml.safe_load(handle) or {}
        if not isinstance(file_config, dict):
            raise ValueError(f"配置文件格式错误, 顶层必须是字典: {path}")

    config = deep_merge(DEFAULT_CONFIG, file_config)
    config["_config_path"] = path
    config["_project_root"] = os.path.dirname(path)
    return config


def get_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """按点号路径读取配置, 例如 get_value(config, "detection.imgsz")。"""
    node: Any = config
    for key in key_path.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return default if node is None else node


def get_section(config: Dict[str, Any], section: str) -> Dict[str, Any]:
    """读取配置中的整个 section, 缺失时返回空字典。"""
    section_value = config.get(section)
    return section_value if isinstance(section_value, dict) else {}


def resolve_path(config: Dict[str, Any], path: Optional[str]) -> Optional[str]:
    """把配置中的相对路径解析为绝对路径(基准为项目根目录)。"""
    if not path:
        return None
    if os.path.isabs(path):
        return os.path.abspath(path)
    root = config.get("_project_root") or os.getcwd()
    return os.path.abspath(os.path.join(root, path))
