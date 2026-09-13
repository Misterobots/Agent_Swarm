"""Regression coverage for preserving direct-task execution modes on retry."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

pytest.importorskip("prometheus_client")

import main
import swarm_run_local_store
import swarm_run_repo_store
import swarm_run_store


def test_retry_preserves_plan_and_research_modes(monkeypatch):
    calls = {}
    monkeypatch.setattr(main, "TASKS_DIRECT_CREATE_ENABLED", True)
    monkeypatch.setattr(main, "_resolve_owner_id", lambda *_args: "alice")
    monkeypatch.setattr(
        swarm_run_store,
        "get_run",
        lambda *_args: {
            "coordination_id": "run-1",
            "owner_id": "alice",
            "status": "failed",
            "prompt": "review the changes",
            "ultraplan_mode": True,
            "research_mode": True,
        },
    )
    monkeypatch.setattr(swarm_run_repo_store, "get", lambda *_args: None)
    monkeypatch.setattr(swarm_run_local_store, "get", lambda *_args: None)
    monkeypatch.setattr(
        main,
        "_schedule_direct_task",
        lambda **kwargs: calls.update(kwargs) or "coord-retry",
    )
    monkeypatch.setattr(swarm_run_store, "record_event", lambda *args, **kwargs: None)

    response = TestClient(main.app).post(
        "/v1/tasks/run-1/retry",
        headers={"X-authentik-uid": "alice"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "coordination_id": "coord-retry",
        "retried_from": "run-1",
    }
    assert calls["ultraplan_mode"] is True
    assert calls["research_mode"] is True
