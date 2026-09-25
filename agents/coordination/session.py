"""CoordinatorSession and worker lifecycle tracking."""

import queue
import threading
import time
import uuid
import weakref
import json
import hashlib
from enum import Enum
from pathlib import Path
from typing import Optional

from coordination.pioneers import _pioneer_for_role, _pick_unique_pioneer
from role_model_resolver import (
    RoleModelBinding, RoleModelSnapshot, canonical_role, snapshot_role_models,
)

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

    def __init__(self, worker_id: str, role: str, task: str, phase: str,
                 pioneer: dict | None = None, model_binding: RoleModelBinding | None = None):
        self.worker_id = worker_id
        self.role = role
        self.task = task
        self.phase = phase
        self.pioneer: dict = pioneer or _pioneer_for_role(role)
        self.model_binding = model_binding
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

    def __init__(self, session_id: str, owner_id: str = None, coordination_id: str = None,
                 context_profile: str | None = None, selected_model: str | None = None,
                 team_builder_roles: bool = False, role_models: dict | None = None):
        self.session_id = session_id
        self.owner_id = owner_id
        # Per-run model source, decided by the user at send time. False (the
        # default) binds every role to selected_model; True keeps the owner's
        # Team Builder assignments. Stored on the session so a resumed run reads
        # back the same choice it started with.
        self.selected_model = selected_model
        self.team_builder_roles = bool(team_builder_roles)
        # Explicit role→model map from the desktop's routing table. Wins over
        # both sources above when the request carries one.
        self.role_models = dict(role_models) if role_models else {}
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
        self.role_snapshot, self.context_profile = self._load_or_create_role_snapshot(context_profile)
        # Thread-safe queue for file_change events emitted by worker threads.
        # The SSE generator drains this between future-wait timeouts so chips
        # appear in the UI as files are written, not just at the end of a phase.
        self.file_change_queue: queue.Queue = queue.Queue()
        # Cooperative cancellation for task lifecycle STOP. Worker/model calls
        # cannot always be interrupted safely, so the orchestrator checks this
        # flag at phase boundaries and workers check it before committing output.
        self.cancel_flag = threading.Event()
        # Accumulated file_change payloads ({op, path, size, diff?}) across all
        # phases — joined into the run's aggregate diff for the mobile task board.
        self.file_changes: list[dict] = []
        # Publish to the live registry for Agent View. Best-effort — monitoring
        # must never break coordination.
        try:
            _ACTIVE_SESSIONS[self.coordination_id] = self
        except Exception:
            pass

    def _role_snapshot_path(self) -> Path:
        """Return an owner-keyed checkpoint path within this run's scratchpad."""
        owner_key = str(self.owner_id) if self.owner_id is not None else "anonymous"
        digest = hashlib.sha256(owner_key.encode("utf-8")).hexdigest()[:16]
        return self.scratchpad_dir / f"00_role_model_snapshot_{digest}.json"

    def _load_or_create_role_snapshot(
        self, requested_context_profile: str | None,
    ) -> tuple[RoleModelSnapshot, str | None]:
        """Restore a checkpointed role map, or capture it exactly once."""
        path = self._role_snapshot_path()
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                restored = RoleModelSnapshot.from_dict(payload)
                # The coordination id is not an owner boundary.  A caller
                # supplying another owner's id must never inherit its map.
                if restored.owner_id == self.owner_id and restored.models:
                    return restored, restored.context_profile
        except Exception:
            # A corrupt optional checkpoint must not prevent a run from starting.
            pass
        snapshot = snapshot_role_models(
            self.owner_id, requested_context_profile,
            selected_model=self.selected_model, team_builder_roles=self.team_builder_roles,
            role_models=self.role_models,
        )
        try:
            path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        except Exception:
            pass
        return snapshot, snapshot.context_profile

    def model_binding_for_role(self, role: str):
        return self.role_snapshot.for_role(role)

    def model_for_role(self, role: str, default: str | None = None) -> str:
        # This is the requested model used to start a stage.  Provider fallback
        # metadata is carried separately so a resumed run never turns a prior
        # fallback into its new preset.
        return self.role_snapshot.for_role(role, default=default).requested_model

    def model_metadata_for_role(self, role: str) -> dict[str, object]:
        return self.role_snapshot.for_role(role).to_dict()

    def register_worker(self, role: str, task: str, phase: str) -> str:
        worker_id = f"w-{uuid.uuid4().hex[:6]}"
        used_names = {w.pioneer["name"] for w in self.workers.values()}
        pioneer = _pick_unique_pioneer(role, used_names)
        binding = self.model_binding_for_role(canonical_role(role))
        self.workers[worker_id] = WorkerInfo(
            worker_id, role, task, phase, pioneer=pioneer, model_binding=binding,
        )
        return worker_id

    def cancel(self) -> None:
        """Request cancellation for this coordination and all known workers."""
        self.cancel_flag.set()
        for worker in list(self.workers.values()):
            worker.cancel()

    def is_cancelled(self) -> bool:
        return self.cancel_flag.is_set()

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
        "model": w.model_binding.to_dict() if w.model_binding else None,
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


def get_active_session(coordination_id: str) -> CoordinatorSession | None:
    """Return the live session for cooperative task cancellation, if present."""
    if not coordination_id:
        return None
    try:
        return _ACTIVE_SESSIONS.get(coordination_id)
    except Exception:
        return None
