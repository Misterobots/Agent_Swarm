import base64
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from providers.ollama_provider import OllamaProvider
from providers.qwen_context import (
    QwenContext,
    decode_image_payload,
    ensure_context_headroom,
    estimate_messages_tokens,
    resolve_qwen_context,
)


PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
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
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_B64}"}},
        ],
    }]
    assert OllamaProvider._messages_for_ollama(messages) == [{
        "role": "user",
        "content": "describe this",
        "images": [PNG_B64],
    }]


def test_ollama_rejects_external_or_malformed_images():
    with pytest.raises(ValueError, match="invalid base64|decode"):
        OllamaProvider._normalize_image("ABC123")
    with pytest.raises(ValueError):
        OllamaProvider._messages_for_ollama([{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://example.invalid/a.png"}},
        ]}])
    with pytest.raises(ValueError):
        OllamaProvider._messages_for_ollama([{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,%%%"}},
        ]}])
    with pytest.raises(ValueError):
        OllamaProvider._messages_for_ollama([{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,"}},
        ]}])
    corrupted = base64.b64encode(b"\x89PNG\r\n\x1a\ncorrupted").decode()
    with pytest.raises(ValueError, match="decode|cannot identify|cannot read"):
        decode_image_payload(corrupted)


def test_qwen_dispatch_rejects_over_budget_before_post_and_attaches_metadata():
    history = MagicMock()
    history.to_openai_messages.return_value = [{"role": "user", "content": "x" * 130000}]
    with patch("providers.ollama_provider.requests.post") as post:
        with pytest.raises(ValueError, match="Context budget exceeded"):
            OllamaProvider("qwen3.8:27b", context_profile="chat").chat_with_tools(history, [])
    post.assert_not_called()


def test_qwen_result_contains_provider_metadata():
    history = MagicMock()
    history.to_openai_messages.return_value = [{"role": "user", "content": "hello"}]
    response = MagicMock()
    response.json.return_value = {"message": {"content": "ok"}}
    response.raise_for_status.return_value = None
    with patch("providers.ollama_provider.requests.post", return_value=response):
        result = OllamaProvider("qwen3.8:27b", context_profile="project").chat_with_tools(history, [])
    assert result.provider_metadata["actual_model"] == "qwen3.8:27b"
    assert result.provider_metadata["effective_context_tokens"] == 65536


def test_history_to_ollama_dispatch_converts_image_and_posts_valid_payload():
    history = MagicMock()
    history.to_openai_messages.return_value = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "describe this"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_B64}"}},
        ],
    }]
    response = MagicMock()
    response.json.return_value = {"message": {"content": "ok"}}
    response.raise_for_status.return_value = None
    with patch("providers.ollama_provider.requests.post", return_value=response) as post:
        OllamaProvider("qwen3.8:27b", context_profile="chat").chat_with_tools(history, [])
    sent = post.call_args.kwargs["json"]["messages"][0]
    assert sent["content"] == "describe this"
    assert sent["images"] == [PNG_B64]


def test_large_legitimate_image_uses_fixed_allowance_not_base64_text_size():
    from PIL import Image

    image = Image.new("RGB", (1024, 1024))
    pixels = image.load()
    for y in range(1024):
        for x in range(1024):
            value = (x * 37 + y * 17) % 256
            pixels[x, y] = (value, (value * 3) % 256, (value * 7) % 256)
    raw = BytesIO()
    image.save(raw, format="PNG", compress_level=0)
    large_image = base64.b64encode(raw.getvalue()).decode()
    messages = [{"role": "user", "content": "describe", "images": [large_image]}]
    assert estimate_messages_tokens(messages) < 10_000

    response = MagicMock()
    response.json.return_value = {"message": {"content": "ok"}}
    response.raise_for_status.return_value = None
    history = MagicMock()
    history.to_openai_messages.return_value = messages
    with patch("providers.ollama_provider.requests.post", return_value=response) as post:
        OllamaProvider("qwen3.8:27b", context_profile="chat").chat_with_tools(history, [])
    assert post.called
