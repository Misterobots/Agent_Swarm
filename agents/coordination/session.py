"""CoordinatorSession and worker lifecycle tracking."""

import queue
import threading
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

from coordination.pioneers import _pioneer_for_role, _pick_unique_pioneer

SCRATCHPAD_ROOT = Path(__file__).parent.parent / "scratchpad"


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

    def __init__(self, session_id: str, owner_id: str = None):
        self.session_id = session_id
        self.owner_id = owner_id
        self.coordination_id = f"coord-{uuid.uuid4().hex[:8]}"
        self.workers: dict[str, WorkerInfo] = {}
        self.scratchpad_dir = SCRATCHPAD_ROOT / session_id / self.coordination_id
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        self.created_at = time.time()
        # Thread-safe queue for file_change events emitted by worker threads.
        # The SSE generator drains this between future-wait timeouts so chips
        # appear in the UI as files are written, not just at the end of a phase.
        self.file_change_queue: queue.Queue = queue.Queue()

    def register_worker(self, role: str, task: str, phase: str) -> str:
        worker_id = f"w-{uuid.uuid4().hex[:6]}"
        used_names = {w.pioneer["name"] for w in self.workers.values()}
        pioneer = _pick_unique_pioneer(role, used_names)
        self.workers[worker_id] = WorkerInfo(worker_id, role, task, phase, pioneer=pioneer)
        return worker_id

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
