import os
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.main import app


class FakeCursor:
    def execute(self, statement, params):
        self.params = params

    def fetchone(self):
        return (42,)

    def close(self):
        pass


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def commit(self):
        pass


class DeleteManager:
    def __init__(self, video_path, fail=False):
        self.video_path = video_path
        self.fail = fail
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.connection = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return self

    def execute(self, statement, params):
        self.statements.append(statement)
        if self.fail and "DELETE b FROM" in statement:
            raise RuntimeError("database unavailable")
        return self

    def fetchone(self):
        return (self.video_path,)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class VideoApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(app)

    def test_upload_enqueues_analysis_and_returns_video_id(self):
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.get.side_effect = [30, 640, 360, 60]
        with patch("backend.api.video_api.resolve_path", return_value=self.temp.name), \
             patch("backend.api.video_api.database.get", return_value=FakeConnection()), \
             patch("cv2.VideoCapture", return_value=capture), \
             patch("backend.api.video_api.analysis_jobs.enqueue", return_value={"status": "queued", "error": None}) as enqueue:
            response = self.client.post("/api/videos/upload", files={"file": ("clip.mp4", b"video bytes", "video/mp4")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["video_id"], 42)
        self.assertEqual(response.json()["data"]["status"], "queued")
        self.assertEqual(enqueue.call_args.args[0], 42)
        self.assertTrue(os.path.isfile(enqueue.call_args.args[1]))

    def test_invalid_video_is_rejected_before_database_insert(self):
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch("backend.api.video_api.resolve_path", return_value=self.temp.name), \
             patch("backend.api.video_api.database.get", return_value=FakeConnection()) as get_connection, \
             patch("cv2.VideoCapture", return_value=capture):
            response = self.client.post("/api/videos/upload", files={"file": ("broken.mp4", b"invalid", "video/mp4")})
        self.assertEqual(response.status_code, 422)
        get_connection.assert_not_called()
        self.assertEqual(os.listdir(self.temp.name), [])

    def test_list_exposes_failure_reason(self):
        record = {"video_id": 42, "filename": "clip.mp4", "path": os.path.join(self.temp.name, "clip.mp4"), "has_results": 0}
        with patch("backend.api.video_api.database.get", return_value=FakeConnection()), \
             patch("backend.api.video_api.fetch_all", return_value=[record]), \
             patch("backend.api.video_api.analysis_jobs.get", return_value={"status": "failed", "error": "model unavailable"}):
            response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["analysis_error"], "model unavailable")

    def test_stream_supports_partial_content(self):
        path = os.path.join(self.temp.name, "clip.mp4")
        with open(path, "wb") as handle:
            handle.write(b"0123456789")
        with patch("backend.api.video_api.database.get", return_value=FakeConnection()), \
             patch("backend.api.video_api.fetch_one", return_value={"video_path": path}):
            response = self.client.get("/api/videos/42/stream", headers={"Range": "bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(response.headers["Content-Type"], "video/mp4")
        self.assertEqual(response.headers["Content-Disposition"], "inline")
        self.assertEqual(response.content, b"2345")

    def test_delete_uploaded_video_and_related_results(self):
        video_path = os.path.join(self.temp.name, "a1b2c3d4e5f6_clip.mp4")
        result_dir = os.path.join(self.temp.name, "results", "a1b2c3d4e5f6_clip")
        os.makedirs(result_dir)
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        with open(os.path.join(result_dir, "performance.json"), "w") as handle:
            handle.write("{}")
        manager = DeleteManager(video_path)
        with patch("backend.api.video_api.SQLServerManager", return_value=manager), \
             patch("backend.api.video_api._uploaded_paths", return_value=(video_path, result_dir)), \
             patch("backend.api.video_api.analysis_jobs.begin_delete", return_value=True), \
             patch("backend.api.video_api.analysis_jobs.end_delete") as end_delete, \
             patch("backend.api.video_api.analysis_jobs.remove_state") as remove_state:
            response = self.client.delete("/api/videos/42")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["deleted"])
        self.assertEqual(manager.commits, 1)
        self.assertFalse(os.path.exists(video_path))
        self.assertFalse(os.path.exists(result_dir))
        self.assertIn("DELETE a FROM dbo.anomalies", manager.statements[1])
        self.assertIn("DELETE b FROM dbo.behaviors", manager.statements[2])
        self.assertIn("DELETE FROM dbo.persons", manager.statements[3])
        self.assertIn("DELETE FROM dbo.videos", manager.statements[4])
        remove_state.assert_called_once_with(42)
        end_delete.assert_called_once_with(42)

    def test_database_failure_preserves_files(self):
        video_path = os.path.join(self.temp.name, "a1b2c3d4e5f6_clip.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        manager = DeleteManager(video_path, fail=True)
        with patch("backend.api.video_api.SQLServerManager", return_value=manager), \
             patch("backend.api.video_api._uploaded_paths", return_value=(video_path, self.temp.name)), \
             patch("backend.api.video_api.analysis_jobs.begin_delete", return_value=True), \
             patch("backend.api.video_api.analysis_jobs.end_delete"):
            response = self.client.delete("/api/videos/42")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(manager.rollbacks, 1)
        self.assertTrue(os.path.isfile(video_path))

    def test_non_uploaded_video_and_active_job_cannot_be_deleted(self):
        manager = DeleteManager(os.path.join(self.temp.name, "original.mp4"))
        with patch("backend.api.video_api.SQLServerManager", return_value=manager), \
             patch("backend.api.video_api._uploaded_paths", return_value=None):
            self.assertEqual(self.client.delete("/api/videos/42").status_code, 403)
        with patch("backend.api.video_api.SQLServerManager", return_value=manager), \
             patch("backend.api.video_api._uploaded_paths", return_value=(manager.video_path, self.temp.name)), \
             patch("backend.api.video_api.analysis_jobs.begin_delete", return_value=False), \
             patch("backend.api.video_api.analysis_jobs.end_delete") as end_delete:
            self.assertEqual(self.client.delete("/api/videos/42").status_code, 409)
        end_delete.assert_not_called()

    def test_upload_path_must_be_direct_child_of_video_directory(self):
        video_root = os.path.join(self.temp.name, "videos")
        results_root = os.path.join(self.temp.name, "results")
        os.makedirs(video_root)
        os.makedirs(results_root)
        def resolve(config, path):
            return video_root if path == "data/videos" else results_root
        with patch("backend.api.video_api.resolve_path", side_effect=resolve):
            from backend.api.video_api import _uploaded_paths
            self.assertIsNotNone(_uploaded_paths(os.path.join(video_root, "a1b2c3d4e5f6_clip.mp4")))
            self.assertIsNone(_uploaded_paths(os.path.join(video_root, "clip.mp4")))
            self.assertIsNone(_uploaded_paths(os.path.join(self.temp.name, "a1b2c3d4e5f6_clip.mp4")))


if __name__ == "__main__":
    unittest.main()
