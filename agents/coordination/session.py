"""CoordinatorSession and worker lifecycle tracking."""

import queue
import threading
import time
import uuid
import weakref
from enum import Enum
from pathlib import Path
from typing import Optional

from coordination.pioneers import _pioneer_for_role, _pick_unique_pioneer

SCRATCHPAD_ROOT = Path(__file__).parent.parent / "scratchpad"

# Live registry of in-flight coordination sessions, keyed by coordination_id.
# WeakValueDictionary: an entry auto-drops as soon as the session object is
# garbage-collected (i.e. when the coordinate_task generator frame that holds it
# is exhausted/closed). This gives Agent View a "currently running" view with no
# hooks in the orchestrator's many early-return paths.
_ACTIVE_SESSIONS: "weakref.WeakValueDictionary[str, 'CoordinatorSession']" = (
    weakref.WeakValueDictionary()
)


class WorkerState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerInfo:
    """Tracks a single worker's lifecycle."""

    def __init__(self, worker_id: str, role: str, task: str, phase: str, pioneer: dict | None = None):
        self.worker_id = worker_id
        self.role = role
        self.task = task
        self.phase = phase
        self.pioneer: dict = pioneer or _pioneer_for_role(role)
        self.state = WorkerState.PENDING
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.cancel_flag = threading.Event()

    def cancel(self):
        self.cancel_flag.set()
        self.state = WorkerState.CANCELLED


class CoordinatorSession:
    """Manages a single coordination session with scratchpad and worker registry."""

    def __init__(self, session_id: str, owner_id: str = None, coordination_id: str = None):
        self.session_id = session_id
        self.owner_id = owner_id
        # Direct task creation (POST /v1/tasks) generates this up front so it
        # can return the id to the caller before the generator has run at all;
        # every other caller leaves it unset and gets the usual random id.
        self.coordination_id = coordination_id or f"coord-{uuid.uuid4().hex[:8]}"
        # Name of this run's per-session Docker container (session_sandbox.py),
        # once resolved — None means "use the shared default" (either the
        # session-sandbox mechanism is off, or this run has no linked repo yet).
        self.container_name: str | None = None
        self.workers: dict[str, WorkerInfo] = {}
        self.scratchpad_dir = SCRATCHPAD_ROOT / session_id / self.coordination_id
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        self.created_at = time.time()
        # Thread-safe queue for file_change events emitted by worker threads.
        # The SSE generator drains this between future-wait timeouts so chips
        # appear in the UI as files are written, not just at the end of a phase.
        self.file_change_queue: queue.Queue = queue.Queue()
        # Cooperative cancellation requested by the owner-scoped task stop
        # endpoint.  Workers observe this between model/tool calls; the
        # orchestrator's finally block records the durable terminal state.
        self.stop_event = threading.Event()
        # Accumulated file_change payloads ({op, path, size, diff?}) across all
        # phases — joined into the run's aggregate diff for the mobile task board.
        self.file_changes: list[dict] = []
        # Publish to the live registry for Agent View. Best-effort — monitoring
        # must never break coordination.
        try:
            _ACTIVE_SESSIONS[self.coordination_id] = self
        except Exception:
            pass

    def register_worker(self, role: str, task: str, phase: str) -> str:
        worker_id = f"w-{uuid.uuid4().hex[:6]}"
        used_names = {w.pioneer["name"] for w in self.workers.values()}
        pioneer = _pick_unique_pioneer(role, used_names)
        self.workers[worker_id] = WorkerInfo(worker_id, role, task, phase, pioneer=pioneer)
        return worker_id

    def cancel(self) -> None:
        """Request cooperative cancellation for this coordination session."""
        self.stop_event.set()
        for worker in list(self.workers.values()):
            worker.cancel()

    @property
    def cancel_requested(self) -> bool:
        return self.stop_event.is_set()

    def write_to_scratchpad(self, filename: str, content: str):
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        (self.scratchpad_dir / safe_name).write_text(content, encoding="utf-8")

    def read_from_scratchpad(self, filename: str) -> Optional[str]:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        path = self.scratchpad_dir / safe_name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def list_scratchpad(self) -> list[str]:
        if not self.scratchpad_dir.exists():
            return []
        return [f.name for f in self.scratchpad_dir.iterdir() if f.is_file()]

    def get_all_scratchpad_content(self) -> str:
        if not self.scratchpad_dir.exists():
            return ""
        parts = []
        for f in sorted(self.scratchpad_dir.iterdir()):
            if f.is_file():
                parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)


# ── Agent View: live snapshot of active coordination sessions ───────────────

def _serialize_worker(w: "WorkerInfo", now: float) -> dict:
    started = w.started_at
    end = w.completed_at or now
    elapsed = round(end - started, 1) if started else None
    return {
        "worker_id": w.worker_id,
        "name": (w.pioneer or {}).get("name"),
        "role": w.role,
        "phase": w.phase,
        "state": w.state.value,
        "task": (w.task or "")[:160],
        "elapsed_s": elapsed,
        "error": w.error or None,
    }


def snapshot_active_sessions() -> list[dict]:
    """Serialize every in-flight coordination session for Agent View.

    Pure read of in-memory state; never raises (monitoring must not disturb
    coordination). Sessions are newest-first.
    """
    now = time.time()
    try:
        sessions = list(_ACTIVE_SESSIONS.values())
    except Exception:
        return []

    out = []
    for s in sessions:
        try:
            workers = [_serialize_worker(w, now) for w in list(s.workers.values())]
            states = [w["state"] for w in workers]
            out.append({
                "coordination_id": s.coordination_id,
                "session_id": s.session_id,
                "owner_id": s.owner_id,
                "created_at": s.created_at,
                "elapsed_s": round(now - s.created_at, 1),
                "worker_count": len(workers),
                "running_count": states.count("running"),
                "workers": workers,
            })
        except Exception:
            continue

    out.sort(key=lambda d: d["created_at"], reverse=True)
    return out


def cancel_active_session(coordination_id: str) -> bool:
    """Request cancellation for a live session, if it is still registered."""
    try:
        session = _ACTIVE_SESSIONS.get(coordination_id)
        if session is None:
            return False
        session.cancel()
        return True
    except Exception:
        return False
