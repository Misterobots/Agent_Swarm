"""
history.py — provider-neutral conversation model for the dev harness.

The harness keeps ONE neutral history (system + a flat list of turns) as the
single source of truth.  Each provider adapter serialises it to its own wire
format and parses tool calls back into neutral turns.  This is what makes a
mid-conversation provider swap (local Ollama → GitHub/Claude escalation) clean:
the loop never holds a raw, provider-specific message list.

Turn types
----------
- UserMessage(content)              — a user/text turn
- AssistantMessage(content, tool_calls)  — assistant text + 0..n tool calls in one turn
- ToolResults(items)                — the results for the preceding assistant tool_calls

Wire-format notes the serialisers encode:
- OpenAI / Ollama: tool calls live ON the assistant message (`tool_calls`),
  and each result is a separate `{"role": "tool", ...}` message.  Ollama wants
  `function.arguments` as a dict; OpenAI/GitHub want it as a JSON string.
- Anthropic: tool calls are `tool_use` content blocks on the assistant turn,
  and results are `tool_result` blocks grouped inside a single *user* turn.
  The system prompt is a top-level kwarg, not a message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Union


# ---------------------------------------------------------------------------
# Neutral data model
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""
    call_id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    """The result of executing one ToolCall."""
    call_id: str
    name: str
    output: str
    is_error: bool = False


@dataclass
class UserMessage:
    content: str


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ToolResults:
    items: list[ToolResult] = field(default_factory=list)


Turn = Union[UserMessage, AssistantMessage, ToolResults]


# ---------------------------------------------------------------------------
# Streaming chunk — matches the shape the existing dev SSE serialiser expects
# (main.py reads .type/.content/.tool_name/.tool_input/.tool_call_id, and for
# tool_result it maps .content -> delta["tool_output"]).  agent_name/event_type
# are used by `agent_event` chunks (escalation notices).
# ---------------------------------------------------------------------------

@dataclass
class StreamChunk:
    type: str = "content"  # content|tool_start|tool_result|tool_approval_needed|todo|agent_event|error|status
    content: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_call_id: str | None = None
    agent_name: str | None = None
    event_type: str | None = None
    # Structured payload for events whose `content` is an object (e.g. `todo`,
    # whose delta.content carries {"todos": [...]}).  When set, the SSE
    # serialiser uses this as delta["content"] instead of the string content.
    data: Any = None


# ---------------------------------------------------------------------------
# History container
# ---------------------------------------------------------------------------

class History:
    """Provider-neutral conversation: a system prompt + an ordered turn list."""

    def __init__(self, system: str = "", turns: list[Turn] | None = None):
        self.system = system
        self.turns: list[Turn] = list(turns) if turns else []

    # -- mutation -----------------------------------------------------------
    def add_user(self, content: str) -> None:
        self.turns.append(UserMessage(content))

    def add_assistant(self, content: str, tool_calls: list[ToolCall] | None = None) -> None:
        self.turns.append(AssistantMessage(content or "", list(tool_calls or [])))

    def add_tool_results(self, items: Iterable[ToolResult]) -> None:
        self.turns.append(ToolResults(list(items)))

    # -- ingestion ----------------------------------------------------------
    @classmethod
    def from_openai_messages(
        cls, messages: list[dict[str, Any]], system: str = ""
    ) -> "History":
        """Build a neutral history from incoming OpenAI-style chat messages.

        A leading/explicit system message is hoisted into `system` (merged with
        any caller-supplied `system`).  Assistant tool_calls / tool messages in
        the *incoming* payload are preserved so resumed conversations round-trip.
        """
        sys_parts: list[str] = [system] if system else []
        turns: list[Turn] = []
        # call_id -> name, so trailing tool messages can be grouped with names
        pending_call_names: dict[str, str] = {}
        pending_results: list[ToolResult] = []

        def _flush_results():
            nonlocal pending_results
            if pending_results:
                turns.append(ToolResults(pending_results))
                pending_results = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content") or ""
            if role == "system":
                if content:
                    sys_parts.append(content)
                continue
            if role == "tool":
                call_id = m.get("tool_call_id", "")
                pending_results.append(
                    ToolResult(
                        call_id=call_id,
                        name=pending_call_names.get(call_id, ""),
                        output=content if isinstance(content, str) else json.dumps(content),
                    )
                )
                continue
            # Non-tool message terminates any pending tool-result group.
            _flush_results()
            if role == "assistant":
                raw_calls = m.get("tool_calls") or []
                calls: list[ToolCall] = []
                for tc in raw_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    cid = (tc.get("id") if isinstance(tc, dict) else None) or ""
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args) if raw_args else {}
                        except json.JSONDecodeError:
                            raw_args = {}
                    calls.append(ToolCall(call_id=cid, name=name, args=raw_args or {}))
                    if cid:
                        pending_call_names[cid] = name
                turns.append(AssistantMessage(content if isinstance(content, str) else "", calls))
            else:  # user (or unknown) -> treat as user text
                turns.append(UserMessage(content if isinstance(content, str) else json.dumps(content)))

        _flush_results()
        return cls(system="\n\n".join(p for p in sys_parts if p), turns=turns)

    # -- serialisation: OpenAI / Ollama ------------------------------------
    def to_openai_messages(self, *, args_as_string: bool) -> list[dict[str, Any]]:
        """Render to OpenAI-style messages.

        args_as_string=True  → GitHub/OpenAI (function.arguments is a JSON string)
        args_as_string=False → Ollama (function.arguments is a dict)
        """
        out: list[dict[str, Any]] = []
        if self.system:
            out.append({"role": "system", "content": self.system})
        for turn in self.turns:
            if isinstance(turn, UserMessage):
                out.append({"role": "user", "content": turn.content})
            elif isinstance(turn, AssistantMessage):
                msg: dict[str, Any] = {"role": "assistant", "content": turn.content or ""}
                if turn.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": c.call_id,
                            "type": "function",
                            "function": {
                                "name": c.name,
                                "arguments": json.dumps(c.args) if args_as_string else c.args,
                            },
                        }
                        for c in turn.tool_calls
                    ]
                out.append(msg)
            elif isinstance(turn, ToolResults):
                for r in turn.items:
                    out.append(
                        {"role": "tool", "tool_call_id": r.call_id, "content": r.output}
                    )
        return out

    # -- serialisation: Anthropic ------------------------------------------
    def to_anthropic_messages(self) -> list[dict[str, Any]]:
        """Render to Anthropic Messages API turns (system is passed separately)."""
        out: list[dict[str, Any]] = []
        for turn in self.turns:
            if isinstance(turn, UserMessage):
                out.append({"role": "user", "content": turn.content})
            elif isinstance(turn, AssistantMessage):
                blocks: list[dict[str, Any]] = []
                if turn.content:
                    blocks.append({"type": "text", "text": turn.content})
                for c in turn.tool_calls:
                    blocks.append(
                        {"type": "tool_use", "id": c.call_id, "name": c.name, "input": c.args}
                    )
                # An assistant turn must carry at least one block.
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            elif isinstance(turn, ToolResults):
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": r.call_id,
                                "content": r.output,
                                **({"is_error": True} if r.is_error else {}),
                            }
                            for r in turn.items
                        ],
                    }
                )
        return out

    def last_tool_calls(self) -> list[ToolCall]:
        """Tool calls from the most recent assistant turn (for loop-detection)."""
        for turn in reversed(self.turns):
            if isinstance(turn, AssistantMessage):
                return turn.tool_calls
        return []
