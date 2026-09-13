"""Unit tests for services/code_gateway — the OpenAI->Ollama translation layer.

Pure translation logic only; no Ollama, no network.  Each test names the upstream defect
it guards against so a future regression is traceable back to the reason the code exists.
"""
import importlib
import json
import os
import sys

import pytest

_SERVICE = os.path.join(os.path.dirname(__file__), "..", "services", "code_gateway")


@pytest.fixture(scope="module")
def gw():
    """Import main.py with a known num_ctx map."""
    os.environ["CODE_GATEWAY_NUM_CTX_MAP"] = json.dumps({"qwen3.8:27b": 122880})
    os.environ["CODE_GATEWAY_NUM_CTX"] = "32768"
    sys.path.insert(0, os.path.abspath(_SERVICE))
    import main
    yield importlib.reload(main)
    sys.path.remove(os.path.abspath(_SERVICE))


SYSTEM = [{"role": "system", "content": "You are a coding agent."}]

# The exact shape qwen-code sends after a tool call: system + assistant + tool, no user turn.
BROKEN = SYSTEM + [
    {"role": "assistant", "content": None,
     "tool_calls": [{"id": "call_a1", "type": "function",
                     "function": {"name": "read_file", "arguments": '{"path":"main.py"}'}}]},
    {"role": "tool", "tool_call_id": "call_a1", "content": "def main(): ..."},
]


# --- qwen-code #9438: the dropped user turn ------------------------------------------------
@pytest.mark.unit
class TestDroppedUserTurn:
    def test_healthy_request_is_not_repaired(self, gw):
        gw._USER_TURN_CACHE.clear()
        msgs = SYSTEM + [{"role": "user", "content": "refactor @main.py"}]
        _, repaired = gw._ensure_user_turn(list(msgs))
        assert repaired is False

    def test_follow_up_recovers_the_cached_user_turn(self, gw):
        gw._USER_TURN_CACHE.clear()
        gw._ensure_user_turn(SYSTEM + [{"role": "user", "content": "refactor @main.py"}])
        fixed, repaired = gw._ensure_user_turn(list(BROKEN))
        assert repaired is True
        assert [m["role"] for m in fixed] == ["system", "user", "assistant", "tool"]
        assert fixed[1]["content"] == "refactor @main.py"

    def test_cold_start_falls_back_to_placeholder(self, gw):
        gw._USER_TURN_CACHE.clear()
        fixed, repaired = gw._ensure_user_turn(list(BROKEN))
        assert repaired is True
        assert fixed[1]["content"] == gw.PLACEHOLDER_USER

    def test_cache_is_keyed_on_the_system_prompt(self, gw):
        gw._USER_TURN_CACHE.clear()
        gw._ensure_user_turn(SYSTEM + [{"role": "user", "content": "session one"}])
        other = [{"role": "system", "content": "A different agent."}]
        fixed, _ = gw._ensure_user_turn(other + BROKEN[1:])
        assert fixed[1]["content"] == gw.PLACEHOLDER_USER  # no bleed across system prompts


# --- OpenAI <-> Ollama message translation -------------------------------------------------
@pytest.mark.unit
class TestMessageTranslation:
    def test_tool_arguments_string_becomes_object(self, gw):
        out = gw._to_ollama_messages(BROKEN)
        assert out[1]["tool_calls"][0]["function"]["arguments"] == {"path": "main.py"}

    def test_tool_call_id_resolves_to_tool_name(self, gw):
        # Ollama identifies a tool result by name, OpenAI by id.
        assert gw._to_ollama_messages(BROKEN)[2]["tool_name"] == "read_file"

    def test_null_assistant_content_becomes_empty_string(self, gw):
        assert gw._to_ollama_messages(BROKEN)[1]["content"] == ""

    def test_multipart_content_is_flattened(self, gw):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello "},
                                             {"type": "text", "text": "world"}]}]
        assert gw._to_ollama_messages(msgs)[0]["content"] == "hello world"

    def test_unparseable_arguments_survive_as_raw(self, gw):
        msgs = [{"role": "assistant", "content": "",
                 "tool_calls": [{"id": "c1", "function": {"name": "f", "arguments": "{not json"}}]}]
        args = gw._to_ollama_messages(msgs)[0]["tool_calls"][0]["function"]["arguments"]
        assert args == {"_raw": "{not json"}


