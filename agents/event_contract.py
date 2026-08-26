"""Stable event envelope shared by streaming and persistence adapters."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def stable_event(run_id: str, seq: int, event_type: str,
                 payload: dict[str, Any] | None = None, *,
                 timestamp: str | None = None) -> dict[str, Any]:
    """Build the canonical event shape without changing renderer-facing fields."""
    return {
        "type": str(event_type or "status"),
        "run_id": str(run_id),
        "seq": int(seq),
        "ts": timestamp or datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload or {}),
    }


def enrich_delta(run_id: str, seq: int, delta: dict[str, Any], *,
                 event_type: str | None = None) -> dict[str, Any]:
    """Attach the canonical envelope while preserving renderer-facing fields.

    Provider adapters emit OpenAI-compatible delta dictionaries.  Keeping the
    envelope beside those fields lets older clients continue to render while
    newer clients can correlate events across transports and persisted history.
    """
    event = stable_event(
        run_id,
        seq,
        event_type or str(delta.get("type") or "message"),
        delta,
    )
    enriched = dict(delta)
    enriched.update({
        "run_id": event["run_id"],
        "seq": event["seq"],
        "event_ts": event["ts"],
        "event": event,
    })
    return enriched
