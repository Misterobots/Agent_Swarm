"""
loop.py — the DevHarness agentic loop (provider-neutral).

Control flow extracted from github_models_provider.generate_stream_with_tools,
but operating on the neutral History and delegating provider selection +
escalation to a ModelRouter.  Each turn:

    1. router.complete(history, tools, state)  → one assistant turn (blocking
       model call, run off the event loop) + any escalation notices
    2. record the assistant turn on the history
    3. if no tool calls → stream the final text and stop
    4. otherwise execute each tool via `tool_executor` (which owns the approval
       gate), stream tool_start / tool_result, append ToolResults, loop

`tool_executor(call_id, name, args) -> str` is preserved verbatim from the old
dev branch so the existing approval wiring keeps working unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from dev_harness.history import History, StreamChunk, ToolResult

logger = logging.getLogger("dev_harness.loop")

_STREAM_CHUNK_SIZE = 80

ToolExecutor = Callable[[str, str, dict], Awaitable[str]]


class DevHarness:
    def __init__(self, max_iterations: int = 12):
        self.max_iterations = max_iterations

    async def run(
        self,
        history: History,
        tools: list[dict],
        tool_executor: ToolExecutor,
        router,
        approval=None,
        gate=None,
    ):
        """Async generator yielding StreamChunk objects (caller serialises to SSE).

        `approval`, if given, gates mutating tool calls.  It must expose:
            needs(tool_name) -> bool
            async wait(call_id) -> "approved" | "denied" | "timeout"
        The loop *yields* the approval request before awaiting the decision, so
        the client receives the approval card immediately (no deadlock).

        `gate`, if given, is a PermissionGate whose check(tool_name) -> (allowed,
        reason) enforces plan mode (read-only) before approval/execution.

        `tool_executor` returns either a result string, or a (string, [extra
        StreamChunks]) tuple for harness tools that also emit UI events
        (e.g. TodoWrite emits a `todo` event alongside its result).
        """
        from dev_harness.router import HarnessState

        state = HarnessState()
        event_loop = asyncio.get_event_loop()

        for _ in range(self.max_iterations):
            state.turn += 1

            # --- one model turn (blocking call + escalation, off the event loop) ---
            try:
                result, notices = await event_loop.run_in_executor(
                    None, router.complete, history, tools, state
                )
            except Exception as e:  # transport/HTTP failure with no escalation path
                logger.error("[dev_harness] model call failed (turn %d): %s", state.turn, e, exc_info=True)
                yield StreamChunk(type="error", content=f"Model call failed: {e}")
                return

            for notice in notices:
                yield notice

            # Record the assistant turn (text + any tool calls) on the neutral history.
            history.add_assistant(result.text, result.tool_calls)

            # Stream any assistant prose (preamble before tools, or the final answer).
            if result.text:
                for i in range(0, len(result.text), _STREAM_CHUNK_SIZE):
                    yield StreamChunk(type="content", content=result.text[i : i + _STREAM_CHUNK_SIZE])

            if not result.tool_calls:
                return  # model is done

            # --- execute tool calls ---
            tool_results: list[ToolResult] = []
            for call in result.tool_calls:
                yield StreamChunk(
                    type="tool_start",
                    content=f"Using tool: {call.name}",
                    tool_name=call.name,
                    tool_input=call.args,
                    tool_call_id=call.call_id,
                )

                # Permission gate (e.g. plan mode blocks mutating tools).
                if gate is not None:
                    allowed, reason = gate.check(call.name)
                    if not allowed:
                        yield StreamChunk(
                            type="tool_result", content=reason,
                            tool_name=call.name, tool_call_id=call.call_id,
                        )
                        tool_results.append(
                            ToolResult(call_id=call.call_id, name=call.name, output=reason, is_error=True)
                        )
                        continue

                # Approval gate: yield the request FIRST (so the client shows the
                # approve/deny card), THEN await the decision.  Never block before
                # yielding, or the event can't reach the client.
                if approval is not None and approval.needs(call.name):
                    yield StreamChunk(
                        type="tool_approval_needed",
                        content=f"Approval required: {call.name}",
                        tool_name=call.name,
                        tool_input=call.args,
                        tool_call_id=call.call_id,
                    )
                    decision = await approval.wait(call.call_id)
                    if decision != "approved":
                        denied = (
                            f"Tool {call.name!r} approval timed out — skipped."
                            if decision == "timeout"
                            else f"Tool {call.name!r} was denied by the user."
                        )
                        yield StreamChunk(
                            type="tool_result",
                            content=denied,
                            tool_name=call.name,
                            tool_call_id=call.call_id,
                        )
                        tool_results.append(
                            ToolResult(call_id=call.call_id, name=call.name, output=denied, is_error=True)
                        )
                        continue

                # tool_executor returns a str, or (str, [extra StreamChunks]) for
                # harness tools that also emit UI events (e.g. TodoWrite -> todo).
                raw = await tool_executor(call.call_id, call.name, call.args)
                if isinstance(raw, tuple):
                    output, extra_chunks = raw
                else:
                    output, extra_chunks = raw, ()
                for ec in extra_chunks:
                    yield ec
                yield StreamChunk(
                    type="tool_result",
                    content=output,
                    tool_name=call.name,
                    tool_call_id=call.call_id,
                )
                tool_results.append(
                    ToolResult(call_id=call.call_id, name=call.name, output=output)
                )

            history.add_tool_results(tool_results)

        # iteration budget exhausted
        yield StreamChunk(
            type="error",
            content=f"Agentic loop exceeded {self.max_iterations} iterations — stopping.",
        )
