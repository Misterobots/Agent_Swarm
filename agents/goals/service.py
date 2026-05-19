"""
Goals service — lifecycle management (ensure, update usage, complete).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from . import store as goals_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_goal(thread_id: str, objective: str, owner_id: str = "") -> dict:
    """Return the active goal for this thread, creating one if none exists."""
    existing = goals_store.get_active_by_thread(thread_id, owner_id)
    if existing:
        return existing

    now = _now()
    goal = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "owner_id": owner_id,
        "objective": objective[:220],   # spec: keep concise
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "tokens_used": 0,
        "time_used_seconds": 0,
    }
    goals_store.create_goal(goal)
    return goal


def update_usage(goal_id: str, delta_tokens: int, delta_seconds: int) -> None:
    goals_store.update_usage(goal_id, delta_tokens, delta_seconds, _now())


def pause_goal(goal_id: str) -> None:
    goals_store.set_status(goal_id, "paused", _now())


def complete_goal(goal_id: str) -> None:
    now = _now()
    goals_store.set_status(goal_id, "complete", now, completed_at=now)
