"""Tests for `providers.model_client` — plan D8's first piece.

The module answers one question, and it has to be answered before any Ollama-specific
option is computed: *who can actually serve this model id?*

Two of these tests exist because of a measurement, not a guess:

* A freshly started process's fetched catalogue holds the **four** fallback ids, while the
  running server holds 464. So `provider_for` alone answers "not a provider model" about a
  gateway id the user genuinely selected, and a caller that believed it would build an
  Ollama client for a tag no GPU host has ever seen. The user's stored selection is the
  durable answer, and `test_cold_catalogue_does_not_send_a_gateway_id_to_ollama` is the
  regression guard for that.
* A phi model object prints its own fields, so the API key this module hands it is visible
  in `repr()`. Every caller must therefore treat the returned object as secret-bearing;
  `test_the_returned_client_holds_the_key_and_prints_it` pins the behaviour so a phi
  upgrade that hides it is noticed rather than assumed.

Nothing here touches the database or the network: the two lookups are patched, which is
also what makes the cold-catalogue case reproducible.

The skip below is per-test, not per-module, and that is deliberate. `providers.model_client`
imports phi *inside* `model_client`, so the two questions that actually decide behaviour —
"is this a model or a tier", "which provider serves this id" — are testable without the
framework installed. Only the tests that construct a client need it. On this machine the
host has pytest and no phi while the container has phi and no pytest, so a module-level
skip would have meant a test file that runs nowhere.
"""
import importlib.util
import os
import sys

import pytest

_AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)

def _has_phi_openrouter() -> bool:
    """`find_spec` on a dotted name raises when the parent package is absent, which is
    exactly the case this is checking for on a machine without phidata."""
    try:
        return importlib.util.find_spec("phi.model.openrouter") is not None
    except (ImportError, ValueError):
        return False


requires_phi = pytest.mark.skipif(
    not _has_phi_openrouter(),
    reason="phidata not installed in this environment",
)

import providers.registry as reg
import provider_keys as pk
from providers.model_client import (
    ProviderNotServed,
    is_honourable_pick,
    model_client,
    provider_of,
)

GATEWAY_ID = "qwen/qwen3.8-flash"


@pytest.fixture
def cold_catalogue(monkeypatch):
    """`provider_for` answers nothing, as it does in a process that has not fetched."""
    monkeypatch.setattr(reg, "provider_for", lambda _mid: None)


@pytest.fixture
def selection(monkeypatch):
    """The user has OpenRouter connected with GATEWAY_ID chosen."""
    monkeypatch.setattr(pk, "list_connected", lambda _uid: [{
        "provider": "openrouter",
        "label": "OpenRouter",
        "connected_at": "2026-09-29T00:00:00",
        "selected_models": [GATEWAY_ID],
    }])


class TestPickIsAModelNotATier:
    def test_ui_tier_names_are_not_honourable(self):
        for tier in ("Home-AI-Swarm", "swarm", "hive-fast", "default", "", "   ".strip()):
            assert is_honourable_pick(tier) is False, tier

    def test_a_gateway_id_and_a_plain_tag_are_both_honourable(self):
        # The whole point: the old guard threw away both because one of them was a tier.
        assert is_honourable_pick(GATEWAY_ID) is True
        assert is_honourable_pick("qwen3:14b") is True


class TestProviderOf:
    def test_the_index_wins_when_it_answers(self, monkeypatch):
        monkeypatch.setattr(reg, "provider_for", lambda _mid: "nvidia")
        assert provider_of("mistralai/mistral-nemotron", "someone") == "nvidia"

    def test_cold_catalogue_does_not_send_a_gateway_id_to_ollama(self, cold_catalogue, selection):
        # provider_for knows nothing here, and the answer is still the provider — because
        # the selection is a Postgres row, not an in-memory cache.
        assert provider_of(GATEWAY_ID, "Justin") == "openrouter"

    def test_without_a_uid_a_cold_index_is_answered_honestly(self, cold_catalogue):
        # No session, no lookup, and no invented claim: None means "I could not
        # establish a provider", which the caller must not read as "therefore Ollama".
        assert provider_of(GATEWAY_ID) is None

    def test_an_id_in_no_selection_and_no_index_is_not_a_provider_model(self, cold_catalogue, selection):
        assert provider_of("qwen3:14b", "Justin") is None

    def test_a_store_that_will_not_answer_is_not_evidence_of_absence(self, cold_catalogue, monkeypatch):
        def boom(_uid):
            raise RuntimeError("database is down")

        monkeypatch.setattr(pk, "list_connected", boom)
        assert provider_of(GATEWAY_ID, "Justin") is None  # logged, not raised


@requires_phi
class TestModelClient:
    def test_a_tier_name_is_refused_before_any_client_is_built(self):
        with pytest.raises(ValueError):
            model_client("Home-AI-Swarm", "Justin")

    def test_a_gateway_id_builds_an_openrouter_client_not_an_ollama_one(self, cold_catalogue, selection, monkeypatch):
        monkeypatch.setattr(pk, "get_key", lambda _uid, _p: type("R", (), {"get_api_key": lambda s: "sk-or-test-value"})())
        client = model_client(GATEWAY_ID, "Justin")
        assert type(client).__name__ == "OpenRouter"
        assert client.id == GATEWAY_ID

    def test_the_returned_client_holds_the_key_and_prints_it(self, cold_catalogue, selection, monkeypatch):
        monkeypatch.setattr(pk, "get_key", lambda _uid, _p: type("R", (), {"get_api_key": lambda s: "sk-or-test-value"})())
        client = model_client(GATEWAY_ID, "Justin")
        # Asserted rather than assumed: this is why no caller may interpolate the object
        # into a log line or an exception message.
        assert "sk-or-test-value" in repr(client)

    def test_a_missing_key_refuses_with_the_control_that_fixes_it(self, cold_catalogue, selection, monkeypatch):
        monkeypatch.setattr(pk, "get_key", lambda _uid, _p: None)
        with pytest.raises(ProviderNotServed) as raised:
            model_client(GATEWAY_ID, "Justin")
        assert "Settings → Model providers" in str(raised.value)
        assert "sk-or-" not in str(raised.value)

    def test_a_provider_with_no_client_yet_is_named_rather_than_falled_back_through(self, monkeypatch):
        monkeypatch.setattr(reg, "provider_for", lambda _mid: "nvidia")
        with pytest.raises(ProviderNotServed) as raised:
            model_client("mistralai/mistral-nemotron", "Justin")
        assert "nvidia" in str(raised.value)

    def test_an_unauthenticated_session_cannot_reach_for_a_key(self, cold_catalogue, selection):
        with pytest.raises(ProviderNotServed):
            model_client(GATEWAY_ID, "")
