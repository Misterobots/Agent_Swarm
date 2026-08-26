"""Endpoint-level checks for the desktop backend handoff contract."""

import os
import sys
import asyncio

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
pytest.importorskip("prometheus_client")

import main
import swarm_run_repo_store
import swarm_run_store
from dev_harness.history import History
from dev_harness.replay_policy import public_call, validate_next
from mcp.server import MCPBridgeServer


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


def test_replay_policy_preserves_order_and_hides_arguments():
    call = {
        "call_id": "c1", "name": "web_search", "args": {"query": "private"},
        "category": "mcp", "source": "mcp", "replayable": True,
    }
    public = public_call(call)
    assert public["name"] == "web_search"
    assert public["args"] == {}
    assert "private" not in str(public)
    assert validate_next(
        pending=[call], call_id="c1", owner_id="alice", requested_owner_id="alice",
        permission_mode="default", is_admin=False, confirm=True,
    ) == (True, "")
    allowed, reason = validate_next(
        pending=[call], call_id="later", owner_id="alice", requested_owner_id="alice",
        permission_mode="default", is_admin=False, confirm=True,
    )
    assert not allowed
    assert "c1" in reason


def test_mcp_capabilities_are_registered_and_implemented():
    server = MCPBridgeServer()
    health = server.health()
    assert health["transports"] == ["http", "sse", "websocket", "stdio"]
    assert health["resources_registered"] == 2
    assert health["prompts_registered"] == 2
    assert health["capabilities"]["resources"]["listChanged"] is False
    config = server.client_config("https://runtime.example")
    descriptors = config["mcpServers"]
    assert descriptors[server.server_name]["transport"] == "http"
    assert descriptors[f"{server.server_name}-sse"]["transport"] == "sse"
    assert descriptors[f"{server.server_name}-websocket"]["transport"] == "websocket"
    assert descriptors[f"{server.server_name}-stdio"]["transport"] == "stdio"
    assert descriptors[server.server_name]["capabilities"] == health["capabilities"]
    resources = asyncio.run(server.handle_rpc("resources/list", {}))
    assert len(resources["resources"]) == 2
    prompt = asyncio.run(server.handle_rpc(
        "prompts/get", {"name": "memex.research", "arguments": {"query": "q"}}
    ))
    assert prompt["messages"][0]["content"]["text"].endswith("\n\nq")


def test_checkpoint_replay_dispatches_read_only_mcp_in_order(monkeypatch):
    import dev_harness.checkpoints as checkpoints

    history = History(system="system", turns=[]).to_checkpoint()
    pending = [
        {"call_id": "c1", "name": "web_search", "tool_name": "web_search",
         "args": {"query": "q"}, "category": "mcp", "replayable": True},
        {"call_id": "c2", "name": "web_fetch", "tool_name": "web_fetch",
         "args": {"url": "https://example.invalid"}, "category": "mcp", "replayable": True},
    ]
    row = {"session_id": "session-1", "status": "recovery_required", "turn": 1,
           "data": {"history": history, "pending_tools": pending, "permission_mode": "default"}}
    saved = {}
    monkeypatch.setattr(checkpoints, "get_checkpoint", lambda *_args: row)
    monkeypatch.setattr(
        checkpoints, "save_checkpoint",
        lambda _owner, _session, **kwargs: saved.update(kwargs) or True,
    )
    monkeypatch.setattr(main, "_run_mcp_tool", lambda _uid, name, _args: f"{name}-ok")
    client = TestClient(main.app)

    out_of_order = client.post(
        "/api/v1/dev/checkpoints/session-1/replay",
        json={"call_id": "c2", "confirm": True},
        headers={"X-authentik-uid": "alice"},
    )
    assert out_of_order.status_code == 409
    assert "c1" in out_of_order.json()["detail"]

    replayed = client.post(
        "/api/v1/dev/checkpoints/session-1/replay",
        json={"call_id": "c1", "confirm": True},
        headers={"X-authentik-uid": "alice"},
    )
    assert replayed.status_code == 200
    assert replayed.json()["output"] == "web_search-ok"
    assert replayed.json()["next_call_id"] == "c2"
    assert saved["status"] == "recovery_required"


def test_task_stop_is_owner_scoped_and_cooperative(monkeypatch):
    import coordination.session as session_module

    run = {"coordination_id": "run-stop", "owner_id": "alice", "status": "running"}
    cancelled = {}

    class Active:
        def __init__(self):
            self.called = False

        def cancel(self):
            self.called = True

    active = Active()
    monkeypatch.setattr(main, "_resolve_owner_id", lambda *_args: "alice")
    monkeypatch.setattr(swarm_run_store, "get_run", lambda *_args: dict(run))
    monkeypatch.setattr(swarm_run_store, "cancel_run", lambda *args: cancelled.setdefault("args", args) or True)
    monkeypatch.setattr(session_module, "get_active_session", lambda *_args: active)
    client = TestClient(main.app)

    response = client.post("/v1/tasks/run-stop/stop", headers={"X-authentik-uid": "alice"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "cancelled"}
    assert active.called
    assert cancelled["args"] == ("run-stop", "alice")
