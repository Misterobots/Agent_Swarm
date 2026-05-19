"""
trigger_scheduler.py — Agent Trigger Scheduler

Provides cron-like scheduling, one-shot timers, and event-driven
trigger registration for automated agent task dispatch.

Features:
    - Cron expressions (hour/minute/day_of_week)
    - One-shot delayed triggers
    - Interval-based recurring triggers
    - Remote trigger support (fire triggers on other nodes via Bridge)
    - Event-based triggers (register handler for event type)
    - Trigger persistence for resume-after-restart

Architecture:
    TriggerScheduler (singleton, runs its own ticker thread)
    └─ Trigger
       ├─ CronTrigger (hour, minute, day_of_week matching)
       ├─ IntervalTrigger (every N seconds)
       └─ OnceTrigger (fire at specific timestamp)

Usage:
    from trigger_scheduler import get_trigger_scheduler

    scheduler = get_trigger_scheduler()

    # Every day at 2:00 AM — run training
    scheduler.add_cron("nightly-training", handler=start_training, hour=2, minute=0)

    # Every 5 minutes — health check
    scheduler.add_interval("health-poll", handler=check_health, seconds=300)

    # One-shot in 60 seconds
    scheduler.add_once("delayed-task", handler=run_task, delay_seconds=60)

    scheduler.start()
"""

import os
import time
import json
import uuid
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from datetime import datetime
from pathlib import Path

from logger_setup import setup_logger

logger = setup_logger("TriggerScheduler")


