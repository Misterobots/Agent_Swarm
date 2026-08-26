"""Stable event envelope shared by streaming and persistence adapters."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def stable_event(run_id: str, seq: int, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the canonical event shape without changing renderer-facing fields."""
    return {
        "type": str(event_type or "status"),
        "run_id": str(run_id),
        "seq": int(seq),
        "ts": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload or {}),
    }
