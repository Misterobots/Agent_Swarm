from event_contract import enrich_delta, stable_event


def test_stable_event_has_ordered_envelope_and_structured_payload():
    event = stable_event("run-1", 7, "tool_result", {"name": "read_file", "content": "ok"})
    assert event["type"] == "tool_result"
    assert event["run_id"] == "run-1"
    assert event["seq"] == 7
    assert event["ts"].endswith("+00:00")
    assert event["payload"] == {"name": "read_file", "content": "ok"}


def test_enrich_delta_preserves_legacy_fields_and_adds_envelope():
    delta = enrich_delta("chat-1", 3, {"content": "hello", "type": "message"})
    assert delta["content"] == "hello"
    assert delta["type"] == "message"
    assert delta["run_id"] == "chat-1"
    assert delta["seq"] == 3
    assert delta["event"]["payload"] == {"content": "hello", "type": "message"}
