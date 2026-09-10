from dev_harness.activity import tool_activity_events


def test_tool_start_has_user_safe_intent_and_progress():
    assert tool_activity_events("read_file", "start") == [
        {"type": "thought", "content": "Next, I’ll read the relevant project files."},
        {"type": "status", "content": "Working: read the relevant project files."},
    ]


def test_tool_result_reports_progress_without_exposing_output():
    assert tool_activity_events("run_command", "result") == [
        {"type": "status", "content": "Completed run_command; reviewing the result."},
    ]


def test_unknown_tool_remains_legible():
    assert tool_activity_events("custom_probe", "start")[0]["content"] == "Next, I’ll custom probe."
