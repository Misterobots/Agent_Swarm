"""Regression contract for desktop-owned Gauntlet continuation IDs."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

import main


def test_chat_request_accepts_a_structured_gauntlet_handoff():
    request = main.ChatRequest.model_validate({
        "messages": [{"role": "user", "content": "please resume"}],
        "gauntlet_mode": True,
        "gauntlet_bar": "https://example.test/bar",
        "gauntlet_handoff": {
            "id": "checkpoint_12345678",
            "goal": "Preserved original objective",
            "qualityBar": "https://example.test/bar",
            "effort": {"model": "qwen3:14b", "reasoningEffort": "high"},
        },
    })
    assert request.gauntlet_handoff["id"] == "checkpoint_12345678"
    assert request.gauntlet_handoff["goal"] == "Preserved original objective"


def test_gauntlet_prompt_keeps_the_named_bar_visible_to_workers():
    prompt = main._gauntlet_prompt("Build the vertical slice", "https://example.test/bar")
    assert "Build the vertical slice" in prompt
    assert "https://example.test/bar" in prompt
    assert "separate Pioneer-backed builder and critic" in prompt
