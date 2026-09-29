"""
OpenRouter model catalogue — live, cached, additive-only.

OpenRouter publishes its model list at GET /api/v1/models and needs no key to read
it, so the list is fetched rather than transcribed. A hardcoded copy would hide every
model added after the commit that wrote it, which is the whole point of a gateway.

The cache exists for a second reason, and it is the one that matters for correctness.
Ids here are `vendor/model`, and the NVIDIA catalogue already ships
`mistralai/mistral-nemotron` and `deepseek-ai/deepseek-v4-pro`, so an id cannot be
claimed by prefix — `providers/registry.py` warns about exactly that. Dispatch is
therefore by *membership*, and membership needs a set to test against even when the
network is down. Hence FALLBACK below, and hence `refresh` only ever ADDS ids: a
model a user can already see in the picker must never disappear because a fetch
returned a shorter list or failed outright.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger("openrouter_catalogue")

MODELS_URL = "https://openrouter.ai/api/v1/models"
TTL_SECONDS = 3600

# Enough for a turn to route correctly after a restart, before the first fetch
# lands. Deliberately small: these are not the catalogue, they are a floor.
#
# Chosen to be ids no curated provider already claims. `openai/gpt-4o` is a real
# OpenRouter id and would be the obvious pick, but GITHUB_MODELS owns that spelling
# (registry.py indexes GitHub first and the first binding wins), so listing it here
# would advertise a model that can never route this way.
FALLBACK: tuple[str, ...] = (
    "openrouter/auto",
    "meta-llama/llama-3.1-70b-instruct",
    "deepseek/deepseek-chat",
    "anthropic/claude-3.5-sonnet",
)

_lock = threading.Lock()
_ids: set[str] = set(FALLBACK)
_labels: dict[str, dict[str, Any]] = {}
_last_fetch: float = 0.0
_last_error: Optional[str] = None


def _parse(payload: Any) -> list[dict[str, Any]]:
    """OpenRouter shape: {"data": [{"id", "name", "context_length", ...}, ...]}."""
    rows = payload.get("data") if isinstance(payload, dict) else None
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("id") or "").strip()
        if not mid:
            continue
        ctx = row.get("context_length") or row.get("top_provider", {}).get("context_length")
        try:
            context = int(ctx) if ctx else 0
        except (TypeError, ValueError):
            context = 0
        out.append({
            "id": mid,
            "label": str(row.get("name") or mid),
            "context": context,
        })
    return out


def refresh(force: bool = False, api_key: str = "", timeout: float = 10.0) -> bool:
    """Fetch the upstream list and ADD it to the cache. Returns True on a good fetch.

    Never subtracts: an id already known stays known even if this response omits it.
    """
    global _last_fetch, _last_error
    with _lock:
        if not force and _last_fetch and (time.time() - _last_fetch) < TTL_SECONDS:
            return True
    try:
        import urllib.request
        headers = {"Accept": "application/json", "User-Agent": "memex-agent-runtime"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(MODELS_URL, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        rows = _parse(payload)
        if not rows:
            # A well-formed but empty answer is treated as a failure: it would leave
            # the cache looking authoritative while knowing nothing.
            raise ValueError("upstream returned no models")
    except Exception as e:
        _last_error = str(e)
        logger.warning(f"openrouter catalogue refresh failed: {e}")
        return False

    with _lock:
        for row in rows:
            _ids.add(row["id"])
            _labels[row["id"]] = row
        _last_fetch = time.time()
        _last_error = None
    logger.info(f"openrouter catalogue: {len(rows)} models fetched, {len(_ids)} known")
    return True


def known_ids() -> set[str]:
    with _lock:
        return set(_ids)


def models() -> list[dict[str, Any]]:
    """The cached catalogue, sorted for a stable UI. Empty ids are not a lie about
    the provider: `stale()` says when these came from FALLBACK rather than upstream."""
    with _lock:
        rows = list(_labels.values())
    if not rows:
        return [{"id": mid, "label": mid, "context": 0} for mid in sorted(FALLBACK)]
    return sorted(rows, key=lambda r: r["label"].lower())


def knows(model_id: str) -> bool:
    with _lock:
        return model_id in _ids


def stale() -> bool:
    with _lock:
        return not _labels or (time.time() - _last_fetch) > TTL_SECONDS


def status() -> dict[str, Any]:
    with _lock:
        return {
            "known": len(_ids),
            "fetched_at": _last_fetch or None,
            "stale": (not _labels) or (time.time() - _last_fetch) > TTL_SECONDS,
            "last_error": _last_error,
        }
