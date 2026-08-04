"""Fuzzy-matching + learned-synonym resolution of Home Assistant area/entity names.

HA's own literal intent-matching (confirmed live: HassTurnOn/Off/HassLightSet/HassToggle
reject anything that isn't an EXACT string match against a real area or entity name — no
partial match, no alias fallback for the LLM-tool-calling path bmo_brain drives) means a
phrase like "second floor hall" never resolves against a real area actually named
"Upstairs", even though a person would recognize them as the same room. This module sits
between the model's raw tool_call arguments and what gets sent back to HA: it rewrites
`area`/`name` to the closest real HA name BEFORE the tool_call is returned, so HA's literal
match has a fighting chance.

Five-stage pipeline, cheapest/most-trusted first, each stage only reached if the previous
one missed:
  1. exact match against a live-fetched HA area/entity list (cached, TTL-refreshed)
  2. a learned-synonym SQLite table (hass_synonyms.py) — anything taught before, either by
     a confident fuzzy/embedding hit or by a real observed correction, resolves for free
  3. stdlib difflib fuzzy string matching (no new pip dependency) — catches typos, partial
     names, pluralization
  4. an OPTIONAL embedding-similarity fallback (off by default, HASS_EMBED_FALLBACK) that
     can bridge phrases sharing no characters with the real name (e.g. "second floor" vs
     "Upstairs") using Ollama's already-warm nomic-embed-text — area names only, since
     entity-name resolution is the secondary, lower-frequency path here (HA area+name
     targeting already prefers dropping `name` in favor of `area` — see main.py) and
     re-embedding a household's full entity list on every registry refresh would be
     needless cost for a rarely-hit stage.
  5. give up — the tool_call's argument is left completely unmodified, so HA's own
     literal-match failure (and bmo_brain's existing clarify-question flow) behaves exactly
     as it does today. Loose near-miss candidates are still available via
     top_candidates() to make that clarifying question name real rooms instead of asking
     generically.

Every stage before the optional embedding one is sub-millisecond and does no I/O. The
registry itself is fetched over HA's REST /api/template endpoint (Jinja2 template
rendering, one round trip) rather than the WebSocket registry APIs, specifically so this
adds no new pip dependency beyond the httpx bmo_brain already depends on.
"""
import difflib
import logging
import os
import re
import time
from dataclasses import dataclass

import httpx

import hass_synonyms

logger = logging.getLogger(__name__)

HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "http://192.168.2.100:8123").rstrip("/")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")

# Same Ollama host bmo_brain already calls for /api/chat also already serves
# nomic-embed-text as part of its small-model fast path (MemPalace uses the identical
# {OLLAMA_URL}/api/embed pattern) — no new infrastructure for the optional stage 4.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.2.101:11434").rstrip("/")
EMBED_MODEL = os.getenv("HASS_EMBED_MODEL", "nomic-embed-text")

REGISTRY_TTL = float(os.getenv("HASS_REGISTRY_TTL", "300"))
FUZZY_CUTOFF = float(os.getenv("HASS_FUZZY_CUTOFF", "0.72"))
# Stricter than FUZZY_CUTOFF on purpose: a 0.74 one-off match is fine to USE once, not fine
# to PERMANENTLY memorize as a synonym without ever seeing it repeated or confirmed.
LEARN_THRESHOLD = float(os.getenv("HASS_LEARN_THRESHOLD", "0.90"))
EMBED_FALLBACK = os.getenv("HASS_EMBED_FALLBACK", "false").strip().lower() in ("1", "true", "yes")
EMBED_THRESHOLD = float(os.getenv("HASS_EMBED_THRESHOLD", "0.55"))

_FILLER_WORDS = {"the", "lights", "light", "lamp", "lamps"}

_registry_cache = {
    "areas": [],       # list of (area_id, name)
    "entities": [],    # list of (entity_id, name)
    "area_by_norm": {},    # {normalized_name: (area_id, name)}
    "entity_by_norm": {},  # {normalized_name: (entity_id, name)}
    "area_by_id": {},      # {area_id: name}
    "entity_by_id": {},    # {entity_id: name}
    "area_embeddings": {},  # {area_id: [float, ...]} — only populated when EMBED_FALLBACK
    "fetched_at": 0.0,
}


