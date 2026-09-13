"""Pure contract tests for the proposed learning.v1 foundation."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from learning_contract import (  # noqa: E402
    EVENT_SCHEMA,
    IdempotencyConflict,
    LearningContractError,
    make_event,
    request_fingerprint,
    require_scope,
    require_uuid,
    validate_budgets,
    validate_job_spec,
    validate_transition,
)


def _spec(**overrides):
    spec = {
        "job_id": str(uuid4()),
        "owner_id": "alice",
        "workspace_id": "memex-core",
        "kind": "sft",
    }
    spec.update(overrides)
    return spec


def test_job_spec_requires_owner_and_workspace_scope():
    with pytest.raises(LearningContractError):
        validate_job_spec(_spec(owner_id=""))
    with pytest.raises(LearningContractError):
        validate_job_spec(_spec(workspace_id=None))


def test_job_spec_rejects_non_uuid_job_and_unknown_kind():
    with pytest.raises(LearningContractError):
        validate_job_spec(_spec(job_id="legacy-1"))
    with pytest.raises(LearningContractError):
        validate_job_spec(_spec(kind="unknown"))


def test_uuid_and_scope_helpers_do_not_invent_defaults():
    value = uuid4()
    assert require_uuid(value, "job_id") == str(value)
    assert require_scope(" alice ", "owner_id") == "alice"
    with pytest.raises(LearningContractError):
        require_scope(None, "owner_id")


def test_fingerprint_is_order_independent_and_changes_with_payload():
    left = request_fingerprint({"b": 2, "a": [1, 2]})
    right = request_fingerprint({"a": [1, 2], "b": 2})
    changed = request_fingerprint({"a": [1, 3], "b": 2})
    assert left == right
    assert left.startswith("sha256:")
    assert left != changed


def test_status_transitions_are_conservative():
    validate_transition("queued", "running")
    validate_transition("running", "retry_wait")
    validate_transition("running", "completed")
    validate_transition("running", "running")
    with pytest.raises(LearningContractError):
        validate_transition("completed", "running")


def test_event_envelope_has_cursor_and_schema():
    job_id = uuid4()
    event = make_event(
        job_id=job_id,
        event_seq=7,
        kind="progress",
        phase="training",
        payload={"current": 3, "total": 10},
    )
    assert event["schema"] == EVENT_SCHEMA
    assert event["job_id"] == str(job_id)
    assert event["event_seq"] == 7
    assert event["payload"]["current"] == 3
    assert UUID(event["event_id"]).int != 0


def test_event_rejects_negative_cursor_and_unknown_phase():
    with pytest.raises(LearningContractError):
        make_event(job_id=uuid4(), event_seq=-1, kind="x", phase="queued")
    with pytest.raises(LearningContractError):
        make_event(job_id=uuid4(), event_seq=0, kind="x", phase="not-a-phase")


def test_idempotency_conflict_is_a_distinct_contract_error():
    assert issubclass(IdempotencyConflict, LearningContractError)


def test_budgets_are_normalized_and_bounded():
    value = validate_budgets({
        "window_timezone": "America/Chicago",
        "max_wall_clock_sec": 60.0,
        "checkpoint_target_sec": 30,
        "max_retries": 2,
        "deadline_at": "2026-09-14T06:00:00Z",
    })
    assert value["max_wall_clock_sec"] == 60
    assert value["checkpoint_target_sec"] == 30

    with pytest.raises(LearningContractError):
        validate_budgets({"max_wall_clock_sec": True})
    with pytest.raises(LearningContractError):
        validate_budgets({"max_retries": -1})
    with pytest.raises(LearningContractError):
        validate_budgets({"deadline_at": "tomorrow"})
