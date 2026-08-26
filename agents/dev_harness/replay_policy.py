"""Policy and ordering checks shared by checkpoint replay adapters."""
from __future__ import annotations

from typing import Any

READ_ONLY_MCP = frozenset({"web_search", "web_fetch", "hive.browser.search", "hive.browser.fetch"})
READ_ONLY_SANDBOX = frozenset({"read_file", "list_directory", "glob", "grep"})
REPLAYABLE_SANDBOX = READ_ONLY_SANDBOX | frozenset({"write_file", "run_command", "edit_file", "git"})


def category(call: dict[str, Any]) -> str:
    value = call.get("category")
    if value in {"sandbox", "task", "mcp"}:
        return value
    name = call.get("tool_name") or call.get("name")
    if name == "Task":
        return "task"
    if name in READ_ONLY_MCP or str(name).startswith("hive."):
        return "mcp"
    return "sandbox"


def replayable(call: dict[str, Any]) -> bool:
    """Return whether this recorded call has a supported explicit replay adapter."""
    if "replayable" in call:
        return bool(call["replayable"])
    name = call.get("tool_name") or call.get("name")
    kind = category(call)
    if kind == "task":
        return name == "Task"
    if kind == "mcp":
        return name in READ_ONLY_MCP
    return name in REPLAYABLE_SANDBOX


def validate_next(*, pending: list[dict[str, Any]], call_id: str,
                  owner_id: str, requested_owner_id: str,
                  permission_mode: str, is_admin: bool,
                  confirm: bool) -> tuple[bool, str]:
    if owner_id != requested_owner_id:
        return False, "call belongs to another owner"
    if not confirm:
        return False, "explicit confirmation is required"
    if not pending or not isinstance(pending[0], dict):
        return False, "checkpoint has no pending call"
    call = pending[0]
    if call.get("call_id") != call_id:
        return False, f"replay must proceed in exact recorded order; expected call_id={call.get('call_id')}"
    if call.get("approval_state") in {"completed", "denied", "failed"}:
        return False, "call is already resolved"
    if not replayable(call):
        return False, "recorded call has no supported replay adapter"
    if permission_mode == "bypass" and not is_admin:
        return False, "bypass replay requires administrator authorization"
    if category(call) == "mcp":
        name = call.get("tool_name") or call.get("name")
        if name not in READ_ONLY_MCP:
            return False, "MCP capability is not allowlisted for replay"
    return True, ""


def public_call(call: dict[str, Any]) -> dict[str, Any]:
    """Return checkpoint metadata without exposing raw arguments."""
    name = call.get("tool_name") or call.get("name")
    result = {
        key: call.get(key) for key in (
            "category", "source", "call_id", "tool_name", "side_effect_class",
            "order_index", "approval_state", "created_at", "expires_at",
        ) if key in call
    }
    # Keep the frontend's stable name/args shape without leaking the recorded
    # tool arguments into an inspection response. Replay still uses the private
    # checkpoint payload after the owner and call order have been validated.
    result.setdefault("name", name)
    result.setdefault("args", {})
    result.setdefault("replayable", replayable(call))
    return result
