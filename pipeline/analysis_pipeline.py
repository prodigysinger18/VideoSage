"""第二阶段分析流程编排。

流程:
    VideoReader -> YOLODetector -> ByteTrackTracker -> YOLOPose
    -> PoseFeatures -> ActionAnalyzer -> BehaviorSmoother
    -> BehaviorSegmentBuilder -> JSON 保存

本模块只负责编排, 不把行为规则塞进 Pipeline。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from analysis.action.action_analyzer import ActionAnalyzer
from analysis.action.anomaly_analyzer import AnomalyAnalyzer, AnomalySegmentBuilder
from analysis.action.activity_segment import merge_activity_segments
from analysis.action.behavior_segment import BehaviorSegmentBuilder
from analysis.action.behavior_smoother import BehaviorSmoother
from analysis.action.behavior_state import BehaviorStateManager
from analysis.pose.pose_estimator import PoseEstimator
from analysis.pose.pose_features import extract_features
from analysis.appearance.outfit_analyzer import OutfitAnalyzer
from detection.yolo_detector import YOLODetector
from detection.yolo_pose import YOLOPose
from tracking.bytetrack_tracker import ByteTrackTracker
from tracking.identity_manager import IdentityManager
from utils.config_loader import get_section, get_value, load_config, resolve_path
from utils.performance import PerformanceRecorder, save_json
from utils.json_localizer import localize_json
from utils.result_manager import create_video_result_paths
from video_processing.video_reader import VideoReader


def _resolve_video_source(config: Dict[str, Any], cli_video: Optional[str]) -> str:
    if cli_video:
        return resolve_path(config, cli_video)

    configured_video = get_value(config, "paths.video_path")
    if configured_video:
        return resolve_path(config, configured_video)

    video_dir = get_value(config, "paths.video_dir", "data/videos")
    return resolve_path(config, video_dir)


def run_analysis_pipeline(
    config_path: str = "config.yaml",
    video_path: Optional[str] = None,
    max_frames: Optional[int] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """运行第二阶段姿态与基础行为分析。"""
    config = load_config(config_path)

    video_config = get_section(config, "video")
    detection_config = get_section(config, "detection")
    tracking_config = get_section(config, "tracking")
    identity_config = get_section(config, "identity")
    pose_config = get_section(config, "pose")
    action_config = get_section(config, "action")
    appearance_config = get_section(config, "appearance")
    anomaly_config = get_section(config, "anomaly")
    performance_config = get_section(config, "performance")

    video_source = _resolve_video_source(config, video_path)
    reader = VideoReader(
        video_path=video_source,
        frame_start=int(video_config.get("frame_start", 0)),
        frame_stride=int(video_config.get("frame_stride", 1)),
        max_frames=max_frames if max_frames is not None else int(video_config.get("max_frames", 0)),
    )

    video_info = reader.get_info()
    results_root = resolve_path(config, get_value(config, "paths.results_dir", "data/results"))
    result_paths = create_video_result_paths(video_info["path"], results_root)
    print("=" * 70)
    print("第二阶段分析视频信息")
    print("=" * 70)
    for key in ("path", "fps", "width", "height", "frame_count", "duration_sec"):
        print(f"  {key:<12}: {video_info.get(key)}")

    detection_model_path = resolve_path(config, get_value(config, "paths.model_path"))
    detector = YOLODetector(
        model_path=detection_model_path,
        conf_threshold=float(detection_config.get("conf_threshold", 0.25)),
        iou_threshold=float(detection_config.get("iou_threshold", 0.7)),
        imgsz=int(detection_config.get("imgsz", 640)),
        max_det=int(detection_config.get("max_det", 300)),
        device=detection_config.get("device", 0),
        quantize=detection_config.get("quantize", 16),
        classes=detection_config.get("classes", [0]),
        class_names=detection_config.get("class_names", {0: "person"}),
    )

    tracker = ByteTrackTracker(
        track_high_thresh=float(tracking_config.get("track_high_thresh", 0.5)),
        track_low_thresh=float(tracking_config.get("track_low_thresh", 0.1)),
        new_track_thresh=float(tracking_config.get("new_track_thresh", 0.6)),
        track_buffer=int(tracking_config.get("track_buffer", 30)),
        min_hits=int(tracking_config.get("min_hits", 2)),
        match_thresh=float(tracking_config.get("match_thresh", 0.8)),
        second_match_thresh=float(tracking_config.get("second_match_thresh", 0.5)),
        unconfirmed_match_thresh=float(tracking_config.get("unconfirmed_match_thresh", 0.7)),
        min_box_area=float(tracking_config.get("min_box_area", 400.0)),
        min_box_area_ratio=float(tracking_config.get("min_box_area_ratio", 0.001)),
        fuse_score=bool(tracking_config.get("fuse_score", True)),
        std_weight_position=float(tracking_config.get("kalman", {}).get("std_weight_position", 0.05)),
        std_weight_velocity=float(tracking_config.get("kalman", {}).get("std_weight_velocity", 0.00625)),
        frame_rate=tracking_config.get("frame_rate") or video_info.get("fps"),
    )
    identity_manager = IdentityManager(
        max_persons=int(identity_config.get("max_persons", 0)),
        appearance_weight=float(identity_config.get("appearance_weight", 0.75)),
        position_weight=float(identity_config.get("position_weight", 0.2)),
        size_weight=float(identity_config.get("size_weight", 0.05)),
        appearance_match_threshold=float(
            identity_config.get("appearance_match_threshold", 0.62)
        ),
        position_time_window=float(identity_config.get("position_time_window", 1.0)),
        template_update_alpha=float(identity_config.get("template_update_alpha", 0.05)),
        template_update_min_confidence=float(
            identity_config.get("template_update_min_confidence", 0.45)
        ),
        confirmation_frames=int(identity_config.get("confirmation_frames", 5)),
        pending_ttl_seconds=float(identity_config.get("pending_ttl_seconds", 2.0)),
        reid_model_path=resolve_path(config, identity_config.get("reid_model_path")),
        reid_input_width=int(identity_config.get("reid_input_width", 128)),
        reid_input_height=int(identity_config.get("reid_input_height", 256)),
        reid_use_cuda=bool(identity_config.get("reid_use_cuda", True)),
        max_appearance_templates=int(
            identity_config.get("max_appearance_templates", 8)
        ),
        reid_update_interval=int(identity_config.get("reid_update_interval", 15)),
        appearance_match_margin=float(
            identity_config.get("appearance_match_margin", 0.04)
        ),
        min_pending_features=int(identity_config.get("min_pending_features", 3)),
        reid_feature_weight=float(identity_config.get("reid_feature_weight", 0.65)),
        global_merge_threshold=float(
            identity_config.get("global_merge_threshold", 0.42)
        ),
    )
    if identity_manager.reid_extractor.available:
        print(f"  ReID model   : {identity_config.get('reid_model_path')}")
    else:
        print("  ReID model   : unavailable, using HSV appearance fallback")

    pose_model_path = resolve_path(config, get_value(config, "paths.pose_model_path"))
    pose_model = YOLOPose(
        model_path=pose_model_path,
        conf_threshold=float(pose_config.get("conf_threshold", 0.25)),
        iou_threshold=float(pose_config.get("iou_threshold", 0.7)),
        imgsz=int(pose_config.get("imgsz", 640)),
        max_det=int(pose_config.get("max_det", 1)),
        device=pose_config.get("device", 0),
        quantize=pose_config.get("quantize", 16),
    )
    pose_estimator = PoseEstimator(
        pose_model=pose_model,
        keypoint_conf_threshold=float(pose_config.get("keypoint_conf_threshold", 0.3)),
    )

    action_analyzer = ActionAnalyzer(
        walking_window_size=int(action_config.get("walking_window_size", 10)),
        standing_knee_angle_thresh=float(action_config.get("standing_knee_angle_thresh", 140)),
        standing_torso_angle_thresh=float(action_config.get("standing_torso_angle_thresh", 20)),
        standing_max_center_displacement=float(action_config.get("standing_max_center_displacement", 0.08)),
        standing_max_ankle_motion=float(action_config.get("standing_max_ankle_motion", 0.06)),
        sitting_knee_angle_thresh=float(action_config.get("sitting_knee_angle_thresh", 110)),
        walking_min_center_displacement=float(action_config.get("walking_min_center_displacement", 0.25)),
        walking_min_ankle_motion=float(action_config.get("walking_min_ankle_motion", 0.12)),
        min_keypoint_visible_ratio=float(action_config.get("min_keypoint_visible_ratio", 0.35)),
        min_keypoint_confidence=float(action_config.get("min_keypoint_confidence", 0.28)),
    )
    smoother = BehaviorSmoother(
        window_size=int(action_config.get("smoothing_window_size", 7)),
        switch_confirmations=int(action_config.get("switch_confirmations", 3)),
    )
    state_manager = BehaviorStateManager()
    segment_builder = BehaviorSegmentBuilder(
        min_segment_seconds=float(action_config.get("min_segment_seconds", 0.5))
    )
    outfit_analyzer = OutfitAnalyzer(
        sample_interval_frames=int(appearance_config.get("sample_interval_frames", 15)),
        min_keypoint_conf=float(appearance_config.get("min_keypoint_confidence", 0.3)),
    )
    anomaly_analyzer = AnomalyAnalyzer(
        window_seconds=float(anomaly_config.get("window_seconds", 2.0)),
        running_speed_threshold=float(anomaly_config.get("running_speed_threshold", 0.8)),
        sudden_down_threshold=float(anomaly_config.get("sudden_down_threshold", 0.25)),
        lying_aspect_ratio=float(anomaly_config.get("lying_aspect_ratio", 1.15)),
        lying_torso_angle=float(anomaly_config.get("lying_torso_angle", 55.0)),
        stationary_seconds=float(anomaly_config.get("stationary_seconds", 10.0)),
        stationary_displacement=float(anomaly_config.get("stationary_displacement", 0.08)),
        abnormal_speed_threshold=float(anomaly_config.get("abnormal_speed_threshold", 1.8)),
        confirmation_frames=int(anomaly_config.get("confirmation_frames", 3)),
        abnormal_max_seconds=float(anomaly_config.get("abnormal_max_seconds", 2.0)),
        movement_deadzone=float(anomaly_config.get("movement_deadzone", 0.03)),
        direction_confirmation_frames=int(anomaly_config.get("direction_confirmation_frames", 2)),
        abnormal_path_ratio=float(anomaly_config.get("abnormal_path_ratio", 2.5)),
        abnormal_min_path=float(anomaly_config.get("abnormal_min_path", 0.25)),
        scene_cut_displacement=float(anomaly_config.get("scene_cut_displacement", 0.8)),
        scene_cut_size_change=float(anomaly_config.get("scene_cut_size_change", 0.35)),
        abnormal_cooldown_seconds=float(anomaly_config.get("abnormal_cooldown_seconds", 1.0)),
        fall_confirmation_frames=int(anomaly_config.get("fall_confirmation_frames", 4)),
        fall_min_vertical_drop=float(anomaly_config.get("fall_min_vertical_drop", 0.3)),
        fall_min_vertical_speed=float(anomaly_config.get("fall_min_vertical_speed", 0.18)),
        fall_upright_torso_angle=float(anomaly_config.get("fall_upright_torso_angle", 35.0)),
        fall_cooldown_seconds=float(anomaly_config.get("fall_cooldown_seconds", 2.5)),
        fall_window_seconds=float(anomaly_config.get("fall_window_seconds", 0.8)),
        fall_active_seconds=float(anomaly_config.get("fall_active_seconds", 0.6)),
    )
    anomaly_segments = AnomalySegmentBuilder(
        max_gap_seconds=float(anomaly_config.get("max_gap_seconds", 0.3)),
        min_duration_seconds=float(anomaly_config.get("min_duration_seconds", 0.3)),
        related_event_gap_seconds=float(anomaly_config.get("related_event_gap_seconds", 1.0)),
    )

    recorder = PerformanceRecorder(
        warmup_frames=int(performance_config.get("warmup_frames", 10)),
        gpu_sample_interval=int(performance_config.get("gpu_sample_interval", 30)),
    )

    pose_records = []
    progress_interval = max(1, int(video_info.get("frame_count", 1) // 20))
    frame_width = int(video_info.get("width", 0))
    frame_height = int(video_info.get("height", 0))

    try:
        for frame in reader.read():
            frame_id = reader.current_frame_id
            timestamp = reader.current_timestamp
            total_start = time.perf_counter()

            detection_start = time.perf_counter()
            detections = detector.detect(frame)
            detection_end = time.perf_counter()

            tracks = tracker.update(detections, frame=frame)
            tracks = identity_manager.update(frame, tracks, timestamp)
            tracking_end = time.perf_counter()

            pose_seconds_total = 0.0
            behavior_seconds_total = 0.0
            outfit_seconds_total = 0.0
            for track in tracks:
                pose_start = time.perf_counter()
                pose_result = pose_estimator.estimate(
                    frame=frame,
                    bbox=track.bbox,
                    person_id=track.person_id,
                    timestamp=timestamp,
                )
                pose_end = time.perf_counter()
                pose_seconds_total += pose_end - pose_start

                features_dict = {}
                if pose_result.get("keypoints"):
                    features = extract_features(
                        keypoints=pose_result["keypoints"],
                        bbox=pose_result.get("bbox", track.bbox),
                        frame_width=frame_width,
                        frame_height=frame_height,
                        keypoint_min_conf=float(pose_config.get("keypoint_conf_threshold", 0.3)),
                    )
                    features_dict = features.to_dict()

                    behavior_start = time.perf_counter()
                    raw_action = action_analyzer.analyze(
                        person_id=track.person_id,
                        timestamp=timestamp,
                        features=features,
                    )
                    smoothed = smoother.update(
                        person_id=track.person_id,
                        timestamp=timestamp,
                        action=raw_action["action"],
                        confidence=raw_action["confidence"],
                    )
                    state_manager.update(
                        person_id=track.person_id,
                        timestamp=timestamp,
                        action=smoothed["action"],
                        confidence=smoothed["confidence"],
                    )
                    segment_builder.add_observation(
                        person_id=track.person_id,
                        timestamp=timestamp,
                        action=smoothed["action"],
                        confidence=smoothed["confidence"],
                    )
                    for anomaly in anomaly_analyzer.analyze(
                        person_id=track.person_id,
                        timestamp=timestamp,
                        features=features,
                        base_action=smoothed["action"],
                    ):
                        anomaly_segments.add(anomaly)
                    behavior_seconds_total += time.perf_counter() - behavior_start

                    outfit_start = time.perf_counter()
                    outfit_analyzer.update(
                        frame=frame,
                        person_id=track.person_id,
                        frame_id=frame_id,
                        timestamp=timestamp,
                        bbox=pose_result.get("bbox", track.bbox),
                        keypoints=pose_result["keypoints"],
                        detection_confidence=min(
                            float(track.confidence),
                            float(pose_result.get("confidence", 0.0)),
                        ),
                    )
                    outfit_seconds_total += time.perf_counter() - outfit_start

                    pose_records.append(
                        {
                            "frame_id": frame_id,
                            "track_id": track.track_id,
                            "person_id": track.person_id,
                            "identity_confidence": track.get("identity_confidence", 0.0),
                            "timestamp": round(timestamp, 4),
                            "bbox": [round(float(value), 2) for value in pose_result.get("bbox", track.bbox)],
                            "confidence": round(float(pose_result.get("confidence", 0.0)), 4),
                            "keypoints": pose_result["keypoints"],
                            "features": features_dict,
                        }
                    )

            total_end = time.perf_counter()
            recorder.record_frame(
                total_seconds=total_end - total_start,
                detection_seconds=detection_end - detection_start,
                tracking_seconds=tracking_end - detection_end,
                pose_seconds=pose_seconds_total,
                behavior_seconds=behavior_seconds_total,
                outfit_seconds=outfit_seconds_total,
            )

            if frame_id % progress_interval == 0:
                print(f"[Analysis Progress] frame={frame_id}, active_tracks={len(tracks)}")
                if progress_callback is not None:
                    progress_callback(frame_id, int(video_info.get("frame_count", 0)), len(tracks))
    finally:
        reader.release()

    identity_map = identity_manager.build_global_identity_map()
    for record in pose_records:
        record["person_id"] = identity_map.get(record["person_id"], record["person_id"])
    segments = _remap_and_merge_segments(
        segment_builder.build_all(), identity_map, "action"
    )
    outfit_profiles = _remap_outfit_profiles(
        outfit_analyzer.build_profiles(), identity_map
    )
    anomaly_results = _remap_and_merge_segments(
        anomaly_segments.build_all(), identity_map, "event"
    )
    activity_results = merge_activity_segments(segments, anomaly_results)
    pose_results_file = result_paths["pose_results_file"]
    behavior_results_file = result_paths["behavior_results_file"]
    outfit_results_file = result_paths["outfit_results_file"]
    anomaly_results_file = result_paths["anomaly_results_file"]
    activity_results_file = result_paths["activity_results_file"]

    if not pose_records:
        raise RuntimeError(
            "Stage 2 未产生有效 Pose 结果, 不写入空 person_poses.json。"
            "请检查人物检测、跟踪结果和 Pose 模型输出。"
        )
    if not segments:
        raise RuntimeError(
            "Stage 2 未产生有效行为时间段, 不写入空 behavior_segments.json。"
            "请检查 Pose 关键点和行为分析配置。"
        )

    save_json(pose_results_file, pose_records)
    save_json(result_paths["pose_results_zh_file"], localize_json(pose_records))
    save_json(behavior_results_file, segments)
    save_json(result_paths["behavior_results_zh_file"], localize_json(segments))
    save_json(outfit_results_file, outfit_profiles)
    save_json(result_paths["outfit_results_zh_file"], localize_json(outfit_profiles))
    save_json(anomaly_results_file, anomaly_results)
    save_json(result_paths["anomaly_results_zh_file"], localize_json(anomaly_results))
    save_json(activity_results_file, activity_results)
    save_json(result_paths["activity_results_zh_file"], localize_json(activity_results))

    summary = recorder.summary()
    save_json(result_paths["video_info_file"], video_info)
    save_json(result_paths["video_info_zh_file"], localize_json(video_info))
    save_json(result_paths["performance_file"], summary)
    save_json(result_paths["performance_zh_file"], localize_json(summary))
    print("=" * 70)
    print("第二阶段分析完成")
    print("=" * 70)
    print(f"  person_poses.json      : {pose_results_file}")
    print(f"  behavior_segments.json : {behavior_results_file}")
    print(f"  outfit_profiles.json    : {outfit_results_file}")
    print(f"  anomaly_segments.json   : {anomaly_results_file}")
    print(f"  activity_segments.json  : {activity_results_file}")
    print(f"  result_dir              : {result_paths['result_dir']}")
    print(f"  处理帧数               : {summary['processed_frames']}")
    print(f"  Pose 平均耗时(ms)      : {summary['avg_pose_time_ms']}")
    print(f"  行为平均耗时(ms)       : {summary['avg_behavior_time_ms']}")
    print(f"  穿搭平均耗时(ms)       : {summary['avg_outfit_time_ms']}")
    print(f"  行为时间段数量         : {len(segments)}")

    return {
        "result_dir": result_paths["result_dir"],
        "video_info_file": result_paths["video_info_file"],
        "performance_file": result_paths["performance_file"],
        "pose_results_file": pose_results_file,
        "behavior_results_file": behavior_results_file,
        "outfit_results_file": outfit_results_file,
        "anomaly_results_file": anomaly_results_file,
        "activity_results_file": activity_results_file,
        "pose_record_count": len(pose_records),
        "behavior_segment_count": len(segments),
        "outfit_profile_count": len(outfit_profiles),
        "anomaly_segment_count": len(anomaly_results),
        "activity_segment_count": len(activity_results),
        "performance": summary,
    }


def _remap_and_merge_segments(records, identity_map, label_key):
    remapped = []
    for record in records:
        item = dict(record)
        item["person_id"] = identity_map.get(item["person_id"], item["person_id"])
        remapped.append(item)
    remapped.sort(key=lambda item: (item["person_id"], item[label_key], item["start_time"]))
    merged = []
    for item in remapped:
        if (
            merged
            and merged[-1]["person_id"] == item["person_id"]
            and merged[-1][label_key] == item[label_key]
            and item["start_time"] - merged[-1]["end_time"] <= 0.2
        ):
            merged[-1]["end_time"] = max(merged[-1]["end_time"], item["end_time"])
            merged[-1]["confidence"] = round(
                (merged[-1]["confidence"] + item["confidence"]) / 2.0, 4
            )
        else:
            merged.append(item)
    return sorted(merged, key=lambda item: (item["start_time"], item["person_id"]))


def _remap_outfit_profiles(profiles, identity_map):
    grouped = {}
    for profile in profiles:
        person_id = identity_map.get(profile["person_id"], profile["person_id"])
        current = grouped.get(person_id)
        if current is None or profile.get("sample_count", 0) > current.get("sample_count", 0):
            selected = dict(profile)
            selected["person_id"] = person_id
            if current is not None:
                selected["sample_count"] = selected.get("sample_count", 0) + current.get("sample_count", 0)
            grouped[person_id] = selected
        else:
            current["sample_count"] = current.get("sample_count", 0) + profile.get("sample_count", 0)
    return [grouped[person_id] for person_id in sorted(grouped)]


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="VideoSage 第二阶段分析")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--video", default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    raise SystemExit(0 if run_analysis_pipeline(args.config, args.video, args.max_frames) else 1)
