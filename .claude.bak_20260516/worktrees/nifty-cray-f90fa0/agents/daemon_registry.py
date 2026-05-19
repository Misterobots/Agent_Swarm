"""
daemon_registry.py — Persistent Background Worker Registry

Manages long-running daemon workers that persist beyond a single
conversation. Workers can be started, stopped, monitored, and
auto-restarted on failure.

Use cases:
    - CI/CD watchers (monitor repos for changes)
    - System health monitors
    - Periodic cleanup tasks
    - PR review bots
    - Metrics collectors

Architecture:
    DaemonRegistry (singleton)
    └─ DaemonWorker (thread-based, restartable)
       ├─ handler: Callable that runs in a loop
       ├─ interval: seconds between handler calls
       └─ state: pending → running → stopped | failed

Usage:
    from daemon_registry import get_daemon_registry

    registry = get_daemon_registry()
    worker_id = registry.register("health-monitor", health_check_handler, interval=60)
    registry.start(worker_id)
    registry.stop(worker_id)
"""

import os
import time
import uuid
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from logger_setup import setup_logger

logger = setup_logger("DaemonRegistry")


class DaemonState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class DaemonWorker:
    """A persistent background worker."""
    worker_id: str
    name: str
    handler: Callable[[], Any]
    interval: float  # seconds between handler calls
    state: DaemonState = DaemonState.PENDING
    max_failures: int = 3
    failure_count: int = 0
    last_run: Optional[float] = None
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "state": self.state.value,
            "interval": self.interval,
            "max_failures": self.max_failures,
            "failure_count": self.failure_count,
            "last_run": self.last_run,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
        }


class DaemonRegistry:
    """Central registry for persistent background workers."""

    def __init__(self, max_workers: int = 20):
        self._workers: Dict[str, DaemonWorker] = {}
        self._lock = threading.Lock()
        self._max_workers = max_workers

    def register(
        self,
        name: str,
        handler: Callable[[], Any],
        interval: float = 60.0,
        max_failures: int = 3,
        auto_start: bool = False,
    ) -> str:
        """
        Register a new daemon worker.

        Args:
            name: Human-friendly worker name
            handler: Callable invoked every `interval` seconds
            interval: Seconds between handler calls (minimum 5)
            max_failures: Consecutive failures before auto-stop
            auto_start: Start the worker immediately after registration

        Returns:
            worker_id (UUID string)
        """
        if len(self._workers) >= self._max_workers:
            raise RuntimeError(f"Maximum daemon workers ({self._max_workers}) reached")

        if interval < 5:
            interval = 5  # Minimum 5-second interval

        worker_id = f"daemon-{uuid.uuid4().hex[:8]}"
        worker = DaemonWorker(
            worker_id=worker_id,
            name=name,
            handler=handler,
            interval=interval,
            max_failures=max_failures,
        )

        with self._lock:
            self._workers[worker_id] = worker

        logger.info(f"[DaemonRegistry] Registered worker '{name}' ({worker_id}), interval={interval}s")

        if auto_start:
            self.start(worker_id)

        return worker_id

    def start(self, worker_id: str) -> bool:
        """Start a registered worker."""
        worker = self._workers.get(worker_id)
        if not worker:
            logger.error(f"[DaemonRegistry] Cannot start unknown worker: {worker_id}")
            return False

        if worker.state == DaemonState.RUNNING:
            logger.warning(f"[DaemonRegistry] Worker {worker_id} already running")
            return True

        worker._stop_event.clear()
        worker.failure_count = 0
        worker.state = DaemonState.RUNNING
        worker.started_at = time.time()
        worker.stopped_at = None

        thread = threading.Thread(
            target=self._worker_loop,
            args=(worker_id,),
            daemon=True,
            name=f"daemon-{worker.name}",
        )
        worker._thread = thread
        thread.start()

        logger.info(f"[DaemonRegistry] Started worker '{worker.name}' ({worker_id})")
        return True

    def stop(self, worker_id: str) -> bool:
        """Signal a worker to stop gracefully."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False

        if worker.state != DaemonState.RUNNING:
            return True

        worker._stop_event.set()
        worker.state = DaemonState.STOPPED
        worker.stopped_at = time.time()

        logger.info(f"[DaemonRegistry] Stopped worker '{worker.name}' ({worker_id})")
        return True

    def unregister(self, worker_id: str) -> bool:
        """Stop and remove a worker."""
        self.stop(worker_id)
        with self._lock:
            return self._workers.pop(worker_id, None) is not None

    def get(self, worker_id: str) -> Optional[dict]:
        """Get worker status."""
        worker = self._workers.get(worker_id)
        return worker.to_dict() if worker else None

    def list_workers(self, state_filter: Optional[str] = None) -> list[dict]:
        """List all workers, optionally filtered by state."""
        workers = self._workers.values()
        if state_filter:
            try:
                target_state = DaemonState(state_filter)
                workers = [w for w in workers if w.state == target_state]
            except ValueError:
                pass
        return [w.to_dict() for w in workers]

    def count(self, state_filter: Optional[str] = None) -> int:
        """Count workers, optionally by state."""
        if state_filter:
            try:
                target_state = DaemonState(state_filter)
                return sum(1 for w in self._workers.values() if w.state == target_state)
            except ValueError:
                return 0
        return len(self._workers)

    def stop_all(self):
        """Stop all running workers (used during shutdown)."""
        for worker_id in list(self._workers.keys()):
            self.stop(worker_id)
        logger.info("[DaemonRegistry] All workers stopped")

    def _worker_loop(self, worker_id: str):
        """Main loop for a daemon worker thread."""
        worker = self._workers.get(worker_id)
        if not worker:
            return

        logger.info(f"[Daemon:{worker.name}] Loop started, interval={worker.interval}s")

        while not worker._stop_event.is_set():
            try:
                worker.handler()
                worker.last_run = time.time()
                worker.failure_count = 0  # Reset on success
            except Exception as e:
                worker.failure_count += 1
                worker.last_error = str(e)
                logger.error(
                    f"[Daemon:{worker.name}] Handler failed "
                    f"({worker.failure_count}/{worker.max_failures}): {e}"
                )

                if worker.failure_count >= worker.max_failures:
                    worker.state = DaemonState.FAILED
                    worker.stopped_at = time.time()
                    logger.error(
                        f"[Daemon:{worker.name}] Max failures reached, stopping"
                    )
                    return

            # Wait for interval or stop signal
            worker._stop_event.wait(timeout=worker.interval)

        logger.info(f"[Daemon:{worker.name}] Loop ended")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_registry: Optional[DaemonRegistry] = None


def get_daemon_registry() -> DaemonRegistry:
    global _registry
    if _registry is None:
        _registry = DaemonRegistry()
    return _registry
