"""Endpoint-level checks for the desktop backend handoff contract."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
pytest.importorskip("prometheus_client")

import main
import swarm_run_repo_store
import swarm_run_store


def _patch_test(monkeypatch, status="running"):
    run = {"coordination_id": "run-1", "owner_id": "alice", "status": status,
           "title": "old", "scope": "old-scope"}
    repo = {"git_url": "https://example.invalid/repo", "branch": "main", "dev_project_id": None}
    monkeypatch.setattr(main, "_resolve_owner_id", lambda *_args: "alice")
    monkeypatch.setattr(swarm_run_store, "get_run", lambda *_args: dict(run))
    monkeypatch.setattr(swarm_run_store, "update_metadata", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(swarm_run_store, "get_workers", lambda *_args: [])
    monkeypatch.setattr(swarm_run_repo_store, "get", lambda *_args: dict(repo))
    monkeypatch.setattr(swarm_run_repo_store, "update_branch", lambda *_args: True)
    return TestClient(main.app)


def test_task_patch_accepts_only_owner_scoped_mutable_metadata(monkeypatch):
    client = _patch_test(monkeypatch)
    response = client.patch("/v1/tasks/run-1", json={
        "title": "new", "scope": "new-scope", "branch": "feature/work", "prompt": "resume",
    }, headers={"X-authentik-uid": "alice"})
    assert response.status_code == 200
    assert response.json()["run"]["coordination_id"] == "run-1"
    assert response.json()["workers"] == []
    rejected = client.patch("/v1/tasks/run-1", json={"status": "completed"})
    assert rejected.status_code == 422


def test_task_patch_rejects_terminal_runs(monkeypatch):
    client = _patch_test(monkeypatch, status="completed")
    response = client.patch("/v1/tasks/run-1", json={"title": "late"})
    assert response.status_code == 409
