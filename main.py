"""VideoSage command-line entry point."""

from __future__ import annotations

import argparse
import sys


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="VideoSage 视频分析")
    parser.add_argument("--analysis", action="store_true", help="运行 Stage 2 姿态与行为分析")
    parser.add_argument("--batch", action="store_true", help="分析目录中的全部视频")
    parser.add_argument("--video", default=None, help="视频文件或视频目录")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--max-frames", type=int, default=None, help="最多处理帧数")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.batch:
        from pipeline.batch_analysis import run_batch_analysis

        summary = run_batch_analysis(args.video, args.config, args.max_frames)
        return 0 if summary["failed_videos"] == 0 else 1

    if args.analysis:
        from pipeline.analysis_pipeline import run_analysis_pipeline

        run_analysis_pipeline(args.config, args.video, args.max_frames)
        return 0

    import cv2
    from detection.yolo_detector import YOLODetector
    from tracking.bytetrack_tracker import ByteTrackTracker
    from video_processing.video_reader import VideoReader

    video = VideoReader(args.video or "data/videos", max_frames=args.max_frames or 0)
    detector = YOLODetector()
    tracker = ByteTrackTracker()
    try:
        for frame in video.read():
            detections = detector.detect(frame)
            tracker.update(detections, frame=frame)
            cv2.imshow("VideoSage", frame)
            if cv2.waitKey(1) == 27:
                break
    finally:
        video.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
