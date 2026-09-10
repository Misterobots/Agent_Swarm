from dev_harness.activity import completed_activity_event, initial_activity_events, tool_activity_events


def test_initial_events_create_one_visible_code_agent_and_safe_summary():
    events = initial_activity_events()
    assert events[0]["worker_id"] == "code-agent"
    assert events[1]["safe_summary"] is True
    assert events[1]["content"] == "I’m reviewing the selected workspace before making changes."
    assert completed_activity_event()["event_type"] == "completed"


def test_tool_start_has_user_safe_intent_and_progress():
    assert tool_activity_events("read_file", "start") == [
        {"type": "thought", "safe_summary": True, "content": "Next, I’ll read the relevant project files."},
        {"type": "status", "content": "Working: read the relevant project files."},
    ]


def test_tool_result_reports_progress_without_exposing_output():
    assert tool_activity_events("run_command", "result", output="[exit 127] bash: python: command not found") == [
        {"type": "thought", "safe_summary": True, "content": "The requested executable is unavailable in this workspace. I’ll use the available project runtime."},
        {"type": "status", "content": "Completed run_command; reviewing the result."},
    ]


def test_command_narration_explains_observable_setup_failures_without_echoing_output():
    start = tool_activity_events("run_command", "start", {"command": "python3 -m archonkit.cli extract assets"})
    module = tool_activity_events("run_command", "result", output="ModuleNotFoundError: No module named 'archonkit'")
    managed = tool_activity_events("run_command", "result", output="error: externally-managed-environment")

    assert start[0]["content"] == "Next, I’ll run the project’s Python tooling."
    assert "missing a required project module" in module[0]["content"]
    assert "project-local environment" in managed[0]["content"]
    assert "archonkit" not in module[0]["content"]


def test_unknown_tool_remains_legible():
    assert tool_activity_events("custom_probe", "start")[0]["content"] == "Next, I’ll custom probe."
