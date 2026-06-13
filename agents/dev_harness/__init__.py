"""
dev_harness — provider-neutral agentic coding loop for the Memex Dev workspace.

Replaces the hand-rolled, GitHub-only `github_stream()` dev branch in main.py
with one coherent harness that:
  - keeps a provider-neutral message history (history.py) so any adapter
    (Ollama / GitHub / Anthropic) can render it to its own wire format and
    escalation can swap providers mid-conversation,
  - runs the model → tool-call → result loop (loop.py),
  - routes to a primary provider and escalates on stall (router.py),
  - repairs malformed small-model tool-arg JSON (arg_repair.py).

Phase 0 scope: the loop + three adapters + active escalation.
Tools, permissions, durability land in later phases.
"""

from dev_harness.history import (
    History,
    ToolCall,
    StreamChunk,
    UserMessage,
    AssistantMessage,
    ToolResults,
    ToolResult,
)

__all__ = [
    "History",
    "ToolCall",
    "StreamChunk",
    "UserMessage",
    "AssistantMessage",
    "ToolResults",
    "ToolResult",
]
