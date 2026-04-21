"""
Tests for the Trigger Scheduler (Phase 5).
"""

import os
import sys
import time
import unittest
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestTriggerType(unittest.TestCase):
    def test_types(self):
        from trigger_scheduler import TriggerType
        self.assertEqual(TriggerType.CRON.value, "cron")
        self.assertEqual(TriggerType.INTERVAL.value, "interval")
        self.assertEqual(TriggerType.ONCE.value, "once")


class TestTriggerState(unittest.TestCase):
    def test_states(self):
        from trigger_scheduler import TriggerState
        self.assertEqual(TriggerState.ACTIVE.value, "active")
        self.assertEqual(TriggerState.PAUSED.value, "paused")
        self.assertEqual(TriggerState.FIRED.value, "fired")


class TestTrigger(unittest.TestCase):
    def test_cron_to_dict(self):
        from trigger_scheduler import Trigger, TriggerType
        t = Trigger(
            trigger_id="t1", name="nightly", trigger_type=TriggerType.CRON,
            handler=lambda: None, cron_hour=2, cron_minute=0,
        )
        d = t.to_dict()
        self.assertEqual(d["trigger_type"], "cron")
        self.assertEqual(d["cron"]["hour"], 2)
        self.assertEqual(d["cron"]["minute"], 0)

    def test_interval_to_dict(self):
        from trigger_scheduler import Trigger, TriggerType
        t = Trigger(
            trigger_id="t2", name="poll", trigger_type=TriggerType.INTERVAL,
            handler=lambda: None, interval_seconds=300,
        )
        d = t.to_dict()
        self.assertEqual(d["interval_seconds"], 300)

    def test_once_to_dict(self):
        from trigger_scheduler import Trigger, TriggerType
        t = Trigger(
            trigger_id="t3", name="delayed", trigger_type=TriggerType.ONCE,
            handler=lambda: None, fire_at=9999999999.0,
        )
        d = t.to_dict()
        self.assertIn("fire_at", d)

    def test_remote_to_dict(self):
        from trigger_scheduler import Trigger, TriggerType
        t = Trigger(
            trigger_id="t4", name="remote", trigger_type=TriggerType.INTERVAL,
            handler=lambda: None, interval_seconds=60,
            remote_node="Turing", remote_task="nvidia-smi",
        )
        d = t.to_dict()
        self.assertEqual(d["remote_node"], "Turing")
        self.assertEqual(d["remote_task"], "nvidia-smi")