@dataclass
class ResolveResult:
    value: str              # what to put back in the tool_call argument
    target_id: str | None   # canonical area_id / entity_id, None if unresolved
    confidence: float
    method: str              # "exact" | "learned" | "fuzzy" | "embedding" | "none"


def _normalize(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"[^a-z0-9 ]", "", raw.lower())
    s = re.sub(r"\s+", " ", s).strip()
    words = [w for w in s.split(" ") if w and w not in _FILLER_WORDS]
    return " ".join(words) if words else s


_REGISTRY_TEMPLATE = (
    "{{ {"
    "'area_ids': areas() | list, "
    "'area_names': areas() | map('area_name') | list, "
    "'entity_ids': states | map(attribute='entity_id') | list, "
    "'entity_names': states | map(attribute='name') | list"
    "} | tojson }}"
)


async def _fetch_registry() -> dict:
    """One POST to HA's /api/template — returns {"areas": [(id, name), ...],
    "entities": [(id, name), ...]}. Raises on any failure; caller catches."""
    import json
    async with httpx.AsyncClient(timeout=8.0) as c:
        r = await c.post(
            f"{HOME_ASSISTANT_URL}/api/template",
            headers={"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
                      "Content-Type": "application/json"},
            json={"template": _REGISTRY_TEMPLATE},
        )
        r.raise_for_status()
        data = json.loads(r.text)
    area_ids, area_names = data.get("area_ids", []), data.get("area_names", [])
    entity_ids, entity_names = data.get("entity_ids", []), data.get("entity_names", [])
    # The two lists in each pair are independently-evaluated Jinja2 expressions — zip()
    # would silently misalign id<->name pairs (every subsequent pairing shifted by one) if
    # HA ever returns mismatched lengths for either. Discard rather than risk resolving a
    # phrase to the WRONG area/entity id with no visible error anywhere in the pipeline.
    if len(area_ids) != len(area_names):
        logger.warning("hass_resolver: area_ids/area_names length mismatch (%d vs %d) — "
                        "discarding areas this refresh rather than risk misaligned pairs",
                        len(area_ids), len(area_names))
        area_ids, area_names = [], []
    if len(entity_ids) != len(entity_names):
        logger.warning("hass_resolver: entity_ids/entity_names length mismatch (%d vs %d) — "
                        "discarding entities this refresh rather than risk misaligned pairs",
                        len(entity_ids), len(entity_names))
        entity_ids, entity_names = [], []
    areas = list(zip(area_ids, area_names))
    entities = list(zip(entity_ids, entity_names))
    return {"areas": areas, "entities": entities}


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _embed_texts(texts: list) -> list:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": texts})
        r.raise_for_status()
        return r.json()["embeddings"]


async def _refresh_area_embeddings(registry: dict) -> None:
    """Only ever called when EMBED_FALLBACK is on, and only for areas (typically a dozen
    or two strings for a household) — never for the full entity list, which would be
    needless re-embedding cost every REGISTRY_TTL for a stage this rarely reached."""
    if not EMBED_FALLBACK:
        return
    areas = [(area_id, name) for area_id, name in registry["areas"] if name]
    if not areas:
        registry["area_embeddings"] = {}
        return
    try:
        vecs = await _embed_texts([name for _, name in areas])
        registry["area_embeddings"] = {area_id: vec for (area_id, _name), vec in zip(areas, vecs)}
    except Exception as e:  # noqa: BLE001
        logger.warning("hass_resolver embedding refresh failed (non-fatal): %s", e)


