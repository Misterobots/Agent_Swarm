"""
Tests for the Bridge Mode relay (Phase 5).
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestBridgeNode(unittest.TestCase):
    """Test BridgeNode dataclass."""

    def test_defaults(self):
        from utils.bridge import BridgeNode
        node = BridgeNode(name="test", api_url="http://1.2.3.4:8000")
        self.assertFalse(node.healthy)
        self.assertEqual(node.last_checked, 0.0)


class TestRemoteJob(unittest.TestCase):
    """Test RemoteJob dataclass."""

    def test_defaults(self):
        from utils.bridge import RemoteJob
        job = RemoteJob(job_id="j1", target_node="Turing", task="test")
        self.assertEqual(job.status, "submitted")
        self.assertIsNone(job.result)

    def test_to_dict(self):
        from utils.bridge import RemoteJob
        job = RemoteJob(job_id="j1", target_node="Turing", task="hello")
        d = job.to_dict()
        self.assertEqual(d["job_id"], "j1")
        self.assertEqual(d["status"], "submitted")
        self.assertIn("submitted_at", d)


class TestBridge(unittest.TestCase):
    """Test the Bridge class."""

    def _get_bridge(self):
        from utils.bridge import Bridge
        return Bridge()

    def test_initialize_nodes(self):
        bridge = self._get_bridge()
        nodes = bridge.list_nodes()
        self.assertTrue(len(nodes) >= 3)
        names = [n["name"] for n in nodes]
        self.assertIn("Turing", names)
        self.assertIn("Lovelace", names)

    def test_check_health_unknown_node(self):
        bridge = self._get_bridge()
        self.assertFalse(bridge.check_health("nonexistent"))

    @patch("requests.get")
    def test_check_health_success(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        bridge = self._get_bridge()
        self.assertTrue(bridge.check_health("Turing"))

    @patch("requests.get")
    def test_check_health_failure(self, mock_get):
        mock_get.side_effect = ConnectionError("refused")
        bridge = self._get_bridge()
        self.assertFalse(bridge.check_health("Turing"))

    @patch("requests.get")
    def test_check_all_health(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        bridge = self._get_bridge()
        health = bridge.check_all_health()
        self.assertIsInstance(health, dict)
        self.assertIn("Turing", health)

    def test_submit_task_unknown_node(self):
        bridge = self._get_bridge()
        result = bridge.submit_task("nonexistent", "hello")
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    @patch("requests.post")
    def test_submit_task_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"status": "queued"},
        )
        bridge = self._get_bridge()
        result = bridge.submit_task("Turing", "run nvidia-smi")
        self.assertEqual(result["status"], "running")
        self.assertIn("job_id", result)

    @patch("requests.post")
    def test_submit_task_http_error(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=500,
            text="Internal Server Error",
        )
        bridge = self._get_bridge()
        result = bridge.submit_task("Turing", "failing task")
        self.assertEqual(result["status"], "failed")
        self.assertIn("500", result["error"])

    @patch("requests.post")
    def test_submit_task_network_error(self, mock_post):
        mock_post.side_effect = ConnectionError("refused")
        bridge = self._get_bridge()
        result = bridge.submit_task("Turing", "unreachable")
        self.assertEqual(result["status"], "failed")

    def test_proxy_request_unknown_node(self):
        bridge = self._get_bridge()
        result = bridge.proxy_request("nonexistent", "GET", "/")
        self.assertIn("error", result)
        self.assertEqual(result["status_code"], -1)

    @patch("requests.request")
    def test_proxy_request_success(self, mock_req):
        mock_req.return_value = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"models": ["qwen2.5"]},
        )
        bridge = self._get_bridge()
        result = bridge.proxy_request("Turing", "GET", "/v1/models")
        self.assertEqual(result["status_code"], 200)
        self.assertIn("models", result["body"])

    def test_get_job_status_nonexistent(self):
        bridge = self._get_bridge()
        self.assertIsNone(bridge.get_job_status("nonexistent-job"))

    @patch("requests.post")
    def test_job_tracking(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"status": "queued"},
        )
        bridge = self._get_bridge()
        result = bridge.submit_task("Turing", "tracked task")
        job_id = result["job_id"]
        
        # Verify job shows up
        status = bridge.get_job_status(job_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["task"], "tracked task")

        # Verify list_jobs works
        jobs = bridge.list_jobs()
        self.assertTrue(len(jobs) >= 1)

    def test_list_jobs_filter(self):
        bridge = self._get_bridge()
        jobs = bridge.list_jobs(status_filter="completed")
        self.assertEqual(len(jobs), 0)


class TestBridgeSingleton(unittest.TestCase):
    def test_singleton(self):
        from utils.bridge import get_bridge
        a = get_bridge()
        b = get_bridge()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()


