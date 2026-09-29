import json
import os
import sys
import tempfile
import time
import types
import unittest
from threading import Event
from unittest.mock import patch

from backend.analysis_jobs import AnalysisJobs


class AnalysisJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jobs = AnalysisJobs()
        self.path = os.path.join(self.temp.name, "video.mp4")
        self.state_path = os.path.join(self.temp.name, "job.json")
        self.jobs._state_path = lambda video_id: self.state_path

    def wait_for_terminal_state(self):
        for _ in range(100):
            state = self.jobs.get(7)
            if state and state["status"] in {"completed", "failed"}:
                return state
            time.sleep(0.01)
        self.fail("后台任务未进入最终状态")

    def test_analysis_import_and_duplicate_enqueue(self):
        info_path = os.path.join(self.temp.name, "video_info.json")
        with open(info_path, "w", encoding="utf-8") as handle:
            json.dump({"path": self.path}, handle)
        pipeline = types.ModuleType("pipeline.analysis_pipeline")
        started = Event()
        release = Event()
        calls = []

        def run_pipeline(video_path, progress_callback=None):
            calls.append(video_path)
            started.set()
            if progress_callback is not None:
                progress_callback(10, 100, 1)
            release.wait(2)
            return {"result_dir": self.temp.name, "video_info_file": info_path}

        pipeline.run_analysis_pipeline = run_pipeline

        class Manager:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        class Importer:
            def __init__(self, manager, result_dir):
                pass

            def import_results(self):
                return {"video_id": 7}

        with patch.dict(sys.modules, {"pipeline.analysis_pipeline": pipeline}), \
             patch("backend.analysis_jobs.SQLServerManager", Manager), \
             patch("backend.analysis_jobs.ResultImporter", Importer):
            try:
                self.assertEqual(self.jobs.enqueue(7, self.path)["status"], "queued")
                self.assertTrue(started.wait(2))
                self.assertEqual(self.jobs.enqueue(7, self.path)["status"], "queued")
            finally:
                release.set()
            self.assertEqual(self.wait_for_terminal_state()["status"], "completed")
            self.assertEqual(calls, [self.path])

    def test_failure_preserves_reason_and_can_retry(self):
        pipeline = types.ModuleType("pipeline.analysis_pipeline")
        calls = []

        def fail(video_path, progress_callback=None):
            calls.append(video_path)
            raise RuntimeError("model unavailable")

        pipeline.run_analysis_pipeline = fail
        with patch.dict(sys.modules, {"pipeline.analysis_pipeline": pipeline}):
            self.jobs.enqueue(7, self.path)
            self.assertIn("model unavailable", self.wait_for_terminal_state()["error"])
            self.jobs.enqueue(7, self.path)
            self.assertIn("model unavailable", self.wait_for_terminal_state()["error"])
        self.assertEqual(len(calls), 2)

    def test_interrupted_job_becomes_failed(self):
        self.jobs._save(7, "analyzing")
        state = self.jobs.get(7)
        self.assertEqual(state["status"], "failed")
        self.assertIn("重试", state["error"])


if __name__ == "__main__":
    unittest.main()