async def _get_registry() -> dict:
    """TTL-cached registry snapshot. Inert (returns the empty/stale cache, never raises or
    blocks) if HOME_ASSISTANT_TOKEN isn't configured, or if the fetch fails — a fetch
    failure still stamps fetched_at so a down/unreachable HA is retried at most once per
    REGISTRY_TTL window, never on every single request."""
    if not HOME_ASSISTANT_TOKEN:
        return _registry_cache
    now = time.time()
    if now - _registry_cache["fetched_at"] < REGISTRY_TTL:
        return _registry_cache
    _registry_cache["fetched_at"] = now
    try:
        fresh = await _fetch_registry()
        _registry_cache["areas"] = fresh["areas"]
        _registry_cache["entities"] = fresh["entities"]
        _registry_cache["area_by_norm"] = {
            _normalize(name): (area_id, name) for area_id, name in fresh["areas"] if name
        }
        _registry_cache["entity_by_norm"] = {
            _normalize(name): (entity_id, name) for entity_id, name in fresh["entities"] if name
        }
        _registry_cache["area_by_id"] = {area_id: name for area_id, name in fresh["areas"] if name}
        _registry_cache["entity_by_id"] = {entity_id: name for entity_id, name in fresh["entities"] if name}
        await _refresh_area_embeddings(_registry_cache)
    except Exception as e:  # noqa: BLE001
        logger.warning("hass_resolver registry refresh failed (serving stale/empty cache): %s", e)
    return _registry_cache


def _fuzzy_candidates(normalized: str, by_norm: dict, cutoff: float, limit: int = 3) -> list:
    """by_norm: {normalized_name: (id, display_name)}. Returns [((id, display_name), ratio), ...]
    sorted best-first, ratio >= cutoff."""
    if not normalized or not by_norm:
        return []
    norms = list(by_norm.keys())
    close = difflib.get_close_matches(normalized, norms, n=limit, cutoff=cutoff)
    out = []
    for c in close:
        ratio = difflib.SequenceMatcher(None, normalized, c).ratio()
        out.append((by_norm[c], ratio))
    out.sort(key=lambda pair: -pair[1])
    return out


async def _embed_best_match(raw: str, kind: str, registry: dict):
    """Returns ((area_id, display_name), cosine) or None. Area-only in v1 — see module
    docstring for why entity-name embedding matching is out of scope."""
    if kind != "area":
        return None
    embeddings = registry.get("area_embeddings") or {}
    if not embeddings:
        return None
    try:
        vecs = await _embed_texts([raw])
        raw_vec = vecs[0]
    except Exception as e:  # noqa: BLE001
        logger.warning("hass_resolver embed query failed (non-fatal): %s", e)
        return None
    best_id, best_cosine = None, -1.0
    for area_id, vec in embeddings.items():
        cosine = _cosine(raw_vec, vec)
        if cosine > best_cosine:
            best_cosine, best_id = cosine, area_id
    if best_id is None:
        return None
    display_name = registry["area_by_id"].get(best_id, best_id)
    return (best_id, display_name), best_cosine


async def resolve(raw: str, kind: str, owner_id: str) -> ResolveResult:
    """kind is "area" or "entity". Never raises — any failure at any stage degrades to the
    next stage, and total failure returns method="none" with `value` unchanged from `raw`,
    so the caller can safely do `args[key] = result.value` unconditionally when
    method != "none" and otherwise leave the original tool_call argument untouched."""
    if not raw:
        return ResolveResult(value=raw, target_id=None, confidence=0.0, method="none")

    normalized = _normalize(raw)
    registry = await _get_registry()
    by_norm = registry["area_by_norm"] if kind == "area" else registry["entity_by_norm"]
    by_id = registry["area_by_id"] if kind == "area" else registry["entity_by_id"]

    # Stage 1: exact match against the live registry.
    hit = by_norm.get(normalized)
    if hit:
        target_id, display_name = hit
        return ResolveResult(value=display_name, target_id=target_id, confidence=1.0, method="exact")

    # Stage 2: learned synonym table — cheaper and more trusted than fresh fuzzy work.
    learned_id = hass_synonyms.lookup(kind, normalized, owner_id)
    if learned_id:
        # Re-derive the CURRENT display name by id, not whatever was stored at learn-time —
        # HA area_ids are stable, display names aren't (an area can be renamed later).
        display_name = by_id.get(learned_id, learned_id)
        return ResolveResult(value=display_name, target_id=learned_id, confidence=1.0, method="learned")

    # Stage 3: stdlib fuzzy string matching.
    fuzzy_hits = _fuzzy_candidates(normalized, by_norm, FUZZY_CUTOFF, limit=1)
    if fuzzy_hits:
        (target_id, display_name), ratio = fuzzy_hits[0]
        return ResolveResult(value=display_name, target_id=target_id, confidence=ratio, method="fuzzy")

    # Stage 4: optional embedding fallback — only for the narrow "some textual signal, but
    # not enough for stage 3" band; skips outright if there's no signal at all.
    if EMBED_FALLBACK:
        loose = _fuzzy_candidates(normalized, by_norm, cutoff=0.30, limit=5)
        if loose:
            embed_hit = await _embed_best_match(raw, kind, registry)
            if embed_hit and embed_hit[1] >= EMBED_THRESHOLD:
                (target_id, display_name), cosine = embed_hit
                return ResolveResult(value=display_name, target_id=target_id, confidence=cosine, method="embedding")

    # Stage 5: give up — caller must leave the original argument untouched.
    return ResolveResult(value=raw, target_id=None, confidence=0.0, method="none")


