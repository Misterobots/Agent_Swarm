from event_contract import stable_event


def test_stable_event_has_ordered_envelope_and_structured_payload():
    event = stable_event("run-1", 7, "tool_result", {"name": "read_file", "content": "ok"})
    assert event["type"] == "tool_result"
    assert event["run_id"] == "run-1"
    assert event["seq"] == 7
    assert event["ts"].endswith("+00:00")
    assert event["payload"] == {"name": "read_file", "content": "ok"}
