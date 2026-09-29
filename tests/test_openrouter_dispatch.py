"""OpenRouter dispatch in providers/registry.py.

The gateway's ids are `vendor/model`, and the NVIDIA catalogue already owns
`mistralai/mistral-nemotron` and `deepseek-ai/deepseek-v4-pro`. registry.py's own
docstring warns against prefix-matching for exactly this reason, so the only safe
signal is membership in a catalogue — which makes two field failures possible and
both of them silent: a connected model that never routes, and a curated model that
quietly reroutes to the gateway because the gateway happens to list it too.

Nothing here touches the network. The cache is set directly, because the property
under test is how membership is resolved, not what OpenRouter returned today.
"""
import os
import sys

import pytest

# tests/conftest.py puts agents/ on sys.path, and that holds when this file is run on
# its own — but in a whole-directory collection it does not, which is also why
# test_node_vram_reporting.py errors there while passing alone. Repeating the insert
# here is duplication; being collectable in the run people actually make is the point.
_AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)

import provider_keys
import providers.openrouter_catalogue as cat
import providers.registry as reg


@pytest.fixture
def catalogue(monkeypatch):
    """A cache holding one id per outcome: gateway-only, NVIDIA-claimed, GitHub-claimed."""
    ids = {
        "meta-llama/llama-3.1-70b-instruct",  # declared by no one else
        "mistralai/mistral-nemotron",         # also in provider_keys.PROVIDERS["nvidia"]
        "openai/gpt-4o",                      # also in GITHUB_MODELS
    }
    monkeypatch.setattr(cat, "_ids", set(ids))
    monkeypatch.setattr(cat, "_labels", {i: {"id": i, "label": i, "context": 8192} for i in ids})
    monkeypatch.setattr(cat, "_last_fetch", 9_999_999_999.0)  # fresh, so nothing refreshes
    return ids


def test_an_unclaimed_gateway_id_routes_to_openrouter(catalogue):
    assert reg.provider_for("meta-llama/llama-3.1-70b-instruct") == "openrouter"


def test_a_curated_nvidia_id_is_not_stolen_by_the_gateway(catalogue):
    # The regression this whole design exists to avoid: the id is in both lists, and
    # the curated provider was declared first.
    assert "mistralai/mistral-nemotron" in catalogue
    assert "mistralai/mistral-nemotron" in [m["id"] for m in provider_keys.PROVIDERS["nvidia"]["models"]]
    assert reg.provider_for("mistralai/mistral-nemotron") == "nvidia"


def test_a_github_claimed_id_is_not_stolen_either(catalogue):
    # Found by running the first version of this test rather than by reading the
    # catalogue: GITHUB_MODELS owns every `openai/*` spelling, so the models a user is
    # most likely to reach for on OpenRouter route to GitHub. The gateway list is
    # therefore never authoritative over a declared one, and the client has to say so
    # rather than offer the id as an ordinary pick.
    from providers.github_models_provider import GITHUB_MODELS
    assert "openai/gpt-4o" in [m["id"] for m in GITHUB_MODELS]
    assert reg.provider_for("openai/gpt-4o") == "github"


def test_a_local_model_is_not_claimed_by_any_provider(catalogue):
    assert reg.provider_for("qwen3:8b") is None


def test_openrouter_declares_a_live_catalogue_and_the_others_stay_curated():
    info = provider_keys.PROVIDERS["openrouter"]
    assert info["live_models"] is True
    assert info["models"] == []
    assert info["key_prefix"] == "sk-or-"
    for curated in ("anthropic", "google", "nvidia"):
        assert provider_keys.PROVIDERS[curated]["models"], f"{curated} must keep its declared list"
        assert not provider_keys.PROVIDERS[curated].get("live_models")


def test_refresh_may_only_add_ids(monkeypatch):
    """A shorter upstream answer must not drop a model a user can already see."""
    monkeypatch.setattr(cat, "_ids", {"openai/gpt-4o", "meta-llama/llama-3.1-70b-instruct"})
    monkeypatch.setattr(cat, "_labels", {})

    class _Resp:
        def read(self):
            return b'{"data": [{"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000}]}'
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    assert cat.refresh(force=True) is True
    assert "meta-llama/llama-3.1-70b-instruct" in cat.known_ids()
    assert "openai/gpt-4o" in cat.known_ids()


def test_an_empty_answer_is_a_failure_not_an_empty_catalogue(monkeypatch):
    """A well-formed `{"data": []}` would otherwise make the provider look keyless."""
    monkeypatch.setattr(cat, "_ids", {"openai/gpt-4o"})

    class _Resp:
        def read(self):
            return b'{"data": []}'
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    assert cat.refresh(force=True) is False
    assert cat.known_ids() == {"openai/gpt-4o"}


def test_a_cold_cache_still_offers_the_floor_and_says_so(monkeypatch):
    monkeypatch.setattr(cat, "_ids", set(cat.FALLBACK))
    monkeypatch.setattr(cat, "_labels", {})
    monkeypatch.setattr(cat, "_last_fetch", 0.0)
    assert {m["id"] for m in cat.models()} == set(cat.FALLBACK)
    assert cat.stale() is True
    assert cat.status()["stale"] is True


def test_the_floor_holds_only_ids_that_actually_route_here():
    # A cold cache is the only state a restart guarantees, so an id in FALLBACK that
    # some curated provider owns would advertise a model that can never arrive.
    for mid in cat.FALLBACK:
        assert reg.provider_for(mid) == "openrouter", mid
