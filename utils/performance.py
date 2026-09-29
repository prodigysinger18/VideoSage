"""性能统计与 JSON 保存工具。"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class PerformanceRecorder:
    """记录每帧处理耗时、并发跟踪人数与 GPU 显存采样。"""

    def __init__(
        self,
        warmup_frames: int = 10,
        gpu_sample_interval: int = 30,
    ) -> None:
        self.warmup_frames = max(0, int(warmup_frames))
        self.gpu_sample_interval = max(1, int(gpu_sample_interval))

        self.frame_times_ms: List[float] = []
        self.detection_times_ms: List[float] = []
        self.tracking_times_ms: List[float] = []
        self.pose_times_ms: List[float] = []
        self.behavior_times_ms: List[float] = []
        self.outfit_times_ms: List[float] = []
        self.concurrent_track_counts: List[int] = []
        self.gpu_samples: List[Dict[str, float]] = []
        self.processed_frames = 0
        self.started_at = time.perf_counter()

    def record_frame(
        self,
        total_seconds: float,
        detection_seconds: float = 0.0,
        tracking_seconds: float = 0.0,
        pose_seconds: float = 0.0,
        behavior_seconds: float = 0.0,
        outfit_seconds: float = 0.0,
    ) -> None:
        """记录单帧处理耗时。"""
        self.processed_frames += 1
        self.frame_times_ms.append(float(total_seconds) * 1000.0)
        self.detection_times_ms.append(float(detection_seconds) * 1000.0)
        self.tracking_times_ms.append(float(tracking_seconds) * 1000.0)
        self.pose_times_ms.append(float(pose_seconds) * 1000.0)
        self.behavior_times_ms.append(float(behavior_seconds) * 1000.0)
        self.outfit_times_ms.append(float(outfit_seconds) * 1000.0)

    def record_track_count(self, count: int) -> None:
        """记录当前帧激活的跟踪目标数。"""
        self.concurrent_track_counts.append(max(0, int(count)))

    def sample_gpu(self, device: Any = 0) -> None:
        """采样当前 PyTorch GPU 显存占用。"""
        try:
            import torch

            if not torch.cuda.is_available():
                return
            allocated_mb = torch.cuda.memory_allocated(device) / 1024 ** 2
            reserved_mb = torch.cuda.memory_reserved(device) / 1024 ** 2
            self.gpu_samples.append(
                {
                    "allocated_mb": round(float(allocated_mb), 2),
                    "reserved_mb": round(float(reserved_mb), 2),
                }
            )
        except Exception:
            return

    def summary(self) -> Dict[str, Any]:
        """汇总性能指标。"""
        times = self.frame_times_ms[self.warmup_frames :]
        if not times and self.frame_times_ms:
            times = self.frame_times_ms

        detection_times = self.detection_times_ms[self.warmup_frames :]
        tracking_times = self.tracking_times_ms[self.warmup_frames :]
        pose_times = self.pose_times_ms[self.warmup_frames :]
        behavior_times = self.behavior_times_ms[self.warmup_frames :]
        outfit_times = self.outfit_times_ms[self.warmup_frames :]
        if not detection_times and self.detection_times_ms:
            detection_times = self.detection_times_ms
        if not tracking_times and self.tracking_times_ms:
            tracking_times = self.tracking_times_ms
        if not pose_times and self.pose_times_ms:
            pose_times = self.pose_times_ms
        if not behavior_times and self.behavior_times_ms:
            behavior_times = self.behavior_times_ms
        if not outfit_times and self.outfit_times_ms:
            outfit_times = self.outfit_times_ms

        sorted_times = sorted(times)
        p50 = _percentile(sorted_times, 0.50)
        p95 = _percentile(sorted_times, 0.95)

        avg_frame_time_ms = sum(times) / len(times) if times else 0.0
        avg_detection_time_ms = (
            sum(detection_times) / len(detection_times) if detection_times else 0.0
        )
        avg_tracking_time_ms = (
            sum(tracking_times) / len(tracking_times) if tracking_times else 0.0
        )
        avg_pose_time_ms = (
            sum(pose_times) / len(pose_times) if pose_times else 0.0
        )
        avg_behavior_time_ms = sum(behavior_times) / len(behavior_times) if behavior_times else 0.0
        avg_outfit_time_ms = sum(outfit_times) / len(outfit_times) if outfit_times else 0.0

        gpu_allocated_mb = max(
            (sample["allocated_mb"] for sample in self.gpu_samples), default=0.0
        )
        gpu_reserved_mb = max(
            (sample["reserved_mb"] for sample in self.gpu_samples), default=0.0
        )

        elapsed_seconds = time.perf_counter() - self.started_at
        wall_fps = self.processed_frames / elapsed_seconds if elapsed_seconds > 0 else 0.0

        return {
            "processed_frames": self.processed_frames,
            "warmup_frames": self.warmup_frames,
            "avg_fps": round(1000.0 / avg_frame_time_ms, 2) if avg_frame_time_ms > 0 else 0.0,
            "wall_fps": round(wall_fps, 2),
            "total_processing_seconds": round(elapsed_seconds, 2),
            "avg_frame_time_ms": round(avg_frame_time_ms, 2),
            "p50_frame_time_ms": round(p50, 2),
            "p95_frame_time_ms": round(p95, 2),
            "avg_detection_time_ms": round(avg_detection_time_ms, 2),
            "avg_tracking_time_ms": round(avg_tracking_time_ms, 2),
            "avg_pose_time_ms": round(avg_pose_time_ms, 2),
            "avg_behavior_time_ms": round(avg_behavior_time_ms, 2),
            "avg_outfit_time_ms": round(avg_outfit_time_ms, 2),
            "max_simultaneous_tracks": (
                max(self.concurrent_track_counts) if self.concurrent_track_counts else 0
            ),
            "gpu_allocated_mb": round(gpu_allocated_mb, 2),
            "gpu_reserved_mb": round(gpu_reserved_mb, 2),
        }


def _percentile(sorted_values: List[float], ratio: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, int(len(sorted_values) * ratio)))
    return float(sorted_values[index])


def save_json(path: str, data: Any) -> None:
    """保存 JSON 文件, 自动创建父目录。"""
    absolute_path = os.path.abspath(path)
    parent_dir = os.path.dirname(absolute_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(absolute_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
