from unittest.mock import MagicMock, patch

import pytest

from providers.ollama_provider import OllamaProvider
from providers.qwen_context import (
    QwenContext,
    ensure_context_headroom,
    resolve_qwen_context,
)


def test_qwen_profiles_and_task_mode_defaults():
    assert resolve_qwen_context("qwen3.8:27b") == QwenContext("chat", 32768)
    assert resolve_qwen_context("qwen3.8:27b", task_mode="swarm") == QwenContext("project", 65536)
    assert resolve_qwen_context("qwen3.8:27b", "long") == QwenContext("long", 122880)


def test_non_qwen_models_keep_existing_provider_context_behavior():
    assert resolve_qwen_context("qwen3.6:27b", "long", task_mode="project") == QwenContext(None, None)
    provider = OllamaProvider("qwen3.6:27b", context_profile="chat", task_mode="project")
    assert provider.context == QwenContext(None, None)
    assert provider._options()["num_ctx"] == 32768


def test_invalid_profile_is_rejected():
    with pytest.raises(ValueError, match="Invalid Qwen context profile"):
        resolve_qwen_context("qwen3.8:27b", "huge")


def test_headroom_rejects_silent_truncation():
    ensure_context_headroom(input_tokens=100, tool_tokens=50, output_tokens=50, effective_tokens=200)
    with pytest.raises(ValueError, match="Context budget exceeded"):
        ensure_context_headroom(input_tokens=100, tool_tokens=51, output_tokens=50, effective_tokens=200)


def test_qwen_provider_payload_uses_effective_profile_and_metadata():
    history = MagicMock()
    history.to_openai_messages.return_value = [{"role": "user", "content": "hello"}]
    response = MagicMock()
    response.json.return_value = {"message": {"content": "ok"}}
    response.raise_for_status.return_value = None
    with patch("providers.ollama_provider.requests.post", return_value=response) as post:
        result = OllamaProvider("qwen3.8:27b", context_profile="long").chat_with_tools(history, [])
    payload = post.call_args.kwargs["json"]
    assert payload["options"]["num_ctx"] == 122880
    assert result.text == "ok"
    assert OllamaProvider("qwen3.8:27b", context_profile="project").metadata == {
        "context_profile": "project",
        "effective_context_tokens": 65536,
        "requested_model": "qwen3.8:27b",
        "actual_model": "qwen3.8:27b",
        "provider": "ollama",
        "fallback": False,
    }
    with pytest.raises(ValueError, match="Context budget exceeded"):
        OllamaProvider("qwen3.8:27b", context_profile="chat").validate_context_headroom(
            input_tokens=30000, output_tokens=3000
        )


def test_ollama_image_transport_normalizes_data_url():
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "describe this"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC123"}},
        ],
    }]
    assert OllamaProvider._messages_for_ollama(messages) == [{
        "role": "user",
        "content": "describe this",
        "images": ["ABC123"],
    }]