def resolve_cached(raw: str, kind: str, owner_id: str) -> ResolveResult:
    """Cache-only exact/learned lookup — never awaits, never triggers a registry fetch or
    embedding call. For callers confirming the target_id of a phrase that's already known
    to be correct (e.g. reactive synonym learning in main.py's _answer, looking up whatever
    phrase just succeeded against HA), where forcing a fresh HA /api/template round trip
    (possible in resolve() itself once REGISTRY_TTL has expired) would add a real, avoidable
    latency spike in front of this turn's actual LLM call for what is otherwise a background
    bookkeeping step — if the cache happens to be cold/stale, this simply skips the lookup
    (method="none") rather than paying to warm it; the synonym just doesn't get recorded this
    one time, which is a fine tradeoff for a nice-to-have background write-back that gets
    another chance on this phrase's next occurrence."""
    if not raw:
        return ResolveResult(value=raw, target_id=None, confidence=0.0, method="none")
    normalized = _normalize(raw)
    by_norm = _registry_cache["area_by_norm"] if kind == "area" else _registry_cache["entity_by_norm"]
    by_id = _registry_cache["area_by_id"] if kind == "area" else _registry_cache["entity_by_id"]
    hit = by_norm.get(normalized)
    if hit:
        target_id, display_name = hit
        return ResolveResult(value=display_name, target_id=target_id, confidence=1.0, method="exact")
    learned_id = hass_synonyms.lookup(kind, normalized, owner_id)
    if learned_id:
        display_name = by_id.get(learned_id, learned_id)
        return ResolveResult(value=display_name, target_id=learned_id, confidence=1.0, method="learned")
    return ResolveResult(value=raw, target_id=None, confidence=0.0, method="none")


def learn_synonym(kind: str, phrase_raw: str, target_id: str, method: str,
                   confidence: float, owner_id: str) -> None:
    """Convenience wrapper so callers don't need to know about normalization or the
    storage layer directly — just what was said, what it resolved to, and why."""
    hass_synonyms.learn(kind, phrase_raw, _normalize(phrase_raw), target_id, method,
                         confidence, owner_id)


def top_candidates(raw: str, kind: str, limit: int = 3) -> list:
    """Loose-cutoff (0.3) near-miss display names, for enriching a clarifying question only
    — never auto-selected, so a bad guess here has zero risk of silently misdirecting a
    command. Reads the in-memory cache directly (sync, no fetch) since this is called from
    the clarify-prompt path with whatever's already cached."""
    if not raw:
        return []
    normalized = _normalize(raw)
    by_norm = _registry_cache["area_by_norm"] if kind == "area" else _registry_cache["entity_by_norm"]
    hits = _fuzzy_candidates(normalized, by_norm, cutoff=0.30, limit=limit)
    return [display_name for (_target_id, display_name), _ratio in hits]
