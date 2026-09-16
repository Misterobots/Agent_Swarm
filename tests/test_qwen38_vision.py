"""Focused, no-GPU tests for Qwen 3.8 vision routing."""

import base64
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

try:
    from providers.qwen_context import resolve_qwen_context  # noqa: F401
except ImportError:
    import types

    context_module = types.ModuleType("providers.qwen_context")

    class _TestContext:
        def __init__(self, profile, tokens):
            self.context_profile = profile
            self.effective_context_tokens = tokens

    def _test_resolve(model, context_profile=None, *, task_mode="chat"):
        if model != "qwen3.8:27b":
            return _TestContext(None, None)
        if context_profile is not None and context_profile not in {"chat", "project", "long"}:
            raise ValueError("Invalid Qwen context profile")
        profile = context_profile or ("project" if task_mode in {"code", "coding", "project", "swarm"} else "chat")
        return _TestContext(profile, {"chat": 32768, "project": 65536, "long": 122880}[profile])

    context_module.QWEN_MODEL = "qwen3.8:27b"
    context_module.QWEN_OUTPUT_RESERVE = 4096
    context_module.QWEN_IMAGE_TOKEN_ALLOWANCE = 2048
    context_module.resolve_qwen_context = _test_resolve
    context_module.estimate_messages_tokens = lambda messages: 100
    context_module.ensure_context_headroom = lambda **kwargs: None
    sys.modules["providers.qwen_context"] = context_module

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
    validate_vision_headroom,
)
from handlers.vision import handle_vision  # noqa: E402


PNG_B64 = base64.b64encode(b"fake-png").decode()


def _response(payload, status=200):
    return SimpleNamespace(status_code=status, json=lambda: payload, raise_for_status=lambda: None)


def test_malformed_attachment_is_rejected():
    assert extract_image_data("data:image/png;base64,not-valid***") is None
    assert extract_image_data("plain text that is not an image") is None


def test_context_profiles_are_exact():
    assert context_tokens(QWEN_VISION_MODEL, "chat") == ("chat", 32768)
    assert context_tokens(QWEN_VISION_MODEL, "project") == ("project", 65536)
    assert context_tokens(QWEN_VISION_MODEL, "long") == ("long", 122880)
    with pytest.raises(ValueError):
        context_tokens(QWEN_VISION_MODEL, "huge")
    assert context_tokens("minicpm-v:latest", "long") == (None, None)


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
        selected, fallback, requested, selected_host = select_vision_model(
            "http://ollama", {"requested_model": QWEN_VISION_MODEL}, inventory=inventory
        )
    assert selected == "minicpm-v:latest"
    assert fallback is True
    assert requested == QWEN_VISION_MODEL
    assert selected_host == "http://ollama"
    assert show.call_count == 1


def test_fallback_capability_is_checked_on_candidate_host():
    hosts = {QWEN_VISION_MODEL: "http://lovelace", "minicpm-v:latest": "http://turing"}
    inventories = {
        "http://lovelace": {},
        "http://turing": {"minicpm-v:latest": {"name": "minicpm-v:latest"}},
    }

    def get(url, **_kwargs):
        host = url.removesuffix("/api/tags")
        return _response({"models": list(inventories[host].values())})

    with patch("handlers.qwen_vision.requests.get", side_effect=get), \
         patch("handlers.qwen_vision.requests.post", return_value=_response({"capabilities": ["vision"]})):
        selected, fallback, requested, selected_host = select_vision_model(
            "http://lovelace",
            {"requested_model": QWEN_VISION_MODEL},
            host_resolver=lambda model: hosts[model],
        )

    assert (selected, fallback, requested, selected_host) == (
        "minicpm-v:latest", True, QWEN_VISION_MODEL, "http://turing"
    )


def test_native_payload_contains_image_and_profile_context():
    payload = build_vision_payload(QWEN_VISION_MODEL, "describe", PNG_B64, 65536)
    assert payload["model"] == QWEN_VISION_MODEL
    assert payload["images"] == [PNG_B64]
    assert payload["options"] == {"num_ctx": 65536, "num_predict": 4096}
    legacy = build_vision_payload("minicpm-v:latest", "describe", PNG_B64, None)
    assert "options" not in legacy


def test_qwen_vision_headroom_uses_shared_context_helper():
    with patch("handlers.qwen_vision.estimate_messages_tokens", return_value=30000) as estimate, \
         patch("handlers.qwen_vision.ensure_context_headroom") as ensure:
        validate_vision_headroom(QWEN_VISION_MODEL, "describe", PNG_B64, 32768)
    estimate.assert_called_once()
    ensure.assert_called_once_with(
        input_tokens=30000,
        output_tokens=4096,
        tool_tokens=0,
        effective_tokens=32768,
    )


def test_qwen_vision_headroom_fails_closed():
    with patch(
        "handlers.qwen_vision.estimate_messages_tokens", return_value=32760
    ), patch(
        "handlers.qwen_vision.ensure_context_headroom",
        side_effect=ValueError("Context budget exceeded"),
    ):
        with pytest.raises(ValueError, match="Context budget exceeded"):
            validate_vision_headroom(QWEN_VISION_MODEL, "describe", PNG_B64, 32768)


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
        "image_attachments": [],
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
    assert generate_call.kwargs["json"]["options"] == {
        "num_ctx": 65536,
        "num_predict": 4096,
    }
    lock.assert_called_once_with("text")


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
        "image_attachments": [],
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


def test_ordinary_legacy_vision_is_not_a_qwen_fallback_and_uses_candidate_host():
    ctx = {
        "turn_id": "turn-3",
        "extracted_context": f"data:image/png;base64,{PNG_B64}",
        "history_context": "",
        "lf_trace": None,
        "langfuse": None,
        "use_langfuse": False,
        "image_attachments": [],
    }

    hosts = {
        QWEN_VISION_MODEL: "http://lovelace",
        "minicpm-v:latest": "http://turing",
    }

    def get(url, **_kwargs):
        if url.startswith("http://lovelace"):
            return _response({"models": []})
        return _response({"models": [{"name": "minicpm-v:latest"}]})

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            return _response({"capabilities": ["vision"]})
        return _response({"response": "legacy result"})

    with patch("handlers.vision.get_best_host_for_model", side_effect=lambda model: hosts.get(model, "http://turing")), \
         patch("handlers.vision.request_lock") as lock, \
         patch("handlers.qwen_vision.requests.get", side_effect=get), \
         patch("handlers.qwen_vision.requests.post", side_effect=post) as qwen_post:
        lock.return_value.__enter__.return_value = None
        lock.return_value.__exit__.return_value = False
        events = list(handle_vision("describe this", ctx))

    metadata = next(event for event in events if event.get("type") == "model_metadata")
    assert metadata["requested_model"] is None
    assert metadata["actual_model"] == "minicpm-v:latest"
    assert metadata["fallback"] is False
    assert metadata["context_profile"] is None
    assert metadata["effective_context_tokens"] is None
    generate_call = qwen_post.call_args_list[-1]
    assert generate_call.args[0] == "http://turing/api/generate"
    assert "options" not in generate_call.kwargs["json"]
    lock.assert_called_once_with("text")
