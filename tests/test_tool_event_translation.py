"""Translation from phidata's tool chunks to the desktop's tool event contract (plan D8(b)).

These shapes are not invented: the start dict carries role/tool_call_id/tool_name/tool_args
and the completion *replaces* that same entry with one carrying content/tool_call_error
(phi `Model.run_function_calls`). The bug this file guards is the one those shapes caused —
`handlers/conversation.py` read only `chunk.content`, so a turn could run a tool and the
desktop would see nothing at all.

Pure function over plain dicts, so it runs on the host with no phi and no database — which
matters because on this machine the host has pytest and no phi while the container has phi
and no pytest.
"""
import os
import sys
from types import SimpleNamespace

_AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)

from handlers.base import tool_events_from_chunk


def _chunk(*tool_calls):
    return SimpleNamespace(tools=list(tool_calls))


def _fresh():
    return set(), set()


def _start(tc_id="call_1", name="list_dir", args=None):
    return {"role": "tool", "tool_call_id": tc_id, "tool_name": name,
            "tool_args": {"path": "."} if args is None else args}


def _done(tc_id="call_1", name="list_dir", output="a.txt\nb.txt", error=False):
    return {"role": "tool", "tool_call_id": tc_id, "tool_name": name,
            "tool_args": {"path": "."}, "content": output, "tool_call_error": error,
            "metrics": {"time": 0.01}, "created_at": 1}


def test_start_emits_one_queued_tool_start():
    starts, results = _fresh()
    events = list(tool_events_from_chunk(_chunk(_start()), starts, results))

    assert len(events) == 1
    assert events[0]["type"] == "tool_start"
    assert events[0]["tool_call_id"] == "call_1"
    assert events[0]["tool_name"] == "list_dir"
    assert events[0]["tool_input"] == {"path": "."}
    assert events[0]["tool_state"] == "queued"


def test_completion_emits_only_the_result_because_the_start_was_already_seen():
    starts, results = _fresh()
    list(tool_events_from_chunk(_chunk(_start()), starts, results))

    events = list(tool_events_from_chunk(_chunk(_done()), starts, results))

    assert [e["type"] for e in events] == ["tool_result"]
    assert events[0]["tool_output"] == "a.txt\nb.txt"
    assert events[0]["tool_state"] == "completed"


def test_the_same_accumulated_list_is_not_announced_twice():
    starts, results = _fresh()
    chunk = _chunk(_done())
    list(tool_events_from_chunk(chunk, starts, results))

    assert list(tool_events_from_chunk(chunk, starts, results)) == []


def test_a_failed_call_is_reported_as_an_error_not_a_silent_success():
    starts, results = _fresh()
    events = list(tool_events_from_chunk(_chunk(_done(error=True)), starts, results))

    assert len(events) == 2
    assert events[1]["type"] == "tool_result"
    assert events[1]["tool_state"] == "error"


def test_parallel_calls_are_tracked_independently():
    starts, results = _fresh()
    list(tool_events_from_chunk(_chunk(_start("call_a"), _start("call_b")), starts, results))

    events = list(tool_events_from_chunk(
        _chunk(_done("call_a"), _start("call_b")), starts, results))

    assert [e["type"] for e in events] == ["tool_result"]
    assert events[0]["tool_call_id"] == "call_a"


def test_a_chunk_carrying_no_tool_list_is_not_an_error():
    starts, results = _fresh()
    assert list(tool_events_from_chunk(SimpleNamespace(), starts, results)) == []
    assert list(tool_events_from_chunk(SimpleNamespace(tools=None), starts, results)) == []
    assert list(tool_events_from_chunk(_chunk("not a dict"), starts, results)) == []


def test_an_empty_result_is_marked_because_blank_and_absent_are_otherwise_identical():
    # D8(f). A model named three entries in a directory the tool had reported as empty, and
    # nothing on the wire distinguished "" from a missing field.
    starts, results = _fresh()
    events = list(tool_events_from_chunk(_chunk(_done(output="")), starts, results))

    assert len(events) == 2
    assert events[1]["type"] == "tool_result"
    assert events[1]["empty_result"] is True


def test_a_real_result_is_not_marked_empty():
    starts, results = _fresh()
    events = list(tool_events_from_chunk(_chunk(_done(output=".agents\n.claude")), starts, results))

    assert events[1]["empty_result"] is False


def test_whitespace_only_output_counts_as_empty():
    starts, results = _fresh()
    events = list(tool_events_from_chunk(_chunk(_done(output="\n  \n")), starts, results))

    assert events[1]["empty_result"] is True
