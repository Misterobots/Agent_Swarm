"""Focused regression coverage for the backend parity contracts."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

from dev_harness.approval_service import arguments_hash, request_approval
from dev_harness.loop import _call_category
from dev_harness.permissions import PermissionGate
from dev_harness.replay_policy import public_call, validate_next
from coordination.workspace_lifecycle import _safe
from mcp.server import MCPBridgeServer


def test_permission_mode_matrix_is_fail_closed():
    assert PermissionGate("plan").check("read_file")[0]
    assert not PermissionGate("plan").check("write_file")[0]
    assert PermissionGate("acceptEdits").auto_approve("write_file")
    assert not PermissionGate("acceptEdits").check("run_command")[0]
    assert not PermissionGate("bypass", is_admin=False).check("run_command")[0]
    assert PermissionGate("bypass", is_admin=True).check("run_command")[0]


def test_ordered_replay_rejects_future_and_cross_owner_calls():
    pending = [
        {"call_id": "sandbox-1", "category": "sandbox", "approval_state": "pending"},
        {"call_id": "task-1", "category": "task", "approval_state": "pending"},
    ]
    assert validate_next(
        pending=pending, call_id="sandbox-1", owner_id="alice",
        requested_owner_id="alice", permission_mode="default",
        is_admin=False, confirm=True,
    )[0]
    assert not validate_next(
        pending=pending, call_id="task-1", owner_id="alice",
        requested_owner_id="alice", permission_mode="default",
        is_admin=False, confirm=True,
    )[0]
    assert not validate_next(
        pending=pending, call_id="sandbox-1", owner_id="alice",
        requested_owner_id="bob", permission_mode="default",
        is_admin=False, confirm=True,
    )[0]


def test_task_and_mcp_categories_are_recorded():
    assert _call_category("Task")[0] == "task"
    assert _call_category("web_fetch")[0] == "mcp"
    assert _call_category("hive.remote.exec")[2] == "external"
    assert _call_category("write_file")[0] == "sandbox"


def test_public_checkpoint_metadata_redacts_arguments():
    call = {
        "category": "sandbox", "source": "dev_harness", "call_id": "c1",
        "tool_name": "write_file", "arguments": {"content": "secret"},
        "order_index": 0, "approval_state": "pending",
    }
    public = public_call(call)
    assert public["call_id"] == "c1"
    assert "arguments" not in public
    assert "content" not in public


def test_approval_hash_is_stable_without_logging_raw_arguments():
    first = arguments_hash({"token": "secret", "path": "/workspace/a"})
    second = arguments_hash({"path": "/workspace/a", "token": "secret"})
    assert first == second
    assert "secret" not in first


def test_approval_request_rejects_malformed_input_before_storage():
    assert request_approval(
        owner_id="", call_id="c1", tool_name="write_file", arguments={}
    ) is None
    assert request_approval(
        owner_id="alice", call_id="c1", tool_name="write_file",
        arguments={}, permission_mode="invalid"
    ) is None


def test_workspace_inputs_reject_traversal_and_branch_injection():
    _safe("feature/task-123", "branch")
    with pytest.raises(ValueError):
        _safe("../escape", "branch")
    with pytest.raises(ValueError):
        _safe("-c", "branch")
    with pytest.raises(ValueError):
        _safe("", "session_id")


@pytest.mark.asyncio
async def test_mcp_health_and_standard_empty_capabilities():
    server = MCPBridgeServer()
    health = server.health()
    assert health["tools_registered"] > 0
    assert health["resources_registered"] == 0
    assert health["prompts_registered"] == 0
    assert set(health["transports"]) == {"http", "sse", "websocket", "stdio"}
    assert await server.handle_rpc("resources/list", {}) == {"resources": []}
    assert await server.handle_rpc("prompts/list", {}) == {"prompts": []}
    with pytest.raises(ValueError):
        await server.handle_rpc("resources/read", {"uri": "mcp://missing"})


def test_replay_order_error_identifies_expected_call():
    ok, reason = validate_next(
        pending=[{"call_id": "first"}, {"call_id": "second"}],
        call_id="second", owner_id="alice", requested_owner_id="alice",
        permission_mode="default", is_admin=False, confirm=True,
    )
    assert not ok
    assert "expected call_id=first" in reason
