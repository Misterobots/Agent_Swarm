"""
file_change_sink.py — shared thread-local file_change SSE sink.

Both tools/file_ops (host fs / swarm path) and tools/sandbox_ops (Docker dev
sandbox / dev-harness path) emit file_change events through this single sink so
the SSE generator can surface inline activity chips — now optionally with a
unified `diff`.  The sink must be non-blocking (put() onto a queue, never yield).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

_sink = threading.local()


def set_file_change_sink(sink: Optional[Callable[[dict], None]]) -> None:
    """Register (or clear, with None) the file_change callback for this thread."""
    _sink.callback = sink


def emit_file_change(op: str, path: str, size: int, diff: Optional[str] = None) -> None:
    """Fire a file_change event if a sink is registered for this thread.

    op   — "created" | "modified" | "deleted"
    diff — optional unified diff (edit_file supplies it; write_file does not)
    """
    cb = getattr(_sink, "callback", None)
    if not callable(cb):
        return
    payload: dict = {"op": op, "path": path, "size": size}
    if diff is not None:
        payload["diff"] = diff
    try:
        cb({"type": "file_change", "content": payload})
    except Exception:
        pass  # sink errors must never break the tool call
