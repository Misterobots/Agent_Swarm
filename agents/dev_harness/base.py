"""
base.py — the provider-adapter contract shared by every dev-harness backend.

Each adapter takes the *canonical* OpenAI-format tool definitions
(`main.DEV_TOOL_DEFINITIONS`) and the neutral `History`, converts both to its
own wire format internally, makes one non-streaming call, and returns a
`ProviderResult`.  Keeping the call non-streaming lets the loop inspect tool
calls deterministically before deciding to execute or finish (same approach the
original github_models loop used).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from dev_harness.history import History, ToolCall


@dataclass
class ProviderResult:
    """One assistant turn as parsed back into neutral form."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # True when a tool-arg payload failed to parse cleanly and we fell back to
    # repair/empty.  The router counts this toward escalation.
    malformed_args: bool = False


@runtime_checkable
class Provider(Protocol):
    name: str   # short id used in logs + escalation agent_events ("ollama"|"github"|"anthropic")
    model: str

    def chat_with_tools(self, history: History, tools: list[dict]) -> ProviderResult:
        """One blocking model call.  Raises on transport/HTTP failure (the loop
        decides whether to escalate or surface the error)."""
        ...
