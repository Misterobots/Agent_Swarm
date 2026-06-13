"""
router.py — primary-provider selection + active escalation for the dev harness.

The local model (qwen3-coder) is the default.  When it stalls — repeated
malformed tool args, no forward progress, or a tool-call loop — the router
swaps to a stronger, reliable tool-caller (GitHub gpt-4o first, then Claude)
and stays there for the rest of the run.  This is the dominant-risk mitigation:
a weak local loop degrades to a working cloud loop instead of failing.

Escalation is ON by default (`DEV_ESCALATION_ENABLED`), but degrades to a no-op
when no cloud target is configured (no GitHub token / no ANTHROPIC_API_KEY) — so
the local-only path always runs.

`complete()` is synchronous and is invoked from the loop via run_in_executor;
it may make two blocking model calls in one invocation (primary then escalated)
on a transport failure.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field

from dev_harness.base import ProviderResult, Provider
from dev_harness.history import History, StreamChunk, ToolCall

logger = logging.getLogger("dev_harness.router")


def _escalation_enabled_default() -> bool:
    return os.getenv("DEV_ESCALATION_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")


# Escalation trigger thresholds (turns / counts).
_MALFORMED_LIMIT = 2          # cumulative malformed-arg turns
_NO_PROGRESS_LIMIT = 2        # consecutive turns with neither tool calls nor text
_LOOP_REPEAT = 3              # identical consecutive tool-call signatures


@dataclass
class HarnessState:
    """Per-run signals the router accumulates to decide escalation."""
    turn: int = 0
    malformed_count: int = 0
    consecutive_no_progress: int = 0
    recent_tool_signatures: list[str] = field(default_factory=list)
    escalated: bool = False


def _signature(tool_calls: list[ToolCall]) -> str:
    """Stable hash of a turn's tool calls (name+args) for loop detection."""
    if not tool_calls:
        return ""
    parts = sorted(f"{c.name}:{json.dumps(c.args, sort_keys=True, default=str)}" for c in tool_calls)
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _escalation_chunk(frm: str, to: str, reason: str) -> StreamChunk:
    return StreamChunk(
        type="agent_event",
        content=f"Local model {frm} stalled ({reason}) — escalating to {to}.",
        agent_name="router",
        event_type="escalation",
    )


class ModelRouter:
    def __init__(
        self,
        primary: Provider,
        escalation_targets: list[Provider] | None = None,
        enabled: bool | None = None,
    ):
        self.primary = primary
        self._targets = list(escalation_targets or [])
        self.enabled = _escalation_enabled_default() if enabled is None else enabled
        self._current_target: Provider | None = None

    # -- public -------------------------------------------------------------
    def complete(self, history: History, tools: list[dict], state: HarnessState):
        """Run one assistant turn; returns (ProviderResult, [notice StreamChunks])."""
        notices: list[StreamChunk] = []
        provider = self._select(state, notices)

        try:
            result = provider.chat_with_tools(history, tools)
        except Exception as e:
            # Transport/HTTP failure: escalate once if we still can.
            if not state.escalated and self._targets:
                target = self._activate_target()
                logger.warning("[router] primary %s failed (%s); escalating to %s", provider.name, e, target.name)
                state.escalated = True
                notices.append(_escalation_chunk(provider.name, target.name, f"call failed: {e}"))
                result = target.chat_with_tools(history, tools)
            else:
                raise

        self._update_state(state, result)
        return result, notices

    # -- internals ----------------------------------------------------------
    def _select(self, state: HarnessState, notices: list[StreamChunk]) -> Provider:
        # Already escalated → stay on the chosen cloud target.
        if state.escalated and self._current_target is not None:
            return self._current_target
        # Decide whether prior turns warrant escalation now.
        if self.enabled and self._targets and self._should_escalate(state):
            target = self._activate_target()
            state.escalated = True
            notices.append(_escalation_chunk(self.primary.name, target.name, self._reason(state)))
            logger.info("[router] escalating %s → %s (%s)", self.primary.name, target.name, self._reason(state))
            return target
        return self.primary

    def _activate_target(self) -> Provider:
        if self._current_target is None:
            self._current_target = self._targets[0]
        return self._current_target

    def _should_escalate(self, state: HarnessState) -> bool:
        return bool(self._reason(state))

    def _reason(self, state: HarnessState) -> str:
        if state.malformed_count >= _MALFORMED_LIMIT:
            return f"malformed tool args x{state.malformed_count}"
        if state.consecutive_no_progress >= _NO_PROGRESS_LIMIT:
            return f"no progress x{state.consecutive_no_progress}"
        sigs = state.recent_tool_signatures
        if len(sigs) >= _LOOP_REPEAT and sigs[-1] and all(s == sigs[-1] for s in sigs[-_LOOP_REPEAT:]):
            return "tool-call loop"
        return ""

    @staticmethod
    def _update_state(state: HarnessState, result: ProviderResult) -> None:
        if result.malformed_args:
            state.malformed_count += 1
        state.recent_tool_signatures.append(_signature(result.tool_calls))
        if not result.tool_calls and not (result.text or "").strip():
            state.consecutive_no_progress += 1
        else:
            state.consecutive_no_progress = 0
