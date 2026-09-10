"""User-safe activity narration for the desktop DevHarness stream.

These messages describe observable harness state and the next tool action. They
are not model scratchpad or hidden chain-of-thought.
"""

from __future__ import annotations


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


def tool_activity_events(tool_name: str | None, phase: str) -> list[dict[str, object]]:
    """Return small, user-readable lifecycle events for one tool call.

    ``phase`` is ``start`` or ``result``. Unknown tools retain their name so
    the stream never becomes a vague, empty spinner.
    """
    name = (tool_name or "tool").strip() or "tool"
    action = _TOOL_ACTIONS.get(name, name.replace("_", " "))
    if phase == "start":
        return [
            {"type": "thought", "safe_summary": True, "content": f"Next, I’ll {action}."},
            {"type": "status", "content": f"Working: {action}."},
        ]
    if phase == "result":
        return [{"type": "status", "content": f"Completed {name}; reviewing the result."}]
    return []
