"""Run uploaded-video analysis and result import outside the request thread."""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

from core.config_loader import get_section, get_value, load_config, resolve_path
from database.result_importer import ResultImporter
from database.sqlserver_manager import SQLServerManager


logger = logging.getLogger(__name__)


class AnalysisJobs:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-analysis")
        self._lock = Lock()
        self._file_lock = Lock()
        self._active: set[int] = set()
        self._deleting: set[int] = set()

    def _state_path(self, video_id: int) -> str:
        config = load_config()
        root = resolve_path(config, get_value(config, "paths.results_dir", "data/results"))
        return os.path.join(root, ".jobs", f"{video_id}.json")

    def get(self, video_id: int) -> dict | None:
        path = self._state_path(video_id)
        state = self._read_state(path)
        if state and state.get("status") in {"queued", "analyzing", "importing"}:
            with self._lock:
                if video_id in self._active:
                    return state
                latest = self._read_state(path)
                if latest and latest.get("status") not in {"queued", "analyzing", "importing"}:
                    return latest
                return self._save(video_id, "failed", "服务重启中断了分析，请重试")
        return state

    def _read_state(self, path: str) -> dict | None:
        with self._file_lock:
            if not os.path.isfile(path):
                return None
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, ValueError):
                return None

    def _save(self, video_id: int, status: str, error: str | None = None, **extra) -> dict:
        path = self._state_path(video_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "status": status,
            "error": error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state.update(extra)
        temporary = f"{path}.tmp"
        with self._file_lock:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False)
            os.replace(temporary, path)
        return state

    def enqueue(self, video_id: int, video_path: str) -> dict:
        with self._lock:
            if video_id in self._deleting:
                raise RuntimeError("视频正在删除，无法开始分析")
            if video_id in self._active:
                return {"status": "queued", "error": None}
            self._active.add(video_id)
            try:
                state = self._save(video_id, "queued")
                self._executor.submit(self._run, video_id, video_path)
            except Exception as exc:
                self._active.discard(video_id)
                return self._save(video_id, "failed", str(exc))
            return state

    def begin_delete(self, video_id: int) -> bool:
        with self._lock:
            if video_id in self._active or video_id in self._deleting:
                return False
            self._deleting.add(video_id)
            return True

    def end_delete(self, video_id: int) -> None:
        with self._lock:
            self._deleting.discard(video_id)

    def remove_state(self, video_id: int) -> None:
        with self._file_lock:
            path = self._state_path(video_id)
            if os.path.isfile(path):
                os.remove(path)

    def _run(self, video_id: int, video_path: str) -> None:
        started = time.perf_counter()
        logger.info("video_id=%s status=started path=%s", video_id, video_path)
        try:
            from pipeline.analysis_pipeline import run_analysis_pipeline

            self._save(video_id, "analyzing", progress=0.0, processed_frames=0, total_frames=None, active_tracks=0)

            def on_progress(processed_frames: int, total_frames: int, active_tracks: int) -> None:
                progress = round((processed_frames / total_frames) * 100, 1) if total_frames else None
                self._save(
                    video_id,
                    "analyzing",
                    progress=progress,
                    processed_frames=processed_frames,
                    total_frames=total_frames or None,
                    active_tracks=active_tracks,
                )

            result = run_analysis_pipeline(video_path=video_path, progress_callback=on_progress)
            self._save(video_id, "importing")
            with open(result["video_info_file"], "r", encoding="utf-8") as handle:
                analyzed_path = json.load(handle).get("path")
            if not analyzed_path or os.path.normcase(os.path.abspath(analyzed_path)) != os.path.normcase(os.path.abspath(video_path)):
                raise RuntimeError("分析结果的视频路径与上传视频不一致，已停止入库")
            config = load_config()
            with SQLServerManager(get_section(config, "database")) as manager:
                imported = ResultImporter(manager, result["result_dir"]).import_results()
            if imported["video_id"] != video_id:
                raise RuntimeError("导入结果关联到了另一个视频，请检查 video_info.json 的路径")
            self._save(video_id, "completed")
            logger.info(
                "video_id=%s status=completed duration_ms=%.2f",
                video_id,
                (time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            self._save(video_id, "failed", f"{type(exc).__name__}: {exc}")
            logger.exception("video_id=%s status=failed", video_id)
        finally:
            with self._lock:
                self._active.discard(video_id)


analysis_jobs = AnalysisJobs()
