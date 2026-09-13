"""Pure helpers and invariants for the proposed ``learning.v1`` contract.

This module intentionally has no database, network, GPU, or process side
effects.  It is the shared validation layer for the future durable store and
API adapters.  The adapter must reject invalid scope/identifiers rather than
falling back to a global or in-memory job state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4


CONTRACT_VERSION = "learning.v1"
EVENT_SCHEMA = "learning.event.v1"

STATUSES = frozenset({
    "queued", "running", "paused", "retry_wait", "blocked", "failed",
    "cancelled", "completed",
})

PHASES = frozenset({
    "queued", "preflight", "preparing", "training", "checkpointing",
    "evaluating", "exporting", "awaiting_review", "restoring", "done",
})

JOB_KINDS = frozenset({
    "sft", "preference", "rl", "harness_adaptation", "dataset_prepare",
    "evaluation", "export",
})

TERMINAL_STATUSES = frozenset({"failed", "cancelled", "completed"})

# This is deliberately conservative.  A future control adapter can add an
# explicit migration for any transition not listed here; silently permitting
# arbitrary transitions would make recovery and UI state ambiguous.
ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "paused", "blocked", "cancelled"}),
    "running": frozenset({"paused", "retry_wait", "blocked", "failed", "cancelled", "completed"}),
    "paused": frozenset({"queued", "running", "cancelled", "blocked"}),
    "retry_wait": frozenset({"queued", "running", "blocked", "failed", "cancelled"}),
    "blocked": frozenset({"queued", "cancelled"}),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "completed": frozenset(),
}


class LearningContractError(ValueError):
    """Input violates a learning.v1 invariant."""


class IdempotencyConflict(LearningContractError):
    """An idempotency key was reused for a different request fingerprint."""


def require_scope(value: str | None, field: str) -> str:
    """Require a non-empty owner/workspace scope value.

    The caller must resolve the authenticated owner before invoking this
    helper.  There is intentionally no ``"default"`` or ``"anonymous"``
    fallback for learning jobs.
    """

    normalized = str(value or "").strip()
    if not normalized:
        raise LearningContractError(f"{field} is required for learning.v1")
    return normalized


def require_uuid(value: str | UUID | None, field: str) -> str:
    """Return a canonical UUID string or reject the identifier."""

    if value is None or str(value).strip() == "":
        raise LearningContractError(f"{field} is required for learning.v1")
    try:
        return str(UUID(str(value)))
    except (AttributeError, ValueError, TypeError) as exc:
        raise LearningContractError(f"{field} must be a UUID") from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_fingerprint(payload: Mapping[str, Any]) -> str:
    """Hash a canonical JSON request for idempotency comparison."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_job_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the durable portion of a job creation spec."""

    normalized = dict(spec)
    normalized["job_id"] = require_uuid(normalized.get("job_id"), "job_id")
    normalized["owner_id"] = require_scope(normalized.get("owner_id"), "owner_id")
    normalized["workspace_id"] = require_scope(normalized.get("workspace_id"), "workspace_id")

    for optional_id in ("experiment_id", "parent_id", "session_id"):
        if optional_id in normalized and normalized[optional_id] is not None:
            if optional_id == "session_id":
                normalized[optional_id] = require_scope(normalized[optional_id], optional_id)
            else:
                normalized[optional_id] = require_uuid(normalized[optional_id], optional_id)

    kind = str(normalized.get("kind") or "").strip()
    if kind not in JOB_KINDS:
        raise LearningContractError(f"unsupported learning job kind: {kind or '<empty>'}")
    normalized["kind"] = kind

    status = str(normalized.get("status") or "queued")
    phase = str(normalized.get("phase") or "queued")
    if status not in STATUSES:
        raise LearningContractError(f"unsupported learning status: {status}")
    if phase not in PHASES:
        raise LearningContractError(f"unsupported learning phase: {phase}")
    normalized["status"] = status
    normalized["phase"] = phase
    return normalized


def validate_transition(current: str, target: str) -> None:
    """Reject an unapproved durable status transition."""

    if current not in STATUSES or target not in STATUSES:
        raise LearningContractError("unknown learning status")
    if current == target:
        return
    if target not in ALLOWED_STATUS_TRANSITIONS[current]:
        raise LearningContractError(f"invalid learning transition: {current} -> {target}")


def make_event(
    *,
    job_id: str | UUID,
    event_seq: int,
    kind: str,
    phase: str,
    payload: Mapping[str, Any] | None = None,
    experiment_id: str | UUID | None = None,
    attempt_id: str | UUID | None = None,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Build the stable event envelope used by API and desktop consumers."""

    if int(event_seq) < 0:
        raise LearningContractError("event_seq must be non-negative")
    if phase not in PHASES:
        raise LearningContractError(f"unsupported learning phase: {phase}")
    if not kind.strip():
        raise LearningContractError("event kind is required")

    event = {
        "schema": EVENT_SCHEMA,
        "event_id": str(uuid4()),
        "job_id": require_uuid(job_id, "job_id"),
        "experiment_id": str(experiment_id) if experiment_id else None,
        "attempt_id": str(attempt_id) if attempt_id else None,
        "event_seq": int(event_seq),
        "kind": kind.strip(),
        "phase": phase,
        "occurred_at": occurred_at or utc_now(),
        "payload": dict(payload or {}),
    }
    return event
