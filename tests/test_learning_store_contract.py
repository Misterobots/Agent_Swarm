"""Pure store-shape tests; no database or live service use."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from learning_store import LearningStore  # noqa: E402


def test_snapshot_defaults_preserve_budget_and_event_cursor():
    snapshot = LearningStore._snapshot_defaults({
        "job_id": str(uuid4()),
        "owner_id": "alice",
        "workspace_id": "memex-core",
        "kind": "sft",
        "budgets": {"max_wall_clock_sec": 120.0},
    })
    assert snapshot["budgets"] == {"max_wall_clock_sec": 120}
    assert snapshot["event_cursor"] == -1
    assert snapshot["resource"]["eligibility"] == "pending"


def test_event_row_round_trip_keeps_experiment_scope():
    event = LearningStore._row_to_event({
        "event_id": str(uuid4()),
        "job_id": str(uuid4()),
        "experiment_id": str(uuid4()),
        "attempt_id": None,
        "event_seq": 4,
        "kind": "progress",
        "phase": "training",
        "payload": {"current": 2},
        "occurred_at": datetime(2026, 9, 13, tzinfo=timezone.utc),
    })
    assert event["experiment_id"]
    assert event["event_seq"] == 4
    assert event["occurred_at"].startswith("2026-09-13T00:00:00")


def test_mutable_snapshot_fields_are_explicit():
    assert "budgets" in LearningStore.MUTABLE_SNAPSHOT_FIELDS
    assert "event_cursor" not in LearningStore.MUTABLE_SNAPSHOT_FIELDS
    assert "owner_id" not in LearningStore.MUTABLE_SNAPSHOT_FIELDS
