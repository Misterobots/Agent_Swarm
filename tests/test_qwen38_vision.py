"""Focused, no-GPU tests for Qwen 3.8 vision routing."""

import base64
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, "agents")


class _MetricStub:
    def labels(self, **_labels):
        return self

    def set(self, _value):
        return None

    def inc(self):
        return None


# The focused test environment intentionally has no Prometheus runtime.  The
# handler only needs the metric surface, so keep this suite independent of the
# production metrics package.
sys.modules.setdefault(
    "metrics",
    SimpleNamespace(AGENT_STATE=_MetricStub(), WORKFLOW_STEPS=_MetricStub()),
)

from handlers.qwen_vision import (  # noqa: E402
    QWEN_VISION_MODEL,
    build_vision_payload,
    context_tokens,
    extract_image_data,
    model_supports_vision,
    requested_qwen_model,
    select_vision_model,
)
from handlers.vision import handle_vision  # noqa: E402


PNG_B64 = base64.b64encode(b"fake-png").decode()


def _response(payload, status=200):
    return SimpleNamespace(status_code=status, json=lambda: payload, raise_for_status=lambda: None)


def test_malformed_attachment_is_rejected():
    assert extract_image_data("data:image/png;base64,not-valid***") is None
    assert extract_image_data("plain text that is not an image") is None


def test_context_profiles_are_exact():
    assert context_tokens("chat") == ("chat", 32768)
    assert context_tokens("project") == ("project", 65536)
    assert context_tokens("long") == ("long", 122880)
    with pytest.raises(ValueError):
        context_tokens("huge")


def test_complete_saved_qwen_profile_enables_qwen_vision():
    roles = {
        role: QWEN_VISION_MODEL
        for role in ("coordinator", "architect", "coder", "devops", "researcher", "analyst", "verifier")
    }
    assert requested_qwen_model({"team_config": roles}) == QWEN_VISION_MODEL
    assert requested_qwen_model({"team_config": {"coder": QWEN_VISION_MODEL}}) is None


def test_selected_qwen_requires_installed_tag_and_vision_capability():
    inventory = {QWEN_VISION_MODEL: {"name": QWEN_VISION_MODEL}}
    with patch("handlers.qwen_vision.requests.post", return_value=_response({"capabilities": ["completion"]})):
        assert model_supports_vision("http://ollama", QWEN_VISION_MODEL, inventory) is False
    with patch("handlers.qwen_vision.requests.post", return_value=_response({"capabilities": ["vision"]})):
        assert model_supports_vision("http://ollama", QWEN_VISION_MODEL, {}) is False


def test_unavailable_qwen_falls_back_only_to_verified_lightweight_model():
    inventory = {
        "minicpm-v:latest": {"name": "minicpm-v:latest"},
    }
    with patch(
        "handlers.qwen_vision.requests.post",
        return_value=_response({"capabilities": ["vision"]}),
    ) as show:
        selected, fallback, requested = select_vision_model(
            "http://ollama", {"requested_model": QWEN_VISION_MODEL}, inventory=inventory
        )
    assert selected == "minicpm-v:latest"
    assert fallback is True
    assert requested == QWEN_VISION_MODEL
    assert show.call_count == 1


def test_native_payload_contains_image_and_profile_context():
    payload = build_vision_payload(QWEN_VISION_MODEL, "describe", PNG_B64, 65536)
    assert payload["model"] == QWEN_VISION_MODEL
    assert payload["images"] == [PNG_B64]
    assert payload["options"] == {"num_ctx": 65536}


def test_handler_reports_selected_qwen_and_uses_native_image_payload():
    ctx = {
        "turn_id": "turn-1",
        "extracted_context": f"data:image/png;base64,{PNG_B64}",
        "history_context": "",
        "lf_trace": None,
        "langfuse": None,
        "use_langfuse": False,
        "requested_model": QWEN_VISION_MODEL,
        "context_profile": "project",
    }

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            return _response({"capabilities": ["vision"]})
        return _response({"response": "qwen vision result"})

    with patch("handlers.vision.get_best_host_for_model", return_value="http://ollama"), \
         patch("handlers.vision.request_lock") as lock, \
         patch("handlers.qwen_vision.requests.get", return_value=_response({"models": [{"name": QWEN_VISION_MODEL}]})), \
         patch("handlers.qwen_vision.requests.post", side_effect=post) as qwen_post:
        lock.return_value.__enter__.return_value = None
        lock.return_value.__exit__.return_value = False
        events = list(handle_vision("describe this", ctx))

    metadata = next(event for event in events if event.get("type") == "model_metadata")
    assert metadata == {
        "type": "model_metadata",
        "requested_model": QWEN_VISION_MODEL,
        "actual_model": QWEN_VISION_MODEL,
        "provider": "ollama",
        "fallback": False,
        "context_profile": "project",
        "effective_context_tokens": 65536,
    }
    generate_call = qwen_post.call_args_list[-1]
    assert generate_call.args[0].endswith("/api/generate")
    assert generate_call.kwargs["json"]["images"] == [PNG_B64]
    assert generate_call.kwargs["json"]["options"] == {"num_ctx": 65536}
    lock.assert_called_once_with("vision")


def test_handler_reports_actual_model_when_qwen_falls_back():
    ctx = {
        "turn_id": "turn-2",
        "extracted_context": f"data:image/png;base64,{PNG_B64}",
        "history_context": "",
        "lf_trace": None,
        "langfuse": None,
        "use_langfuse": False,
        "requested_model": QWEN_VISION_MODEL,
        "context_profile": "chat",
    }

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            return _response({"capabilities": ["vision"]})
        return _response({"response": "fallback result"})

    with patch("handlers.vision.get_best_host_for_model", return_value="http://ollama"), \
         patch("handlers.vision.request_lock") as lock, \
         patch("handlers.qwen_vision.requests.get", return_value=_response({"models": [{"name": "minicpm-v:latest"}]})), \
         patch("handlers.qwen_vision.requests.post", side_effect=post):
        lock.return_value.__enter__.return_value = None
        lock.return_value.__exit__.return_value = False
        events = list(handle_vision("describe this", ctx))

    metadata = next(event for event in events if event.get("type") == "model_metadata")
    assert metadata["requested_model"] == QWEN_VISION_MODEL
    assert metadata["actual_model"] == "minicpm-v:latest"
    assert metadata["fallback"] is True
