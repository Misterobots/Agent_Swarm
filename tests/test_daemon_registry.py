"""
Tests for the Daemon Worker Registry (Phase 5).
"""

import os
import sys
import time
import unittest
import threading
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestDaemonState(unittest.TestCase):
    def test_states(self):
        from daemon_registry import DaemonState
        self.assertEqual(DaemonState.PENDING.value, "pending")
        self.assertEqual(DaemonState.RUNNING.value, "running")
        self.assertEqual(DaemonState.STOPPED.value, "stopped")
        self.assertEqual(DaemonState.FAILED.value, "failed")


class TestDaemonWorker(unittest.TestCase):
    def test_to_dict(self):
        from daemon_registry import DaemonWorker, DaemonState
        w = DaemonWorker(
            worker_id="d1", name="test", handler=lambda: None,
            interval=60, state=DaemonState.RUNNING, failure_count=1,
        )
        d = w.to_dict()
        self.assertEqual(d["worker_id"], "d1")
        self.assertEqual(d["state"], "running")
        self.assertEqual(d["interval"], 60)


class TestDaemonRegistry(unittest.TestCase):
    def _get_registry(self):
        from daemon_registry import DaemonRegistry
        return DaemonRegistry(max_workers=5)

    def test_register(self):
        reg = self._get_registry()
        wid = reg.register("test", lambda: None, interval=10)
        self.assertTrue(wid.startswith("daemon-"))
        self.assertEqual(reg.count(), 1)

    def test_register_auto_start(self):
        reg = self._get_registry()
        called = threading.Event()
        def handler():
            called.set()
        wid = reg.register("auto", handler, interval=5, auto_start=True)
        # Give thread time to start and call handler
        called.wait(timeout=2)
        reg.stop(wid)
        self.assertTrue(called.is_set())

    def test_register_max_workers(self):
        reg = self._get_registry()
        for i in range(5):
            reg.register(f"w{i}", lambda: None)
        with self.assertRaises(RuntimeError):
            reg.register("overflow", lambda: None)

    def test_register_min_interval(self):
        reg = self._get_registry()
        wid = reg.register("fast", lambda: None, interval=1)
        w = reg.get(wid)
        self.assertEqual(w["interval"], 5)  # Clamped to minimum

    def test_start_stop(self):
        reg = self._get_registry()
        wid = reg.register("svc", lambda: None, interval=10)
        self.assertTrue(reg.start(wid))
        w = reg.get(wid)
        self.assertEqual(w["state"], "running")
        self.assertTrue(reg.stop(wid))
        w = reg.get(wid)
        self.assertEqual(w["state"], "stopped")

    def test_start_unknown(self):
        reg = self._get_registry()
        self.assertFalse(reg.start("nonexistent"))

    def test_start_already_running(self):
        reg = self._get_registry()
        wid = reg.register("svc", lambda: None, interval=10)
        reg.start(wid)
        self.assertTrue(reg.start(wid))  # Idempotent
        reg.stop(wid)

    def test_unregister(self):
        reg = self._get_registry()
        wid = reg.register("rm", lambda: None)
        self.assertTrue(reg.unregister(wid))
        self.assertEqual(reg.count(), 0)
        self.assertFalse(reg.unregister(wid))  # Already removed

    def test_get_unknown(self):
        reg = self._get_registry()
        self.assertIsNone(reg.get("nonexistent"))

    def test_list_workers(self):
        reg = self._get_registry()
        reg.register("a", lambda: None)
        reg.register("b", lambda: None)
        workers = reg.list_workers()
        self.assertEqual(len(workers), 2)

    def test_list_workers_filter(self):
        reg = self._get_registry()
        wid = reg.register("r", lambda: None)
        reg.start(wid)
        pending = reg.list_workers(state_filter="pending")
        running = reg.list_workers(state_filter="running")
        self.assertEqual(len(pending), 0)
        self.assertEqual(len(running), 1)
        reg.stop(wid)

    def test_count_filter(self):
        reg = self._get_registry()
        reg.register("a", lambda: None)
        wid = reg.register("b", lambda: None)
        reg.start(wid)
        self.assertEqual(reg.count("pending"), 1)
        self.assertEqual(reg.count("running"), 1)
        self.assertEqual(reg.count(), 2)
        reg.stop(wid)

    def test_stop_all(self):
        reg = self._get_registry()
        w1 = reg.register("a", lambda: None)
        w2 = reg.register("b", lambda: None)
        reg.start(w1)
        reg.start(w2)
        reg.stop_all()
        running = reg.count("running")
        self.assertEqual(running, 0)

    def test_worker_handler_called(self):
        reg = self._get_registry()
        counter = {"n": 0}
        def handler():
            counter["n"] += 1
        wid = reg.register("counter", handler, interval=5, auto_start=True)
        time.sleep(0.3)  # Give time for at least one call
        reg.stop(wid)
        self.assertGreaterEqual(counter["n"], 1)

    def test_worker_failure_tracking(self):
        reg = self._get_registry()
        def failing_handler():
            raise RuntimeError("boom")
        wid = reg.register("failer", failing_handler, interval=5, max_failures=2, auto_start=True)
        time.sleep(0.5)  # Let it fail twice
        reg.stop(wid)
        w = reg.get(wid)
        self.assertIn(w["state"], ("failed", "stopped"))
        self.assertIsNotNone(w["last_error"])

    def test_invalid_state_filter(self):
        reg = self._get_registry()
        reg.register("a", lambda: None)
        # Invalid filter falls through (returns all workers)
        result = reg.list_workers(state_filter="nonexistent")
        self.assertEqual(len(result), 1)  # Filter not recognized = no filtering


class TestDaemonSingleton(unittest.TestCase):
    def test_singleton(self):
        from daemon_registry import get_daemon_registry
        a = get_daemon_registry()
        b = get_daemon_registry()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()
