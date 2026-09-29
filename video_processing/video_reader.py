"""视频读取模块。

职责:
    1. 读取本地视频文件(默认支持 mp4 / avi / mov / mkv / webm / m4v);
    2. 提取 FPS、分辨率、总帧数、时长等基础信息;
    3. 按帧输出 frame, 同时暴露当前帧号与时间戳。

本模块只负责视频输入, 不包含检测、跟踪或结果存储逻辑。
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterator

import cv2


class VideoReader:
    """OpenCV 视频读取器。"""

    SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}

    def __init__(
        self,
        video_path: str,
        frame_start: int = 0,
        frame_stride: int = 1,
        max_frames: int = 0,
    ) -> None:
        """初始化视频读取器。

        Args:
            video_path: 视频文件路径; 也可以是目录, 此时自动选择目录中第一个支持的视频。
            frame_start: 起始帧(0 基, 包含)。
            frame_stride: 抽帧步长, 必须 >= 1。
            max_frames: 最多读取帧数, 0 表示不限制。
        """
        if not video_path:
            raise ValueError("video_path 不能为空")

        if os.path.isdir(video_path):
            video_path = self.find_video(video_path)

        self.video_path = os.path.abspath(video_path)
        if not os.path.isfile(self.video_path):
            raise FileNotFoundError(f"视频文件不存在: {self.video_path}")

        self.frame_start = max(0, int(frame_start))
        self.frame_stride = max(1, int(frame_stride))
        self.max_frames = max(0, int(max_frames))

        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频: {self.video_path}")

        self.current_frame_id = 0
        self.current_source_index = -1
        self.current_timestamp = 0.0

        self._info = self._read_info()
        self.fps = float(self._info["fps"])
        self.width = int(self._info["width"])
        self.height = int(self._info["height"])
        self.frame_count = int(self._info["frame_count"])

    @classmethod
    def find_video(cls, video_dir: str) -> str:
        """在目录中查找第一个受支持的视频文件。"""
        if not os.path.isdir(video_dir):
            raise NotADirectoryError(f"视频目录不存在: {video_dir}")

        for entry in sorted(os.listdir(video_dir)):
            file_path = os.path.join(video_dir, entry)
            if os.path.isfile(file_path) and os.path.splitext(entry)[1].lower() in cls.SUPPORTED_EXTENSIONS:
                return file_path

        raise FileNotFoundError(f"视频目录中没有找到受支持的视频文件: {video_dir}")

    def _read_info(self) -> Dict[str, Any]:
        """读取并规范化视频基础信息。"""
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(round(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0))
        height = int(round(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
        frame_count = int(round(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))

        if fps <= 0:
            fps = 0.0
        duration = frame_count / fps if fps > 0 else 0.0

        return {
            "path": self.video_path,
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "duration_sec": duration,
            "fourcc": int(self.cap.get(cv2.CAP_PROP_FOURCC) or 0),
        }

    def get_info(self) -> Dict[str, Any]:
        """返回视频基础信息。"""
        return dict(self._info)

    def read(self) -> Iterator[Any]:
        """逐帧读取视频。

        Yields:
            BGR frame。读取后可通过 ``current_frame_id`` 获取 1 基帧号,
            通过 ``current_timestamp`` 获取当前帧对应的视频时间(秒)。
        """
        self.current_frame_id = 0
        next_source_index = self.frame_start

        if self.frame_count > 0:
            next_source_index = min(next_source_index, self.frame_count - 1)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, next_source_index)

        while True:
            if self.max_frames > 0 and self.current_frame_id >= self.max_frames:
                break

            ret, frame = self.cap.read()
            if not ret:
                break

            self.current_frame_id += 1
            self.current_source_index = next_source_index
            self.current_timestamp = (
                next_source_index / self.fps if self.fps > 0 else 0.0
            )

            yield frame

            next_source_index += self.frame_stride
            if self.frame_stride > 1:
                if self.frame_count > 0 and next_source_index >= self.frame_count:
                    break
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, next_source_index)

    def release(self) -> None:
        """释放视频资源。"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.release()