@pytest.mark.unit
class TestResponseTranslation:
    OLLAMA_TOOL_REPLY = {
        "message": {"role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": "run_shell_command",
                                                 "arguments": {"cmd": "ls -la"}}}]},
        "done_reason": "stop", "prompt_eval_count": 1200, "eval_count": 40,
    }

    def test_tool_calls_set_finish_reason(self, gw):
        out = gw._openai_response("qwen3.8:27b", self.OLLAMA_TOOL_REPLY)
        assert out["choices"][0]["finish_reason"] == "tool_calls"

    def test_arguments_serialize_back_to_json_string(self, gw):
        out = gw._openai_response("qwen3.8:27b", self.OLLAMA_TOOL_REPLY)
        call = out["choices"][0]["message"]["tool_calls"][0]
        assert call["function"]["arguments"] == '{"cmd": "ls -la"}'
        assert call["id"].startswith("call_")

    def test_usage_is_totalled(self, gw):
        out = gw._openai_response("qwen3.8:27b", self.OLLAMA_TOOL_REPLY)
        assert out["usage"]["total_tokens"] == 1240

    def test_length_done_reason_maps_through(self, gw):
        out = gw._openai_response("m", {"message": {"content": "hi"}, "done_reason": "length"})
        assert out["choices"][0]["finish_reason"] == "length"
        assert "tool_calls" not in out["choices"][0]["message"]


# --- Payload construction: num_ctx and think are the whole point of not using /v1 ----------
@pytest.mark.unit
class TestPayload:
    def test_num_ctx_comes_from_the_per_model_map(self, gw):
        p = gw._build_payload({"model": "qwen3.8:27b"}, [], stream=False)
        assert p["options"]["num_ctx"] == 122880

    def test_unmapped_model_uses_the_default(self, gw):
        p = gw._build_payload({"model": "other:7b"}, [], stream=False)
        assert p["options"]["num_ctx"] == 32768

    def test_think_is_disabled_by_default(self, gw):
        assert gw._build_payload({"model": "m"}, [], stream=False)["think"] is False

    def test_reasoning_effort_overrides_think(self, gw):
        assert gw._build_payload({"model": "m", "reasoning_effort": "none"}, [], False)["think"] is False
        assert gw._build_payload({"model": "m", "reasoning_effort": "high"}, [], False)["think"] == "high"

    def test_sampling_params_are_forwarded(self, gw):
        p = gw._build_payload({"model": "m", "temperature": 0.2, "max_tokens": 8192}, [], False)
        assert p["options"]["temperature"] == 0.2
        assert p["options"]["num_predict"] == 8192


# --- ollama #17825: the poisoned retry -----------------------------------------------------
@pytest.mark.unit
class TestPoisonGuard:
    def test_signature_is_stable_and_model_scoped(self, gw):
        msgs = gw._to_ollama_messages(BROKEN)
        sig = gw._PoisonGuard.signature("qwen3.8:27b", msgs, None)
        assert gw._PoisonGuard.signature("qwen3.8:27b", msgs, None) == sig
        assert gw._PoisonGuard.signature("other:7b", msgs, None) != sig

    def test_mark_then_clear_round_trip(self, gw):
        guard = gw._PoisonGuard()
        sig = "deadbeef"
        assert guard.is_poisoned(sig) is False
        guard.mark(sig)
        assert guard.is_poisoned(sig) is True
        guard.clear(sig)
        assert guard.is_poisoned(sig) is False

    def test_entries_expire(self, gw, monkeypatch):
        # Negative, not 0.0: the sweep compares `elapsed > TTL`, and elapsed is ~0 here.
        monkeypatch.setattr(gw, "POISON_TTL", -1.0)
        guard = gw._PoisonGuard()
        guard.mark("sig")
        assert guard.is_poisoned("sig") is False


