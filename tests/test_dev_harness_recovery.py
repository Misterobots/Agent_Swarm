from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from conversation_compaction import compact_messages
from dev_harness.base import ProviderResult
from dev_harness.history import History, ToolCall
from dev_harness.loop import DevHarness


class ScriptedRouter:
    def __init__(self):
        self.calls = 0

    def complete(self, _history, _tools, _state):
        self.calls += 1
        if self.calls == 1:
            return ProviderResult(
                text="I will update the file.",
                tool_calls=[ToolCall("call-1", "write_file", {"path": "a.txt", "content": "ok"})],
            ), []
        return ProviderResult(text="Done."), []


class Approval:
    def needs(self, name):
        return name == "write_file"

    async def wait(self, _call_id, _tool_name="", _arguments=None):
        return "approved"


class Gate:
    def check(self, _name):
        return True, ""


class ToolBudgetRouter:
    """Consumes the whole active budget, then writes a final response."""

    def __init__(self):
        self.calls = 0

    def complete(self, _history, tools, _state):
        self.calls += 1
        if tools:
            return ProviderResult(
                tool_calls=[ToolCall(f"call-{self.calls}", "read_file", {"path": f"{self.calls}.txt"})],
            ), []
        return ProviderResult(text="I reviewed the available files and preserved the next steps."), []


def test_approved_tool_checkpoint_resume_and_compaction_boundary():
    history = History(system="system")
    history.add_user("update the file")
    checkpoint_states = []
    executed = []

    async def checkpoint(status, turn, pending, error):
        checkpoint_states.append((status, turn, [p["call_id"] for p in pending], error))
        return True

    async def execute(call_id, name, args):
        executed.append((call_id, name, args))
        return "written"

    async def run():
        return [
            chunk async for chunk in DevHarness(max_iterations=3).run(
                history,
                tools=[],
                tool_executor=execute,
                router=ScriptedRouter(),
                approval=Approval(),
                gate=Gate(),
                checkpoint=checkpoint,
            )
        ]

    chunks = asyncio.run(run())
    restored = History.from_checkpoint(history.to_checkpoint())
    compacted = compact_messages([
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
        {"role": "assistant", "content": "four"},
        {"role": "user", "content": "five"},
        {"role": "assistant", "content": "six"},
        {"role": "user", "content": "tail"},
    ], "continue from the approved file edit")

    assert executed == [("call-1", "write_file", {"path": "a.txt", "content": "ok"})]
    assert [chunk.type for chunk in chunks].count("tool_approval_needed") == 1
    assert checkpoint_states[0][0] == "awaiting_tools"
    assert checkpoint_states[1][0] == "recovery_required"
    assert checkpoint_states[-2][0] == "running"
    assert checkpoint_states[-1][0] == "completed"
    assert restored.to_checkpoint() == history.to_checkpoint()
    assert compacted[0]["role"] == "system"
    assert compacted[-1]["content"] == "tail"


def test_budget_exhaustion_synthesizes_instead_of_emitting_a_terminal_error():
    history = History(system="system")
    history.add_user("inspect the workspace")
    checkpoints = []

    async def checkpoint(status, turn, pending, error):
        checkpoints.append((status, turn, pending, error))
        return True

    async def execute(_call_id, _name, _args):
        return "read"

    async def run():
        return [
            chunk async for chunk in DevHarness(max_iterations=3).run(
                history, tools=[{"type": "function"}], tool_executor=execute,
                router=ToolBudgetRouter(), checkpoint=checkpoint,
            )
        ]

    chunks = asyncio.run(run())

    assert [chunk.type for chunk in chunks].count("tool_start") == 3
    assert any(chunk.content == "Tool-turn budget reached; preparing a progress summary." for chunk in chunks)
    assert any("reviewed the available files" in chunk.content for chunk in chunks)
    assert not any(chunk.type == "error" and "loop exceeded" in chunk.content for chunk in chunks)
    assert checkpoints[-2][0] == "synthesizing"
    assert checkpoints[-1][0] == "completed"
