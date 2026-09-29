"""将分析结果转换为中文字段的 JSON 友好结构。"""

from __future__ import annotations

from typing import Any


KEY_TRANSLATIONS = {
    "person_id": "人物ID",
    "track_id": "轨迹ID",
    "frame_id": "帧编号",
    "timestamp": "时间戳",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "action": "行为",
    "event": "异常事件",
    "severity": "严重级别",
    "confidence": "置信度",
    "identity_confidence": "身份置信度",
    "bbox": "人物框",
    "keypoints": "关键点",
    "features": "姿态特征",
    "person_center": "人物中心",
    "person_center_frame_norm": "人物中心帧归一化坐标",
    "shoulder_center": "肩部中心",
    "hip_center": "髋部中心",
    "hip_center_norm": "髋部归一化坐标",
    "left_knee_angle": "左膝角度",
    "right_knee_angle": "右膝角度",
    "torso_angle": "躯干角度",
    "left_ankle": "左脚踝",
    "right_ankle": "右脚踝",
    "left_ankle_frame_norm": "左脚踝帧归一化坐标",
    "right_ankle_frame_norm": "右脚踝帧归一化坐标",
    "bbox_height": "人物框高度",
    "bbox_width": "人物框宽度",
    "bbox_height_norm": "人物框归一化高度",
    "bbox_width_norm": "人物框归一化宽度",
    "keypoint_visible_ratio": "关键点可见比例",
    "keypoint_mean_confidence": "关键点平均置信度",
    "upper": "上衣",
    "lower": "下装",
    "sleeve": "袖长",
    "color": "颜色",
    "type": "类型",
    "length": "长度",
    "sample_count": "有效样本数",
    "path": "路径",
    "fps": "视频帧率",
    "width": "宽度",
    "height": "高度",
    "frame_count": "总帧数",
    "duration_sec": "视频时长秒",
    "fourcc": "视频编码",
    "processed_frames": "处理帧数",
    "warmup_frames": "预热帧数",
    "avg_fps": "平均处理帧率",
    "wall_fps": "总体帧率",
    "total_processing_seconds": "总处理时间秒",
    "avg_frame_time_ms": "平均单帧耗时毫秒",
    "p50_frame_time_ms": "P50单帧耗时毫秒",
    "p95_frame_time_ms": "P95单帧耗时毫秒",
    "avg_detection_time_ms": "平均检测耗时毫秒",
    "avg_tracking_time_ms": "平均跟踪耗时毫秒",
    "avg_pose_time_ms": "平均姿态耗时毫秒",
    "avg_behavior_time_ms": "平均行为分析耗时毫秒",
    "avg_outfit_time_ms": "平均穿搭分析耗时毫秒",
    "max_simultaneous_tracks": "最大同时跟踪人数",
    "gpu_allocated_mb": "GPU已分配显存MB",
    "gpu_reserved_mb": "GPU保留显存MB",
    "video_dir": "视频目录",
    "total_videos": "视频总数",
    "successful_videos": "成功视频数",
    "failed_videos": "失败视频数",
    "total_elapsed_seconds": "总耗时秒",
    "videos": "视频列表",
    "video_path": "视频路径",
    "status": "状态",
    "elapsed_seconds": "耗时秒",
    "result_dir": "结果目录",
    "performance": "性能",
    "error_type": "错误类型",
    "error": "错误信息",
}

VALUE_TRANSLATIONS = {
    "standing": "站立",
    "walking": "行走",
    "sitting": "坐下",
    "unknown": "未知",
    "fall": "摔倒",
    "lying": "躺卧",
    "running": "奔跑",
    "sudden_down": "突然倒下",
    "long_stationary": "长时间静止",
    "abnormal_movement": "异常移动",
    "long_sleeve": "长袖",
    "short_sleeve": "短袖",
    "long_sleeve_top": "长袖上衣",
    "short_sleeve_top": "短袖上衣",
    "long": "长款",
    "short": "短款",
    "pants": "长裤",
    "shorts": "短裤",
    "skirt": "裙子",
    "black": "黑色",
    "white": "白色",
    "gray": "灰色",
    "red": "红色",
    "orange": "橙色",
    "yellow": "黄色",
    "green": "绿色",
    "blue": "蓝色",
    "purple": "紫色",
    "pink": "粉色",
    "success": "成功",
    "failed": "失败",
    "high": "高",
    "warning": "警告",
    "normal": "普通",
}


def localize_json(data: Any) -> Any:
    """递归翻译已知字段名和枚举值。"""
    if isinstance(data, dict):
        return {
            KEY_TRANSLATIONS.get(str(key), str(key)): localize_json(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [localize_json(item) for item in data]
    if isinstance(data, tuple):
        return [localize_json(item) for item in data]
    if isinstance(data, str):
        return VALUE_TRANSLATIONS.get(data, data)
    return data
