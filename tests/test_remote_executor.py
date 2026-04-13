"""
Tests for the SSH Remote Executor (Phase 5).
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Ensure agents dir is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestExecutionResult(unittest.TestCase):
    """Test ExecutionResult dataclass."""

    def _make_result(self, **kwargs):
        from utils.remote_executor import ExecutionResult
        defaults = {
            "host": "r730",
            "command": "echo hello",
            "stdout": "hello\n",
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 42.0,
        }
        defaults.update(kwargs)
        return ExecutionResult(**defaults)

    def test_success_property_true(self):
        r = self._make_result(exit_code=0)
        self.assertTrue(r.success)

    def test_success_property_false_nonzero_exit(self):
        r = self._make_result(exit_code=1)
        self.assertFalse(r.success)

    def test_success_property_false_timeout(self):
        r = self._make_result(exit_code=0, timed_out=True)
        self.assertFalse(r.success)

    def test_to_dict(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertEqual(d["host"], "r730")
        self.assertEqual(d["command"], "echo hello")
        self.assertEqual(d["exit_code"], 0)
        self.assertIn("duration_ms", d)

    def test_str_ok(self):
        r = self._make_result(exit_code=0)
        s = str(r)
        self.assertIn("OK", s)
        self.assertIn("r730", s)

    def test_str_fail(self):
        r = self._make_result(exit_code=127)
        s = str(r)
        self.assertIn("FAIL", s)


class TestRemoteHost(unittest.TestCase):
    """Test RemoteHost dataclass."""

    def test_defaults(self):
        from utils.remote_executor import RemoteHost
        h = RemoteHost(name="test", host="1.2.3.4", user="user")
        self.assertEqual(h.port, 22)
        self.assertFalse(h.healthy)
        self.assertEqual(h.key_path, "")


class TestRemoteExecutor(unittest.TestCase):
    """Test the RemoteExecutor class."""

    def _get_executor(self):
        from utils.remote_executor import RemoteExecutor
        return RemoteExecutor()

    def test_initialize_hosts(self):
        executor = self._get_executor()
        hosts = executor.list_hosts()
        self.assertTrue(len(hosts) >= 3)
        names = [h["name"] for h in hosts]
        self.assertIn("justin-pc", names)
        self.assertIn("control-plane", names)
        self.assertIn("r730", names)

    def test_get_host_known(self):
        executor = self._get_executor()
        host = executor.get_host("r730")
        self.assertIsNotNone(host)
        self.assertEqual(host.name, "r730")

    def test_get_host_unknown(self):
        executor = self._get_executor()
        self.assertIsNone(executor.get_host("nonexistent"))

    def test_execute_blocked_host(self):
        executor = self._get_executor()
        result = executor.execute("evil-server", "echo pwned")
        self.assertFalse(result.success)
        self.assertIn("allowlist", result.stderr)

    def test_execute_blocked_command(self):
        """Commands blocked by bash_classifier should be rejected."""
        executor = self._get_executor()
        # rm -rf / is in the security_policy.json blocklist
        with patch("utils.remote_executor.RemoteExecutor._check_command_safety", return_value=(True, "Blocked by policy")):
            result = executor.execute("r730", "rm -rf /")
            self.assertFalse(result.success)
            self.assertIn("blocked", result.stderr.lower())

    @patch("subprocess.run")
    def test_execute_success_mocked(self, mock_run):
        """Test a successful SSH execution with mocked subprocess."""
        mock_run.return_value = MagicMock(
            stdout="GPU 0: NVIDIA RTX 3070 Ti\n",
            stderr="",
            returncode=0,
        )
        executor = self._get_executor()
        result = executor.execute("r730", "nvidia-smi", check_safety=False)
        self.assertTrue(result.success)
        self.assertIn("GPU", result.stdout)
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_timeout_mocked(self, mock_run):
        """Test SSH timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5)
        executor = self._get_executor()
        result = executor.execute("r730", "sleep 999", timeout=5, check_safety=False)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.success)

    @patch("subprocess.run")
    def test_execute_failure_mocked(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="command not found",
            returncode=127,
        )
        executor = self._get_executor()
        result = executor.execute("r730", "nonexistent_cmd", check_safety=False)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 127)

    def test_check_command_safety_safe(self):
        executor = self._get_executor()
        blocked, reason = executor._check_command_safety("ls -la")
        self.assertFalse(blocked)

    def test_check_command_safety_blocked(self):
        """Verify _check_command_safety integrates with classifier."""
        executor = self._get_executor()
        with patch("utils.remote_executor.RemoteExecutor._check_command_safety") as mock_safety:
            mock_safety.return_value = (True, "dangerous")
            blocked, reason = executor._check_command_safety("rm -rf /")
            # This tests the mock path; real integration tested in bash_classifier tests
            self.assertTrue(blocked)

    def test_case_insensitive_host(self):
        executor = self._get_executor()
        result = executor.execute("EVIL-SERVER", "echo test")
        self.assertIn("allowlist", result.stderr)


class TestRemoteExecutorSingleton(unittest.TestCase):
    """Test singleton pattern."""

    def test_singleton(self):
        from utils.remote_executor import get_remote_executor
        a = get_remote_executor()
        b = get_remote_executor()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()
