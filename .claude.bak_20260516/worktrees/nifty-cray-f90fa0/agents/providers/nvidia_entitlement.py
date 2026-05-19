"""
Per-user entitlement filter for NVIDIA NIM.

NVIDIA's `integrate.api.nvidia.com` returns 404 (not 403) when a key isn't
entitled to a specific model, so the only reliable way to build a per-user
accessible-model list is to ping each model with a 1-token probe.

Results are cached in-process per user. Cache is invalidated when the user
re-uploads or deletes their NVIDIA key.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("nvidia_entitlement")

CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
CACHE_TTL = 6 * 60 * 60        # 6 h
PROBE_TIMEOUT = 6              # seconds per model
PROBE_PARALLELISM = 6

# user_id -> (timestamp, allowed_ids)
_cache: dict[str, tuple[float, set[str]]] = {}


def _probe_one(model_id: str, api_key: str) -> tuple[str, bool]:
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        CHAT_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as r:
            r.read(64)
        return (model_id, True)
    except urllib.error.HTTPError as e:
        # 404/410: model exists but key not entitled. 401/403: bad key.
        # Anything else (5xx, rate limit): fail open so UI isn't gutted by
        # transient upstream issues.
        if e.code in (401, 403, 404, 410):
            return (model_id, False)
        return (model_id, True)
    except Exception:
        return (model_id, True)


def accessible_models(user_id: str, candidate_ids: list[str], api_key: str) -> set[str]:
    """Return the subset of `candidate_ids` the user's key can call.

    Synchronous on cache miss (~1-3 s for 6 models in parallel). After that,
    served from cache for CACHE_TTL.
    """
    now = time.time()
    cached = _cache.get(user_id)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1] & set(candidate_ids)

    with ThreadPoolExecutor(max_workers=PROBE_PARALLELISM) as pool:
        results = list(pool.map(lambda mid: _probe_one(mid, api_key), candidate_ids))

    allowed = {mid for mid, ok in results if ok}
    _cache[user_id] = (now, allowed)
    logger.info(
        f"nvidia_entitlement: uid={user_id[:8]} allowed={len(allowed)}/{len(candidate_ids)} "
        f"({sorted(set(candidate_ids) - allowed)} blocked)"
    )
    return allowed


def invalidate(user_id: str) -> None:
    _cache.pop(user_id, None)
