"""
Model → provider lookup.

Catalog ids are stored verbatim in the form upstream APIs accept
(e.g. `openai/gpt-4o`, `nvidia/llama-3.1-nemotron-70b-instruct`).
Use provider_for() to dispatch instead of prefix-matching the model id,
since publisher prefixes (`openai/`, `meta/`, `mistralai/`, …) collide
across providers.
"""

from __future__ import annotations

from typing import Optional


def _build_index() -> dict[str, str]:
    index: dict[str, str] = {}
    try:
        from providers.github_models_provider import GITHUB_MODELS
        for m in GITHUB_MODELS:
            index[m["id"]] = "github"
    except Exception:
        pass
    try:
        from provider_keys import PROVIDERS
        for provider_id, info in PROVIDERS.items():
            for m in info.get("models", []):
                index[m["id"]] = provider_id
    except Exception:
        pass
    # OpenRouter's catalogue is fetched rather than declared, so it is merged last and
    # with setdefault: a gateway that carries `mistralai/mistral-nemotron` must not
    # take an id NVIDIA's curated list already owns — the collision this module's
    # docstring warns about, arriving from the data instead of the prefix.
    try:
        from providers.openrouter_catalogue import known_ids
        for mid in known_ids():
            index.setdefault(mid, "openrouter")
    except Exception:
        pass
    return index


def provider_for(model_id: str) -> Optional[str]:
    return _build_index().get(model_id)


def provider_key_connected(provider: str, uid: str) -> bool:
    """Does this user hold a key that makes `provider` usable right now?

    Lives here rather than at the call site because the answer is what turns a
    catalogue entry into an entitlement, and two callers need it identically: the
    model gate in main.py and the picker list. Keys are stored per X-authentik-uid,
    so that is the identity used — not the permission owner, which prefers a
    username when one is present.
    """
    if not provider or not uid:
        return False
    try:
        from provider_keys import get_key
        return bool(get_key(uid, provider))
    except Exception:
        return False


def provider_selection(uid: str, provider: str) -> Optional[list[str]]:
    """The models this user opted into, or None when no key is connected.

    The two states are distinct on purpose and callers must not collapse them:
    None means "cannot serve this provider at all", an empty list means
    "connected, nothing chosen yet" — which for a live-catalogue provider offers
    zero models rather than all of them.
    """
    if not provider or not uid:
        return None
    try:
        from provider_keys import get_key
        record = get_key(uid, provider)
        return record.get_selection() if record else None
    except Exception:
        return None
