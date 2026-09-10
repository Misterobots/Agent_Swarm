"""User-safe activity narration for the desktop DevHarness stream.

These messages describe observable harness state and the next tool action. They
are not model scratchpad or hidden chain-of-thought.
"""

from __future__ import annotations

from typing import Any


_TOOL_ACTIONS = {
    "list_directory": "inspect the workspace structure",
    "read_file": "read the relevant project files",
    "write_file": "create the requested project file",
    "edit_file": "apply the requested code change",
    "glob": "locate matching project files",
    "grep": "search the project for relevant code",
    "run_command": "run a project command",
    "git": "check the repository state",
    "web_search": "look up supporting information",
    "web_fetch": "read the selected reference",
    "kb_search": "check the project knowledge base",
    "TodoWrite": "update the task plan",
    "Task": "delegate a focused subtask",
}


def initial_activity_events() -> list[dict[str, object]]:
    """Start one durable Code-agent presence and a safe work narrative."""
    return [
        {
            "type": "agent_event", "worker_id": "code-agent",
            "agent_name": "Code agent", "role": "coding agent",
            "task": "Reviewing the selected workspace", "event_type": "status",
            "content": "Code agent started the workspace review.",
        },
        {
            "type": "thought", "agent_name": "Code agent", "safe_summary": True,
            "content": "I’m reviewing the selected workspace before making changes.",
        },
        {"type": "status", "content": "Planning the first verifiable step."},
    ]


def completed_activity_event() -> dict[str, object]:
    return {
        "type": "agent_event", "worker_id": "code-agent",
        "agent_name": "Code agent", "role": "coding agent",
        "event_type": "completed", "content": "Code agent completed this turn.",
    }


def _command_action(arguments: dict[str, Any] | None) -> str:
    """Describe a command's observable purpose without echoing its source."""
    command = str((arguments or {}).get("command") or "").lower()
    if "command -v " in command or "which " in command or "where " in command:
        return "check which project runtime is available"
    if "python" in command and (" -m " in command or "-m" in command):
        return "run the project’s Python tooling"
    if "pip install" in command or "uv pip" in command:
        return "prepare a project-local dependency setup"
    if "git " in command:
        return "inspect the repository state"
    if "test" in command or "pytest" in command or "vitest" in command:
        return "run the relevant project checks"
    return _TOOL_ACTIONS["run_command"]


def _result_narrative(tool_name: str, output: str | None) -> str:
    """Produce an execution summary from known tool outcomes, never raw output."""
    if tool_name != "run_command":
        return f"Completed {tool_name}; reviewing the result."
    lower = (output or "").lower()
    if "command not found" in lower or "not recognized as" in lower:
        return "The requested executable is unavailable in this workspace. I’ll use the available project runtime."
    if "no module named" in lower or "modulenotfounderror" in lower:
        return "The available runtime is missing a required project module. I’ll check the project’s supported setup."
    if "externally-managed-environment" in lower or "break-system-packages" in lower:
        return "The system Python cannot be modified here. I’ll use a project-local environment instead."
    if "exit " in lower or "traceback" in lower or "error:" in lower:
        return "The command did not complete successfully. I’ll inspect the failure and adjust the next step."
    return "The command completed; reviewing what it reported before the next step."


def tool_activity_events(
    tool_name: str | None,
    phase: str,
    arguments: dict[str, Any] | None = None,
    output: str | None = None,
) -> list[dict[str, object]]:
    """Return small, user-readable lifecycle events for one tool call.

    ``phase`` is ``start`` or ``result``. Unknown tools retain their name so
    the stream never becomes a vague, empty spinner.
    """
    name = (tool_name or "tool").strip() or "tool"
    action = _command_action(arguments) if name == "run_command" else _TOOL_ACTIONS.get(name, name.replace("_", " "))
    if phase == "start":
        return [
            {"type": "thought", "safe_summary": True, "content": f"Next, I’ll {action}."},
            {"type": "status", "content": f"Working: {action}."},
        ]
    if phase == "result":
        narrative = _result_narrative(name, output)
        return [
            {"type": "thought", "safe_summary": True, "content": narrative},
            {"type": "status", "content": f"Completed {name}; reviewing the result."},
        ]
    return []
