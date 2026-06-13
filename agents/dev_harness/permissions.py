"""
permissions.py — the dev-harness permission gate.

Phase 1 scope: **plan mode** — a read-only restriction.  While plan mode is
active the harness allows only read/search tools (and the meta tools
TodoWrite/Task) and blocks every mutating tool, so the model must present a
plan and wait for the user to approve it (turn plan mode off) before editing.

Phase 2 will extend this gate with risk tiers (bash_classifier) and the
acceptEdits / bypass permission modes; the `mode` field is already shaped for
that so the wiring doesn't change.
"""

from __future__ import annotations

# Tools that never mutate the workspace — always allowed, even in plan mode
# (incl. web research, which is read-only with respect to /workspace).
READ_ONLY_TOOLS = frozenset({
    "read_file", "list_directory", "glob", "grep", "web_search", "web_fetch",
})
# Harness meta tools always allowed in plan mode (pure planning, no mutations).
# NOTE: Task is intentionally NOT here — a subagent can make changes, so plan
# mode must block it too.
META_TOOLS = frozenset({"TodoWrite"})

_VALID_MODES = ("default", "plan", "acceptEdits", "bypass")


class PermissionGate:
    def __init__(self, mode: str = "default"):
        self.mode = mode if mode in _VALID_MODES else "default"

    @property
    def plan_mode(self) -> bool:
        return self.mode == "plan"

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Return (allowed, reason).  reason is shown to the model when blocked."""
        if self.mode == "plan" and tool_name not in READ_ONLY_TOOLS and tool_name not in META_TOOLS:
            return False, (
                f"🛑 Plan mode is active — `{tool_name}` is blocked. Investigate with "
                "read/glob/grep, record your steps with TodoWrite, then present your plan "
                "and ask the user to approve it (turn off plan mode) before making changes."
            )
        return True, ""
