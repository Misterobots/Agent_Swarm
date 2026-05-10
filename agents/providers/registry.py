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
    return index


def provider_for(model_id: str) -> Optional[str]:
    return _build_index().get(model_id)
