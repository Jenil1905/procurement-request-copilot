"""Unit tests for the FastAPI web application and UI endpoints."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app import app


class TestWebApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AI Procurement Request Copilot", resp.text)
        self.assertIn("Grounded Evidence Dossier", resp.text)

    def test_list_requests(self):
        resp = self.client.get("/api/requests")
        self.assertEqual(resp.status_code, 200)
        requests = resp.json()
        self.assertEqual(len(requests), 10)
        self.assertEqual(requests[0]["request_id"], "REQ-1001")

    def test_run_copilot_endpoint(self):
        resp = self.client.post("/api/run", json={"request_id": "REQ-1001", "arch": "A"})
        self.assertEqual(resp.status_code, 200)
        decision = resp.json()
        self.assertEqual(decision["request_id"], "REQ-1001")
        self.assertIn("Manager", decision["required_approvals"])
        self.assertTrue(decision["human_review_required"])
        self.assertGreater(len(decision["evidence"]), 0)

    def test_human_decision_logging(self):
        resp = self.client.post(
            "/api/human-decision",
            json={
                "request_id": "REQ-1001",
                "action": "approve",
                "notes": "Verified quarterly budget with Priya Shah",
                "approver": "Test User",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

        # Check log retrieval
        log_resp = self.client.get("/api/decisions-log")
        self.assertEqual(log_resp.status_code, 200)
        logs = log_resp.json()
        self.assertTrue(any(l["request_id"] == "REQ-1001" and l["action"] == "approve" for l in logs))


if __name__ == "__main__":
    unittest.main()