class TestTriggerScheduler(unittest.TestCase):
    def _get_scheduler(self):
        from trigger_scheduler import TriggerScheduler
        return TriggerScheduler()

    def test_add_cron(self):
        sched = self._get_scheduler()
        tid = sched.add_cron("nightly", lambda: None, hour=2, minute=0)
        self.assertTrue(tid.startswith("trg-"))
        self.assertEqual(sched.count(), 1)

    def test_add_interval(self):
        sched = self._get_scheduler()
        tid = sched.add_interval("poll", lambda: None, seconds=60)
        t = sched.get(tid)
        self.assertEqual(t["trigger_type"], "interval")
        self.assertEqual(t["interval_seconds"], 60)

    def test_add_interval_min_5s(self):
        sched = self._get_scheduler()
        tid = sched.add_interval("fast", lambda: None, seconds=1)
        t = sched.get(tid)
        self.assertEqual(t["interval_seconds"], 5)

    def test_add_once(self):
        sched = self._get_scheduler()
        tid = sched.add_once("delayed", lambda: None, delay_seconds=60)
        t = sched.get(tid)
        self.assertEqual(t["trigger_type"], "once")
        self.assertIsNotNone(t["fire_at"])

    def test_add_once_fire_at(self):
        sched = self._get_scheduler()
        future = time.time() + 3600
        tid = sched.add_once("timed", lambda: None, fire_at=future)
        t = sched.get(tid)
        self.assertAlmostEqual(t["fire_at"], future, places=0)

    def test_remove(self):
        sched = self._get_scheduler()
        tid = sched.add_interval("rm", lambda: None, seconds=60)
        self.assertTrue(sched.remove(tid))
        self.assertEqual(sched.count(), 0)
        self.assertFalse(sched.remove(tid))

    def test_pause_resume(self):
        sched = self._get_scheduler()
        tid = sched.add_interval("pr", lambda: None, seconds=60)
        self.assertTrue(sched.pause(tid))
        t = sched.get(tid)
        self.assertEqual(t["state"], "paused")
        self.assertTrue(sched.resume(tid))
        t = sched.get(tid)
        self.assertEqual(t["state"], "active")

    def test_pause_nonexistent(self):
        sched = self._get_scheduler()
        self.assertFalse(sched.pause("nonexistent"))

    def test_resume_not_paused(self):
        sched = self._get_scheduler()
        tid = sched.add_interval("active", lambda: None, seconds=60)
        self.assertFalse(sched.resume(tid))  # Already active

    def test_list_triggers(self):
        sched = self._get_scheduler()
        sched.add_cron("c", lambda: None, hour=0)
        sched.add_interval("i", lambda: None, seconds=60)
        triggers = sched.list_triggers()
        self.assertEqual(len(triggers), 2)

    def test_list_triggers_filter(self):
        sched = self._get_scheduler()
        sched.add_cron("c", lambda: None, hour=0)
        sched.add_interval("i", lambda: None, seconds=60)
        cron_only = sched.list_triggers(type_filter="cron")
        self.assertEqual(len(cron_only), 1)

    def test_get_nonexistent(self):
        sched = self._get_scheduler()
        self.assertIsNone(sched.get("nonexistent"))

    def test_start_stop(self):
        sched = self._get_scheduler()
        sched.start()
        self.assertTrue(sched.is_running)
        sched.stop()
        self.assertFalse(sched.is_running)

    def test_start_idempotent(self):
        sched = self._get_scheduler()
        sched.start()
        sched.start()  # Should not crash
        self.assertTrue(sched.is_running)
        sched.stop()

    def test_interval_fires(self):
        sched = self._get_scheduler()
        counter = {"n": 0}
        def handler():
            counter["n"] += 1

        sched.add_interval("quick", handler, seconds=5)
        # Manually tick (don't rely on background thread timing)
        sched._tick()
        self.assertGreaterEqual(counter["n"], 1)

    def test_once_fires(self):
        sched = self._get_scheduler()
        counter = {"n": 0}
        def handler():
            counter["n"] += 1

        sched.add_once("now", handler, fire_at=time.time() - 1)  # Already past
        sched._tick()
        self.assertEqual(counter["n"], 1)

    def test_once_becomes_fired(self):
        sched = self._get_scheduler()
        tid = sched.add_once("past", lambda: None, fire_at=time.time() - 1)
        sched._tick()
        t = sched.get(tid)
        self.assertEqual(t["state"], "fired")

    def test_paused_trigger_not_fired(self):
        sched = self._get_scheduler()
        counter = {"n": 0}
        tid = sched.add_interval("paused", lambda: counter.update(n=counter["n"]+1), seconds=5)
        sched.pause(tid)
        sched._tick()
        self.assertEqual(counter["n"], 0)

    def test_cron_match(self):
        sched = self._get_scheduler()
        now = datetime.now()
        counter = {"n": 0}
        def handler():
            counter["n"] += 1

        # Set cron to match current hour and minute
        sched.add_cron("now-cron", handler, hour=now.hour, minute=now.minute)
        sched._tick()
        self.assertEqual(counter["n"], 1)

    def test_cron_no_match(self):
        sched = self._get_scheduler()
        now = datetime.now()
        counter = {"n": 0}
        wrong_hour = (now.hour + 5) % 24  # Different hour
        sched.add_cron("wrong", lambda: counter.update(n=counter["n"]+1), hour=wrong_hour)
        sched._tick()
        self.assertEqual(counter["n"], 0)

    def test_cron_no_double_fire(self):
        sched = self._get_scheduler()
        now = datetime.now()
        counter = {"n": 0}
        def handler():
            counter["n"] += 1

        sched.add_cron("once-per-min", handler, hour=now.hour, minute=now.minute)
        sched._tick()
        sched._tick()  # Second tick in same minute
        self.assertEqual(counter["n"], 1)

    def test_remote_trigger(self):
        sched = self._get_scheduler()
        tid = sched.add_interval(
            "remote-poll", lambda: None, seconds=60,
            remote_node="Turing", remote_task="nvidia-smi"
        )
        t = sched.get(tid)
        self.assertEqual(t["remote_node"], "Turing")

    def test_handler_error_tracked(self):
        sched = self._get_scheduler()
        def failing():
            raise RuntimeError("boom")

        tid = sched.add_once("fail", failing, fire_at=time.time() - 1)
        sched._tick()
        t = sched.get(tid)
        self.assertIsNotNone(t["last_error"])
        self.assertIn("boom", t["last_error"])


class TestTriggerSingleton(unittest.TestCase):
    def test_singleton(self):
        from trigger_scheduler import get_trigger_scheduler
        a = get_trigger_scheduler()
        b = get_trigger_scheduler()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()


