from dev_harness.history import (
    AssistantMessage,
    History,
    ToolCall,
    ToolResult,
    UserMessage,
)


def test_checkpoint_round_trip_preserves_neutral_history():
    history = History(system="system prompt", turns=[
        UserMessage("inspect the project"),
        AssistantMessage(
            "I will inspect it.",
            [ToolCall("call-1", "list_directory", {"path": "."})],
        ),
    ])
    history.add_tool_results([
        ToolResult("call-1", "list_directory", "src\nREADME.md"),
    ])

    restored = History.from_checkpoint(history.to_checkpoint())

    assert restored.to_checkpoint() == history.to_checkpoint()


def test_checkpoint_rejects_unknown_turns_instead_of_dropping_them():
    try:
        History.from_checkpoint({"system": "", "turns": [{"type": "unknown"}]})
    except ValueError as exc:
        assert "unknown checkpoint turn type" in str(exc)
    else:
        raise AssertionError("invalid checkpoint should be rejected")