class TriggerType(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class TriggerState(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    FIRED = "fired"  # For once triggers that have executed
    FAILED = "failed"


@dataclass
class Trigger:
    """Base trigger definition."""
    trigger_id: str
    name: str
    trigger_type: TriggerType
    handler: Callable[[], Any]
    state: TriggerState = TriggerState.ACTIVE
    fire_count: int = 0
    last_fired: Optional[float] = None
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    # Remote trigger support
    remote_node: Optional[str] = None  # If set, fire on this node via Bridge
    remote_task: Optional[str] = None  # Task string for remote execution

    # Cron fields
    cron_hour: Optional[int] = None      # 0-23, None = any
    cron_minute: Optional[int] = None    # 0-59, None = any
    cron_day_of_week: Optional[int] = None  # 0=Mon, 6=Sun, None = any

    # Interval fields
    interval_seconds: Optional[float] = None

    # Once fields
    fire_at: Optional[float] = None  # Unix timestamp

    def to_dict(self) -> dict:
        d = {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "state": self.state.value,
            "fire_count": self.fire_count,
            "last_fired": self.last_fired,
            "last_error": self.last_error,
            "created_at": self.created_at,
        }
        if self.remote_node:
            d["remote_node"] = self.remote_node
            d["remote_task"] = self.remote_task
        if self.trigger_type == TriggerType.CRON:
            d["cron"] = {
                "hour": self.cron_hour,
                "minute": self.cron_minute,
                "day_of_week": self.cron_day_of_week,
            }
        elif self.trigger_type == TriggerType.INTERVAL:
            d["interval_seconds"] = self.interval_seconds
        elif self.trigger_type == TriggerType.ONCE:
            d["fire_at"] = self.fire_at
        return d


# Tick interval for the scheduler loop (seconds)
TICK_INTERVAL = int(os.getenv("TRIGGER_TICK_INTERVAL", "15"))

# Persistence
TRIGGER_STATE_DIR = Path(os.getenv(
    "TRIGGER_STATE_DIR",
    "/workspace/trigger_state"
))


class TriggerScheduler:
    """Cron-like scheduler with interval and one-shot trigger support."""

    def __init__(self):
        self._triggers: Dict[str, Trigger] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Track which cron triggers already fired for the current minute
        self._cron_fired_minute: Dict[str, int] = {}

    def add_cron(
        self,
        name: str,
        handler: Callable[[], Any],
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        day_of_week: Optional[int] = None,
        remote_node: Optional[str] = None,
        remote_task: Optional[str] = None,
    ) -> str:
        """
        Add a cron-style trigger.

        Args:
            name: Trigger name
            handler: Function to call when triggered
            hour: Hour to fire (0-23), None = every hour
            minute: Minute to fire (0-59), None = every minute
            day_of_week: Day to fire (0=Mon, 6=Sun), None = every day
            remote_node: If set, fire on a remote node via Bridge
            remote_task: Task string for remote execution

        Returns:
            trigger_id
        """
        trigger_id = f"trg-{uuid.uuid4().hex[:8]}"
        trigger = Trigger(
            trigger_id=trigger_id,
            name=name,
            trigger_type=TriggerType.CRON,
            handler=handler,
            cron_hour=hour,
            cron_minute=minute,
            cron_day_of_week=day_of_week,
            remote_node=remote_node,
            remote_task=remote_task,
        )
        with self._lock:
            self._triggers[trigger_id] = trigger
        logger.info(f"[Scheduler] Added cron trigger '{name}' ({trigger_id}): h={hour} m={minute} dow={day_of_week}")
        return trigger_id

    def add_interval(
        self,
        name: str,
        handler: Callable[[], Any],
        seconds: float = 60.0,
        remote_node: Optional[str] = None,
        remote_task: Optional[str] = None,
    ) -> str:
        """
        Add a recurring interval trigger.

        Args:
            name: Trigger name
            handler: Function to call
            seconds: Interval between fires (minimum 5)
            remote_node: If set, fire on remote node
            remote_task: Task string for remote

        Returns:
            trigger_id
        """
        if seconds < 5:
            seconds = 5

        trigger_id = f"trg-{uuid.uuid4().hex[:8]}"
        trigger = Trigger(
            trigger_id=trigger_id,
            name=name,
            trigger_type=TriggerType.INTERVAL,
            handler=handler,
            interval_seconds=seconds,
            remote_node=remote_node,
            remote_task=remote_task,
        )
        with self._lock:
            self._triggers[trigger_id] = trigger
        logger.info(f"[Scheduler] Added interval trigger '{name}' ({trigger_id}): every {seconds}s")
        return trigger_id

    def add_once(
        self,
        name: str,
        handler: Callable[[], Any],
        delay_seconds: float = 0,
        fire_at: Optional[float] = None,
        remote_node: Optional[str] = None,
        remote_task: Optional[str] = None,
    ) -> str:
        """
        Add a one-shot trigger.

        Args:
            name: Trigger name
            handler: Function to call
            delay_seconds: Seconds from now to fire (if fire_at not set)
            fire_at: Specific Unix timestamp to fire at
            remote_node: If set, fire on remote node
            remote_task: Task string for remote

        Returns:
            trigger_id
        """
        if fire_at is None:
            fire_at = time.time() + delay_seconds

        trigger_id = f"trg-{uuid.uuid4().hex[:8]}"
        trigger = Trigger(
            trigger_id=trigger_id,
            name=name,
            trigger_type=TriggerType.ONCE,
            handler=handler,
            fire_at=fire_at,
            remote_node=remote_node,
            remote_task=remote_task,
        )
        with self._lock:
            self._triggers[trigger_id] = trigger
        logger.info(f"[Scheduler] Added one-shot trigger '{name}' ({trigger_id})")
        return trigger_id

    def remove(self, trigger_id: str) -> bool:
        """Remove a trigger."""
        with self._lock:
            return self._triggers.pop(trigger_id, None) is not None

    def pause(self, trigger_id: str) -> bool:
        """Pause a trigger."""
        trigger = self._triggers.get(trigger_id)
        if trigger and trigger.state == TriggerState.ACTIVE:
            trigger.state = TriggerState.PAUSED
            return True
        return False

    def resume(self, trigger_id: str) -> bool:
        """Resume a paused trigger."""
        trigger = self._triggers.get(trigger_id)
        if trigger and trigger.state == TriggerState.PAUSED:
            trigger.state = TriggerState.ACTIVE
            return True
        return False

    def list_triggers(self, type_filter: Optional[str] = None) -> list[dict]:
        """List all triggers."""
        triggers = self._triggers.values()
        if type_filter:
            try:
                target = TriggerType(type_filter)
                triggers = [t for t in triggers if t.trigger_type == target]
            except ValueError:
                pass
        return [t.to_dict() for t in triggers]

    def get(self, trigger_id: str) -> Optional[dict]:
        trigger = self._triggers.get(trigger_id)
        return trigger.to_dict() if trigger else None

    def count(self) -> int:
        return len(self._triggers)

    def start(self):
        """Start the scheduler ticker thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._tick_loop,
            daemon=True,
            name="trigger-scheduler",
        )
        self._thread.start()
        logger.info(f"[Scheduler] Started (tick interval: {TICK_INTERVAL}s)")

    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()
        self._running = False
        logger.info("[Scheduler] Stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _tick_loop(self):
        """Main scheduler loop — checks all triggers every TICK_INTERVAL."""
        while not self._stop_event.is_set():
            self._tick()
            self._stop_event.wait(timeout=TICK_INTERVAL)

    def _tick(self):
        """Evaluate all triggers and fire those that are due."""
        now = time.time()
        now_dt = datetime.fromtimestamp(now)

        with self._lock:
            triggers = list(self._triggers.values())

        for trigger in triggers:
            if trigger.state != TriggerState.ACTIVE:
                continue

            should_fire = False

            if trigger.trigger_type == TriggerType.CRON:
                should_fire = self._check_cron(trigger, now_dt)

            elif trigger.trigger_type == TriggerType.INTERVAL:
                if trigger.last_fired is None:
                    should_fire = True
                elif now - trigger.last_fired >= trigger.interval_seconds:
                    should_fire = True

            elif trigger.trigger_type == TriggerType.ONCE:
                if trigger.fire_at and now >= trigger.fire_at:
                    should_fire = True

            if should_fire:
                self._fire(trigger)

    def _check_cron(self, trigger: Trigger, now: datetime) -> bool:
        """Check if a cron trigger should fire now."""
        # Match fields
        if trigger.cron_hour is not None and now.hour != trigger.cron_hour:
            return False
        if trigger.cron_minute is not None and now.minute != trigger.cron_minute:
            return False
        if trigger.cron_day_of_week is not None and now.weekday() != trigger.cron_day_of_week:
            return False

        # Don't fire twice in the same minute
        current_minute = now.hour * 60 + now.minute
        last_minute = self._cron_fired_minute.get(trigger.trigger_id, -1)
        if current_minute == last_minute:
            return False

        return True

    def _fire(self, trigger: Trigger):
        """Execute a trigger's handler."""
        logger.info(f"[Scheduler] Firing trigger '{trigger.name}' ({trigger.trigger_id})")

        try:
            if trigger.remote_node and trigger.remote_task:
                self._fire_remote(trigger)
            else:
                trigger.handler()

            trigger.fire_count += 1
            trigger.last_fired = time.time()

            # Track cron minute
            if trigger.trigger_type == TriggerType.CRON:
                now = datetime.now()
                self._cron_fired_minute[trigger.trigger_id] = now.hour * 60 + now.minute

            # Once triggers become FIRED
            if trigger.trigger_type == TriggerType.ONCE:
                trigger.state = TriggerState.FIRED

        except Exception as e:
            trigger.last_error = str(e)
            logger.error(f"[Scheduler] Trigger '{trigger.name}' failed: {e}")

    def _fire_remote(self, trigger: Trigger):
        """Fire a trigger on a remote node via Bridge."""
        try:
            from utils.bridge import get_bridge
            bridge = get_bridge()
            result = bridge.submit_task(
                target_node=trigger.remote_node,
                task=trigger.remote_task,
            )
            logger.info(
                f"[Scheduler] Remote trigger '{trigger.name}' → "
                f"{trigger.remote_node}: {result.get('status', 'unknown')}"
            )
        except ImportError:
            logger.error("[Scheduler] Bridge not available for remote trigger")
        except Exception as e:
            raise RuntimeError(f"Remote trigger failed: {e}") from e


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_scheduler: Optional[TriggerScheduler] = None


def get_trigger_scheduler() -> TriggerScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TriggerScheduler()
    return _scheduler
