import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class HealthApiTests(unittest.TestCase):
    def test_liveness_does_not_require_database(self):
        with TestClient(app) as client:
            response = client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_reports_database_failure(self):
        with patch("backend.api.health_api.database.get", side_effect=RuntimeError("offline")), \
             patch("backend.api.health_api.database.close_current"):
            with TestClient(app) as client:
                response = client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertFalse(response.json()["checks"]["database"]["ok"])


if __name__ == "__main__":
    unittest.main()