# --- Narrowing the poison guard (2026-09-13 incident) -------------------------------------
@pytest.mark.unit
class TestPoisonNarrowing:
    """A live qwen3.8 session 500'd under prompt-cache memory pressure at a 64k prompt, then
    recovered on its own. The guard poisoned it and turned a transient blip into a 90s outage.
    Only a genuine #17825 tool-parse failure may block retries now."""

    def test_tool_parse_failure_is_poisoned(self, gw):
        assert gw._PoisonGuard.should_poison(
            500, 'failed to parse tool call: invalid character', has_tools=True) is True

    def test_memory_pressure_500_is_retryable(self, gw):
        """The actual incident: no tools, no parse error — must stay retryable."""
        assert gw._PoisonGuard.should_poison(
            500, 'failed to save prompt cache state', has_tools=True) is False

    def test_500_without_tools_is_never_17825(self, gw):
        """#17825 is specifically a tool-call parse failure; no tools means it cannot apply."""
        assert gw._PoisonGuard.should_poison(
            500, 'failed to parse tool call', has_tools=False) is False

    def test_non_500_is_never_poisoned(self, gw):
        for code in (400, 404, 502, 503, 504):
            assert gw._PoisonGuard.should_poison(
                code, 'failed to parse tool call', has_tools=True) is False

    def test_empty_body_is_retryable(self, gw):
        """If we cannot see why it failed, prefer a slow retry over a blocked one."""
        assert gw._PoisonGuard.should_poison(500, '', has_tools=True) is False
        assert gw._PoisonGuard.should_poison(500, None, has_tools=True) is False

    def test_no_user_query_500_is_retryable(self, gw):
        """The #9438 error is repaired upstream of this; it must never poison a signature."""
        assert gw._PoisonGuard.should_poison(
            500, 'no user query found in messages', has_tools=True) is False


# --- Multimodal passthrough ----------------------------------------------------------------
@pytest.mark.unit
class TestImagePassthrough:
    """qwen3.8:27b reports the 'vision' capability and loads a CLIP encoder. OpenAI sends images
    as content parts; Ollama wants a sibling "images" list of raw base64. Dropping them silently
    is the worst failure here — the model answers as if blind and the reply still looks fine."""

    IMG = {"type": "image_url",
           "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="}}

    def test_data_uri_becomes_raw_base64(self, gw):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "what is this?"}, self.IMG]}]
        out = gw._to_ollama_messages(msgs)[0]
        assert out["images"] == ["iVBORw0KGgoAAAANSUhEUg=="]  # data: prefix stripped

    def test_text_still_survives_alongside_the_image(self, gw):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "what is this?"}, self.IMG]}]
        assert gw._to_ollama_messages(msgs)[0]["content"] == "what is this?"

    def test_multiple_images_are_all_carried(self, gw):
        msgs = [{"role": "user", "content": [self.IMG, self.IMG]}]
        assert len(gw._to_ollama_messages(msgs)[0]["images"]) == 2

    def test_no_images_key_when_text_only(self, gw):
        """Adding an empty images list to every message would be noise upstream."""
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        assert "images" not in gw._to_ollama_messages(msgs)[0]

    def test_plain_string_content_is_unaffected(self, gw):
        assert "images" not in gw._to_ollama_messages([{"role": "user", "content": "hi"}])[0]

    def test_remote_url_is_refused_not_silently_dropped(self, gw):
        """Fetching a remote URL server-side would be an SSRF vector; we warn and omit instead."""
        msgs = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}}]}]
        assert "images" not in gw._to_ollama_messages(msgs)[0]
