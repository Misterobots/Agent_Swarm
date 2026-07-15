"""BMO Brain — the canonical conversational brain for both Home Assistant and the Pi
voice satellite (Tier-1 vault-grounded, Tier-2 tool-using).

Takes a transcribed question and produces the answer text, speaking as Friday (the active
persona — see persona.py; BMO/Beemo is a deferred future persona, not currently wired in).
Recalls relevant memories from the personal vault, injects them as context, and asks the
LLM to answer in character.

OpenAI-compatible and Ollama-native-compatible, so Home Assistant's "Control Home
Assistant" feature and the BMO Pi's bmo_driver.chat() both use it unchanged.

Two tool-calling modes, both via the shared `_answer()`:
  - Passthrough: caller supplies its own `tools` array (HA's "Control Home Assistant"
    feature does this) — forwarded to Ollama verbatim, any tool_calls propagated back
    UNEXECUTED. HA owns entity resolution/execution/authorization via its own opt-in
    entity-exposure list; bmo_brain never needs its own device-authorization layer here.
  - Self-executing: caller supplies no `tools` (e.g. the Pi driver) — bmo_brain offers
    its own tool set (tools.py: weather/time/news/web search/device control), executes
    any tool_calls itself, and loops until the model produces final text. Callers with
    no way to execute a tool call (like the Pi driver) never see one.
Delegating "build / research" requests to agent_runtime's swarm/coordinate pipeline is
a separate, still-unwired Tier-2 capability.

Personal values (vault URL / owner) come from env — nothing personal is baked into the
shared repo; the shim is inert for vault recall unless VAULT_URL + VAULT_OWNER are set.
"""
import asyncio
import datetime
import json
import os
import re
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

import hass_resolver
import local_pending
import claude_consult
from ha_registry import REGISTRY_TOOL_NAMES, REGISTRY_TOOL_SCHEMAS, call_registry_tool
from persona import FRIDAY_SYSTEM_PROMPT
from tools import TOOL_SCHEMAS, call_tool

VAULT_URL       = os.getenv("VAULT_URL", "").rstrip("/")
VAULT_OWNER     = os.getenv("VAULT_OWNER", "")
VAULT_LIMIT     = int(os.getenv("VAULT_LIMIT", "6"))
# 0.4 was too permissive: the shared MemPalace is dominated by dev-project (HHGTTG/UI
# design) memories that semantically mis-match Friday's home/life queries at 0.5-0.56
# (e.g. a "two-register layout" design note surfaced for "network layout"), leaking
# irrelevant trivia into spoken answers. 0.6 keeps only genuinely strong matches; her own
# home-relevant memories accrue over time via the write-back path. Tunable via env.
VAULT_MIN_SCORE = float(os.getenv("VAULT_MIN_SCORE", "0.6"))
VAULT_TIMEOUT   = float(os.getenv("VAULT_TIMEOUT", "12"))
# Pending-tier recall is a fast-text-search fallback, not the primary semantic search —
# it must not cost as much as VAULT_TIMEOUT, and is run concurrently with _vault_recall
# (see _answer()) so the two don't stack into a double-length wait when the vault is slow.
VAULT_PENDING_TIMEOUT = float(os.getenv("VAULT_PENDING_TIMEOUT", "3"))

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://192.168.2.101:11434").rstrip("/")
MODEL       = os.getenv("BMO_MODEL", "qwen3:8b")
MODEL_NAME  = os.getenv("BMO_MODEL_NAME", "bmo")
LLM_TIMEOUT = float(os.getenv("BMO_LLM_TIMEOUT", "150"))
TEMPERATURE = float(os.getenv("BMO_TEMPERATURE", "0.5"))
# Ollama's default context window (4096) is too small once a host is VRAM-constrained
# (confirmed on Turing's 8GB card) — Friday's persona + recalled memories + HA's tool
# schema list can approach that on their own. Explicit since relying on the model's/
# host's default risks silent truncation rather than an obvious failure.
NUM_CTX = int(os.getenv("BMO_NUM_CTX", "16384"))
SELF_TOOL_MAX_ROUNDS = int(os.getenv("BMO_SELF_TOOL_MAX_ROUNDS", "6"))
BMO_SOURCE_DEVICE = os.getenv("BMO_SOURCE_DEVICE", "lovelace")
# HA's own tool-calling loop (passthrough mode) has no round cap of its own — bmo_brain
# used to just keep guessing new tool-call variations every round, which could loop for
# 30+ seconds with nothing ever reaching the user if every guess kept failing the same
# way. Past this many consecutive failed attempts in one exchange, stop guessing and ask
# a clarifying question instead. Tunable — 2 is a starting point, not a fixed constant.
HASS_CLARIFY_THRESHOLD = int(os.getenv("HASS_CLARIFY_THRESHOLD", "2"))

# Registry-edit tools (move/assign/rename/create area — see ha_registry.py) are distinct from
# HA's on/off intents and WebSocket-executed by bmo_brain itself. Offering them on EVERY voice
# turn risks a small model mis-firing them on ordinary commands, so they're gated behind this
# intent regex on the user's text and only offered/executed when the request actually looks
# like a registry edit — ordinary on/off turns keep the exact single-call passthrough behavior
# they had before, untouched. BMO_REGISTRY_MAX_ROUNDS caps the internal execute-then-reprompt loop.
REGISTRY_MAX_ROUNDS = int(os.getenv("BMO_REGISTRY_MAX_ROUNDS", "4"))
# Bias toward catching registry intents: a false negative silently breaks the feature. A false
# positive is low-cost but NOT free — it exposes the registry WRITE tools to the model on a
# non-registry turn, so the model could in principle misfire one. That residual risk is bounded
# by ha_registry.py's strict resolution cutoff (a misfire must still resolve a real device+area
# at high confidence) and by every registry edit being reversible and visible in the HA UI.
# Key the move/assign case off the connector (to/in/into) rather than the literal word
# "area"/"room", since the destination is usually a named room ("to the office"). "put ... on"
# (an on/off phrasing) has no to/in/into connector, so it correctly does NOT match.
_REGISTRY_INTENT_RE = re.compile(
    r"\b(move|relocate|reassign|put|assign)\b.{0,50}\b(to|in|into)\b"
    r"|\brename\b|\bchange the name\b"
    r"|\b(create|make|add)\b.{0,30}\b(area|room|zone)\b",
    re.IGNORECASE,
)

# Full override still available for testing/experimentation via BMO_PERSONA.
PERSONA = os.getenv("BMO_PERSONA", FRIDAY_SYSTEM_PROMPT)

# --- Consult Claude: ask-first offload when the local model dead-ends (claude_consult.py) ---
# The OFFER is appended by code ONLY on the two genuine dead-end paths (loop exhaustion), never by
# the model — the persona deliberately says nothing about consulting Claude, so qwen3:8b is not
# trained to produce this sentinel. CONSENT requires all of: (a) consult_available() (fail-closed
# on key/budget), (b) the immediately-preceding assistant turn ended with _CONSULT_OFFER, and
# (c) the user affirming THIS turn — a real human yes the model cannot fabricate. There is NO
# consult tool in TOOL_SCHEMAS/_DISPATCH, so the model has no way to reach Claude on its own.
_CONSULT_OFFER = "Would you like me to consult Claude about this?"
_CONSULT_AFFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|sure|okay|ok|please|go ahead|do it|consult\s+claude|ask\s+claude)\b", re.I)
_CONSULT_DECLINE_RE = re.compile(
    r"\b(no|nope|never\s*mind|leave it|forget it|don'?t)\b", re.I)


def _maybe_offer_consult(fallback_text: str) -> str:
    """On a genuine dead-end, offer a Claude consult instead of the plain 'couldn't finish' reply —
    but only when consult is actually armed, so Friday never offers something she can't deliver."""
    if claude_consult.consult_available():
        return "I couldn't work that one out on my own. " + _CONSULT_OFFER
    return fallback_text


def _pending_consult_question(convo: list) -> str:
    """The user turn immediately before the offer assistant turn — the question to hand Claude."""
    seen_offer = False
    for m in reversed(convo):
        if not seen_offer:
            if m.get("role") == "assistant" and (m.get("content") or "").rstrip().endswith(_CONSULT_OFFER):
                seen_offer = True
            continue
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""

app = FastAPI(title="Friday Brain (vault-RAG assistant)")


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL, "vault": bool(VAULT_URL and VAULT_OWNER), "ollama": OLLAMA_URL}


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "bmo"}]}


async def _vault_recall(query: str):
    """Return a list of recalled memory strings for the query (empty on any failure)."""
    if not (VAULT_URL and VAULT_OWNER and query):
        return []
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            r = await c.post(f"{VAULT_URL}/v1/memories/search",
                             json={"query": query, "owner_id": VAULT_OWNER, "limit": VAULT_LIMIT})
        if r.status_code == 200:
            return [m["content"] for m in r.json() if float(m.get("score") or 0) >= VAULT_MIN_SCORE]
        print(f"[bmo-brain] vault search HTTP {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] vault recall failed: {e}", flush=True)
    return []


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Markdown/symbol stripping for spoken output. The persona asks the model for plain spoken text,
# but a small model (qwen3:8b) reliably emits markdown for structured answers — a device-status
# reply comes back as a **bold** bulleted list with °F / % symbols — and the TTS engine then
# pronounces the literal symbols as gibberish ("asterisk asterisk", "dash"). This flattens it
# deterministically so it doesn't depend on the model obeying the prompt: emphasis/links reduce
# to their text, bullets/headers/code are removed, unit symbols become spoken words, and list
# lines are joined into prose. Applied to every text response in _answer.
_SPEECH_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")   # [label](url) -> label
_SPEECH_STAR_RE = re.compile(r"\*{1,3}([^*]+?)\*{1,3}")  # *x* / **x** / ***x*** -> x
_SPEECH_USCORE_RE = re.compile(r"__([^_]+?)__")          # __x__ -> x (leave single _ for snake_case)
_SPEECH_BULLET_RE = re.compile(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+")  # -, *, 1. list markers
_SPEECH_HEADER_RE = re.compile(r"(?m)^\s*#{1,6}\s*")     # # headers


def _speechify(text: str) -> str:
    if not text or not text.strip():
        return text
    t = _SPEECH_LINK_RE.sub(r"\1", text)
    t = _SPEECH_STAR_RE.sub(r"\1", t)
    t = _SPEECH_USCORE_RE.sub(r"\1", t)
    t = t.replace("`", "")
    t = _SPEECH_HEADER_RE.sub("", t)
    t = _SPEECH_BULLET_RE.sub("", t)
    t = re.sub(r"°\s*[FfCc]\b", " degrees", t)   # 73°F -> 73 degrees
    t = t.replace("°", " degrees").replace("%", " percent").replace("&", " and ")
    # Flatten remaining lines (e.g. a bulleted list) into prose sentences so TTS reads it smoothly.
    out = []
    for ln in t.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.endswith(":"):
            ln = ln[:-1] + "."
        elif ln[-1] not in ".!?,;":
            ln = ln + "."
        out.append(ln)
    t = " ".join(out)
    t = t.replace("*", "").replace("#", "")      # any stragglers (unbalanced markers)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


_STATUS_RE = re.compile(
    r"\b(status|health|healthy|degraded|online|offline|operational|reachable|uptime)\b"
    r"|is (it|the [\w .'-]+?) (up|running|online|down|working)"
    r"|are (they|the [\w .'-]+?) (up|running|online)",
    re.IGNORECASE,
)


def _is_status_question(text: str) -> bool:
    return bool(_STATUS_RE.search(text or ""))


_COUNT_RE = re.compile(
    r"how many (memories|facts|things (do|did) you (know|remember|learn))"
    r"|memory count"
    r"|how much (do you (know|remember)|memory)"
    r"|(size|count) of (the |your )?(vault|memories)",
    re.IGNORECASE,
)


def _is_count_question(text: str) -> bool:
    return bool(_COUNT_RE.search(text or ""))


async def _vault_stats() -> str:
    """Query the vault's real aggregate memory count.

    _vault_recall is semantic search over content, not an aggregate — it cannot answer
    "how many memories are there" (that produced a fabricated number, since the LLM had
    no real total and just guessed). This hits /v1/memories/stats directly for the
    actual count, same ground-truth-injection pattern as _live_status.
    """
    if not VAULT_URL:
        return "(vault not configured)"
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{VAULT_URL}/v1/memories/stats")
        if r.status_code != 200:
            return f"(vault stats HTTP {r.status_code})"
        data = r.json()
        top = sorted(data.get("breakdown", []), key=lambda b: -b["count"])[:5]
        top_str = ", ".join(f"{b['type']}/{b['domain']}: {b['count']}" for b in top)
        return f"Total memories: {data.get('total', 'unknown')}. Largest categories: {top_str}."
    except Exception as e:  # noqa: BLE001
        return f"(vault stats unreachable: {type(e).__name__})"


async def _live_status() -> str:
    """Probe live health of the vault stack + Ollama; return a short status block.

    BMO otherwise answers status questions from (historical) memories. This gives it
    CURRENT ground truth for "is X up / what's the status" questions.
    """
    checks = []
    async with httpx.AsyncClient(timeout=8.0) as c:
        if VAULT_URL:
            try:
                r = await c.get(f"{VAULT_URL}/health")
                ok = r.status_code == 200 and "ok" in r.text.lower()
                checks.append(f"- Vault API: {'healthy' if ok else f'PROBLEM (HTTP {r.status_code})'}")
            except Exception as e:  # noqa: BLE001
                checks.append(f"- Vault API: UNREACHABLE ({type(e).__name__})")
            try:
                r = await c.post(f"{VAULT_URL}/v1/memories/search",
                                 json={"query": "status", "owner_id": VAULT_OWNER, "limit": 1})
                checks.append(f"- Vault search (Postgres + embeddings): {'working' if r.status_code == 200 else f'FAILING (HTTP {r.status_code})'}")
            except Exception as e:  # noqa: BLE001
                checks.append(f"- Vault search (Postgres + embeddings): FAILING ({type(e).__name__})")
        try:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            checks.append(f"- Ollama (embeddings + BMO model): {'up' if r.status_code == 200 else f'PROBLEM (HTTP {r.status_code})'}")
        except Exception as e:  # noqa: BLE001
            checks.append(f"- Ollama: DOWN ({type(e).__name__})")
    return "\n".join(checks) if checks else "(no live checks configured)"


async def _ollama_chat(messages: list, tools=None):
    """One raw call to Ollama's /api/chat. Returns (text, tool_calls) — tool_calls is
    Ollama's native shape (list of {"function": {"name", "arguments"}}) or None."""
    # keep_alive keeps qwen3:8b resident in VRAM between calls — this GPU is shared with
    # other consumers (embeddings, other models), so without it Ollama's default eviction
    # window lets the model fall out of VRAM between conversational turns, and the next
    # call pays a real reload cost (observed: 8-11s on an otherwise-idle model).
    payload = {"model": MODEL, "messages": messages, "stream": False, "keep_alive": "30m",
               "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX}}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as c:
        r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
        r.raise_for_status()
        message = r.json().get("message", {})
    text = _strip_think(message.get("content", "") or "")
    tool_calls = message.get("tool_calls") or None
    return text, tool_calls


async def _self_execute_tools(messages: list, tools: list):
    """Offer the given `tools`, executing any tool_calls server-side and looping until the model
    produces a final text-only response. Used only when the caller supplied no `tools` of its own
    — see _answer()'s docstring. `tools` is built by the caller: the base self-exec set, plus the
    registry WRITE tools ONLY when the turn looks like a registry edit (the same gating the
    passthrough path uses), so the Pi path can't misfire a registry write on an ordinary command.
    Always returns tool_calls=None: a caller with no `tools` array has no way to execute one itself.
    """
    convo = list(messages)
    for _round in range(SELF_TOOL_MAX_ROUNDS):
        text, tool_calls = await _ollama_chat(convo, tools)
        if not tool_calls:
            return text, None
        convo.append({"role": "assistant", "content": text, "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            result = await call_tool(name, args)
            print(f"[bmo-brain] self-executed tool={name} args={args} -> {result[:120]!r}", flush=True)
            convo.append({"role": "tool", "content": result})
    print(f"[bmo-brain] self-executing tool loop exhausted {SELF_TOOL_MAX_ROUNDS} rounds "
          f"without a final answer", flush=True)
    return _maybe_offer_consult(
        "I tried a few things there but couldn't finish that one. Want to try asking again?"), None


def _split_registry_calls(tool_calls):
    """Partition tool_calls into (registry-owned, HA-owned). Registry-owned are bmo_brain's own
    ha_registry tools it must execute itself; HA-owned (HassTurnOn, etc.) are handed back to HA
    unexecuted, exactly as normal passthrough does."""
    reg, other = [], []
    for tc in (tool_calls or []):
        name = (tc.get("function") or {}).get("name", "")
        (reg if name in REGISTRY_TOOL_NAMES else other).append(tc)
    return reg, other


async def _passthrough_with_registry(messages, tools):
    """Passthrough tool-calling with one twist: bmo_brain EXECUTES its own HA registry tools
    itself (HA has no Assist intent for registry edits), looping until the model produces final
    text or an HA-owned tool_call — the latter returned UNEXECUTED for HA to run, exactly as
    normal passthrough does. Only reached when the user's text looked like a registry edit (see
    _REGISTRY_INTENT_RE), so the registry tool schemas are offered ONLY here — never on ordinary
    on/off turns. Returns (text, tool_calls) matching _answer's contract."""
    all_tools = list(tools) + REGISTRY_TOOL_SCHEMAS
    convo = list(messages)
    text, tool_calls = "", None
    for _round in range(REGISTRY_MAX_ROUNDS):
        text, tool_calls = await _ollama_chat(convo, all_tools)
        reg_calls, ha_calls = _split_registry_calls(tool_calls)
        if reg_calls:
            # Execute our OWN registry tools first (HA can't run them). Doing this before the
            # ha_calls return is deliberate: if the model batched a registry call and an HA
            # on/off call into the same round, the registry edit would otherwise be silently
            # dropped. Registry ops are self-contained and each returns a spoken-style string.
            convo = convo + [{"role": "assistant", "content": text, "tool_calls": reg_calls}]
            for tc in reg_calls:
                fn = tc.get("function") or {}
                result = await call_registry_tool(fn.get("name", ""), fn.get("arguments") or {})
                print(f"[bmo-brain] registry tool={fn.get('name')} args={fn.get('arguments')} "
                      f"-> {result[:160]!r}", flush=True)
                convo.append({"role": "tool", "content": result})
            if ha_calls:
                # Same round also carried HA-owned calls — hand them back now (the registry
                # edits above already applied), matching normal passthrough for the on/off part.
                return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
            continue  # only registry calls -> reprompt for a spoken confirmation
        if ha_calls:
            return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
        return text, None  # no tool_calls -> final text answer
    print(f"[bmo-brain] registry passthrough loop exhausted {REGISTRY_MAX_ROUNDS} rounds", flush=True)
    return _maybe_offer_consult(
        text or "I got partway through that change but couldn't finish it."), None


async def _pending_recall(query: str, owner_id: str):
    """Query the vault's pending (not-yet-processed) queue for same-day recall.

    Fast text search over conversations queued but not yet promoted to the curated
    memory store. Never raises and keeps a short timeout — this must not block the
    response for long if the vault is slow or unreachable."""
    if not (VAULT_URL and owner_id and query):
        return []
    try:
        async with httpx.AsyncClient(timeout=VAULT_PENDING_TIMEOUT) as c:
            r = await c.get(f"{VAULT_URL}/v1/extract/pending/search",
                             params={"owner_id": owner_id, "query": query})
        if r.status_code == 200:
            return [item["content"] for item in r.json()]
        print(f"[bmo-brain] pending recall HTTP {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] pending recall failed: {e}", flush=True)
    return []


async def _store_memory(user_text: str, response_text: str, tool_trace: str = ""):
    """Store the exchange for later recall. Non-fatal on any failure — inert (like
    _vault_recall) unless VAULT_URL + VAULT_OWNER are set.

    Queues locally (fast, synchronous, network-independent) first, then fires the
    background POST to the vault's lightweight queue endpoint — which just queues the
    text instantly with no LLM call, replacing the old heavy synchronous /v1/extract
    call that caused GPU contention with bmo_brain's own chat model.

    tool_trace, when this exchange involved any tool calls, is appended so the nightly
    extraction pass has the technical detail (what was tried, what failed, what worked)
    to learn from — not just the user-visible Q&A. Without this, a device-control
    quirk (e.g. a specific slot combination HA rejects) never becomes a memory even
    though the exchange that discovered it is stored, because the stored text alone
    gives no sign anything went wrong underneath a clean-looking final answer."""
    if not (VAULT_URL and VAULT_OWNER and user_text and response_text):
        return
    conversation = f"User: {user_text}\nBMO: {response_text}"
    if tool_trace:
        conversation += f"\n[Tool activity this exchange:\n{tool_trace}\n]"
    local_pending.queue_local(conversation, VAULT_OWNER)
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            await c.post(f"{VAULT_URL}/v1/extract/queue",
                         json={"conversation": conversation,
                               "owner_id": VAULT_OWNER,
                               "source_device": BMO_SOURCE_DEVICE})
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] memory store failed (non-fatal): {e}", flush=True)


_HASS_AREA_INTENTS = {"HassTurnOn", "HassTurnOff", "HassLightSet", "HassToggle"}
_HASS_LIST_TO_STR_KEYS = ("device_class", "domain")
# device_class normally filters WITHIN a domain (e.g. binary_sensor + motion/door/window),
# but models sometimes use it as if it were the domain selector itself for simple
# directly-controllable categories. Confirmed live against real HA: {area,
# device_class: "light"} alone is rejected (InvalidSlotInfo) — HA needs `domain` for
# whole-category area targeting, not `device_class`. Only promote device_class to domain
# for values that are ALSO real domain names for directly-controllable entities; leave
# genuine device_class filters (motion, door, window, etc.) alone since those have no
# domain equivalent and promoting them would be wrong.
_DEVICE_CLASS_IS_ALSO_A_DOMAIN = {
    "light", "switch", "fan", "cover", "lock", "climate", "media_player", "vacuum",
}


async def _sanitize_hass_tool_calls(tool_calls, owner_id: str = ""):
    """Normalize HA intent tool-call arguments to avoid guaranteed-invalid combinations.

    Failure patterns observed live against real HA: (1) device_class/domain sent as a
    list instead of a plain string, which HA's intent slot schema rejects outright
    (InvalidSlotInfo); (2) area targeting combined with a specific `name` that does not
    correspond to a real entity — the model tends to echo the area/domain back as a
    fabricated name (e.g. "living room light" for an area-wide "turn off the living
    room lights" request), and HA rejects mixing area-wide and name-specific targeting
    in one call; (3) `domain` and `device_class` supplied together — confirmed live that
    {area, domain: "light", device_class: "light"} is rejected every time, while the
    identical call with device_class dropped ({area, domain: "light"}) succeeds
    immediately; (4) `device_class` used ALONE as if it selected the domain (e.g. {area,
    device_class: "light"}, no domain at all) — also rejected; promoted to `domain`
    instead when the value is a real domain name for a directly-controllable category.
    A prompt instruction telling the model to avoid these was not reliably followed
    (observed a stuck loop spanning 37+ seconds and many rounds before HA happened to
    try a clean combination) — this normalizes deterministically instead of relying on
    the model to self-correct.

    Also resolves `area`/`name` through hass_resolver.resolve() BEFORE any of the above —
    HA's own area/entity matching is confirmed literal (exact string only, no fuzzy/alias
    fallback for this LLM-tool-calling path), so a phrase like "second floor hall" never
    matches a real area actually named "Upstairs" without this. A confident-but-non-exact
    resolution is proactively learned as a synonym so the same phrasing resolves for free
    (no fuzzy/embedding work) next time.

    `name` is deliberately resolved (and never learned) ONLY when `area` is absent from this
    same call — matching the "drop name when area is present" rule a few lines below, but
    applied a step earlier. This isn't just a redundant no-op: a room-wide request ("turn off
    the living room lights") combined with a model that fabricates a specific `name` for it is
    a real, previously-documented incident (docs/relay_roadmap.md, "Room-wide device targeting
    picks one remembered entity instead of the whole area") — running the fuzzy/embedding
    resolver on that fabricated name BEFORE the drop check would risk rewriting it to a real
    but WRONG entity (e.g. "living room light" fuzzy-matching an actual "Living Room Lamp"
    entity) and, past LEARN_THRESHOLD, permanently memorizing that wrong phrase->entity
    mapping — turning a case the drop-name rule already handles safely into a silently wrong,
    self-reinforcing one.
    """
    if not tool_calls:
        return tool_calls
    for tc in tool_calls:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if fn.get("name") not in _HASS_AREA_INTENTS or not isinstance(args, dict):
            continue
        raw_area = args.get("area")
        if raw_area and isinstance(raw_area, str):
            result = await hass_resolver.resolve(raw_area, "area", owner_id)
            if result.method != "none":
                args["area"] = result.value
                if result.method in ("fuzzy", "embedding") and result.confidence >= hass_resolver.LEARN_THRESHOLD:
                    hass_resolver.learn_synonym("area", raw_area, result.target_id, result.method,
                                                 result.confidence, owner_id)
        raw_name = args.get("name")
        if not args.get("area") and raw_name and isinstance(raw_name, str):
            result = await hass_resolver.resolve(raw_name, "entity", owner_id)
            if result.method != "none":
                args["name"] = result.value
                if result.method in ("fuzzy", "embedding") and result.confidence >= hass_resolver.LEARN_THRESHOLD:
                    hass_resolver.learn_synonym("entity", raw_name, result.target_id, result.method,
                                                 result.confidence, owner_id)
        for key in _HASS_LIST_TO_STR_KEYS:
            val = args.get(key)
            if isinstance(val, list):
                if val:
                    args[key] = val[0]
                else:
                    args.pop(key, None)
        if args.get("area") and args.get("name"):
            args.pop("name", None)
        if args.get("domain") and args.get("device_class"):
            args.pop("device_class", None)
        if (
            not args.get("domain")
            and args.get("device_class") in _DEVICE_CLASS_IS_ALSO_A_DOMAIN
        ):
            args["domain"] = args.pop("device_class")
    return tool_calls


def _tool_result_is_error(content) -> bool:
    """Whether a tool-result message's content signals failure.

    HA's Ollama integration json.dumps()es tool results, so a failed intent surfaces as
    {"error": ...}. Check that structurally rather than substring-matching the literal
    '"error"' token: a client that hands back a dict (or serializes with single quotes)
    would never match the quoted-token form, so every failure would read as a success —
    silently breaking the clarify-loop breaker AND letting a failed attempt be mislearned
    as a synonym. The JSON-dict path is precise; the trailing check preserves the original
    quoted-substring behavior for any non-JSON string content (never loosened)."""
    if content is None:
        return False
    if isinstance(content, dict):
        return "error" in content
    text = str(content)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        return "error" in parsed
    return '"error"' in text


def _count_trailing_tool_failures(convo) -> int:
    """Count consecutive failed tool-result turns at the end of this exchange.

    Scans backward from the most recent turn and stops at the first success or exchange
    boundary — so an old, unrelated failure earlier in a long conversation doesn't
    wrongly trigger the clarify-instead-of-guess path below. Each round-trip is a "tool"
    result turn PRECEDED by an "assistant" turn carrying the tool_calls that produced it
    (that's the call side, not a result) — skip over those rather than stopping at them,
    or every failure past the first would be missed."""
    count = 0
    for m in reversed(convo):
        role = m.get("role")
        if role == "tool":
            if _tool_result_is_error(m.get("content")):
                count += 1
            else:
                break
        elif role == "assistant" and m.get("tool_calls"):
            continue
        else:
            break  # a user turn, or a final assistant text answer — exchange boundary
    return count


def _build_tool_trace(convo) -> str:
    """Compact summary of this exchange's tool calls and results, for memory-write
    purposes only — the model itself already sees the full convo natively as context,
    this is so a nightly memory-extraction pass (which only sees the stored text, not
    the live conversation) has the technical detail to learn from too. Empty string if
    no tool activity occurred this exchange."""
    lines = []
    for m in convo:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                lines.append(f"tried {fn.get('name')}({fn.get('arguments')})")
        elif m.get("role") == "tool":
            lines.append(f"-> {str(m.get('content') or '')[:200]}")
    return "\n".join(lines)


def _extract_tool_attempts(convo) -> list:
    """Reconstruct (round, kind, raw_phrase, success) for every HassTurnOn/Off/etc
    tool_call in this exchange's convo, in call order. `round` is a 0-based index that
    increments once per assistant tool_calls turn — i.e. every tool_call issued in the
    SAME model turn shares the same round number, distinguishing "one batch of several
    independent targets" (e.g. "turn off the living room, deck, and upstairs lights" — one
    round, three unrelated area targets) from "a genuine retry of the same request in a
    later round" (round N fails, round N+1 tries a different phrasing for what's plausibly
    the same target). This distinction matters: a failure and a success sitting in the SAME
    round have no correction relationship at all, they're just two of several unrelated
    things the model was asked to do at once — treating them as a retry-correction pair
    would (and, before this fix, did — confirmed live: a batched "Living Room" + "deck" +
    "Upstairs" turn-off wrongly taught "deck" as a synonym for Living Room, since Living
    Room's unrelated success was mistaken for a correction of deck's unrelated failure)
    silently memorize a wrong phrase->target mapping. See _answer's reactive-learning block
    for how `round` is used to guard against exactly this.

    `raw_phrase` is whatever area/name value was actually sent to HA (already
    hass_resolver-corrected, since convo carries forward what was sent, not the model's
    pre-resolution guess) and `success` is False if the paired tool result's content
    contains an error. Used only for reactive synonym learning and clarify-prompt enrichment
    (see _answer) — never on a path that can raise, since a malformed convo shape here must
    not break the exchange.

    tool_calls arguments can arrive either as native dicts (Ollama's own shape, used by
    the /api/chat surface) or as JSON strings (the OpenAI-compatible surface's shape,
    echoed back verbatim by an OpenAI-style client on later turns) — both are handled.

    Pairing prefers the tool result's `tool_call_id` against each pending tool_call's own
    `id` when both are present (the OpenAI-compatible surface's convention, since
    chat_completions() stamps every emitted tool_call with a unique "call_..." id) and only
    falls back to plain FIFO order when no id is available (Ollama's native shape carries no
    id at all) — a single assistant turn emitting more than one tool_call is plausible during
    the multi-round retry behavior this whole module exists to shortcut, and pairing purely
    by position would silently mis-attribute success/failure to the wrong call if results
    ever arrive in a different order than issued."""
    attempts = []
    pending_tool_calls = []
    round_index = -1
    for m in convo:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            round_index += 1
            pending_tool_calls = list(m["tool_calls"])
        elif role == "tool" and pending_tool_calls:
            result_id = m.get("tool_call_id")
            match_idx = None
            if result_id:
                match_idx = next(
                    (i for i, cand in enumerate(pending_tool_calls) if cand.get("id") == result_id),
                    None,
                )
            tc = pending_tool_calls.pop(match_idx if match_idx is not None else 0)
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (TypeError, ValueError):
                    args = None
            if fn.get("name") in _HASS_AREA_INTENTS and isinstance(args, dict):
                success = not _tool_result_is_error(m.get("content"))
                for key, kind in (("area", "area"), ("name", "entity")):
                    raw = args.get(key)
                    if raw and isinstance(raw, str):
                        attempts.append((round_index, kind, raw, success))
    return attempts


# Curated exact-match phrase list, converged independently on nearly the same set as
# published Whisper-hallucination research (arXiv:2501.11378 finds "thank you" alone
# accounts for ~25% of all hallucinations on non-speech audio) and as this project's own
# Pi-side filter (clean_stt_text() in agents/bmo_voice/bmo_driver.py, which this list is
# kept in sync with — that filter still runs first on the Pi path and is unaffected by
# this one). Deliberately NO length-based cutoff (see _answer()'s docstring note above) —
# match on exact normalized text only, never on "text is short."
_STT_HALLUCINATION_PHRASES = {
    "thank you.", "thanks for watching.", "amara.org", "bye.", "you.", ".",
    "thanks for watching!", "subscribe", "thank you", "thanks", "thanks for watching",
    "hello?", "hello.", "hello", "hi.", "hi", "testing.", "test.", "test", "...",
    ",,,", "www", "okay.", "okay",
}
_STT_MODEL_TAG_RE = re.compile(r"<\|.*?\|>")
_STT_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]+")


def _is_likely_stt_hallucination(text: str) -> bool:
    """Mirrors bmo_driver.py's clean_stt_text() cleaning/matching logic (model tags,
    non-ASCII stripping — Whisper hallucinates Korean/Chinese/Russian text on silence too —
    then exact match against the curated list) without its length-based cutoff, which
    would be wrong here (see _answer())."""
    if not text:
        return False
    cleaned = _STT_MODEL_TAG_RE.sub("", text).strip()
    cleaned = _STT_NON_ASCII_RE.sub("", cleaned).strip()
    return cleaned.lower() in _STT_HALLUCINATION_PHRASES


def _coerce_tool_call_args(tool_calls):
    """Return tool_calls with each function.arguments coerced to a dict.

    The OpenAI-compatible surface (/v1/chat/completions) echoes prior-turn tool_calls
    back with `arguments` as a JSON *string* (see _extract_tool_attempts's note). Ollama's
    /api/chat expects an object there and rejects a string outright, so forwarding an
    OpenAI-shaped assistant turn verbatim would 500 the whole exchange on round 2+ of a
    multi-round tool loop. Parse it back to a dict before the call. Ollama's own native
    shape already carries a dict, so this is a no-op on the /api/chat path — and a shallow
    copy is made only for turns that actually need it, so caller messages aren't mutated."""
    if not tool_calls:
        return tool_calls
    out = []
    for tc in tool_calls:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (TypeError, ValueError):
                args = {}
            tc = {**tc, "function": {**fn, "arguments": args}}
        out.append(tc)
    return out


async def _answer(client_messages, tools=None):
    """Recall vault context, build the BMO prompt, call the LLM, return (text, tool_calls).

    `tools`, when supplied by the caller, is forwarded to Ollama verbatim (OpenAI-style
    function-calling schema) and any tool_calls are propagated back UNEXECUTED —
    passthrough mode, e.g. HA's "Control Home Assistant" feature, which owns entity
    resolution/execution/authorization itself. When the caller supplies no `tools`,
    bmo_brain offers its own tool set (tools.py) and executes any tool_calls itself,
    looping until the model produces a final text-only response — self-executing mode,
    e.g. the Pi driver, which has no way to execute a tool call itself. tool_calls in the
    return value is always None in self-executing mode.
    """
    # Keep tool-result turns (role "tool") and the assistant's own prior tool_calls turn
    # (content is empty when it emits tool_calls) so multi-round tool-calling loops — e.g.
    # HA retrying entity resolution after a failed target — carry forward instead of
    # silently resetting to the original prompt on every round.
    convo = []
    for m in client_messages:
        if m.get("role") not in ("user", "assistant", "tool"):
            continue
        if not (m.get("content") or m.get("tool_calls")):
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            # Normalize any OpenAI-shaped (JSON-string) arguments to dicts so the turn is
            # safe to forward to Ollama's /api/chat (see _coerce_tool_call_args).
            m = {**m, "tool_calls": _coerce_tool_call_args(m["tool_calls"])}
        convo.append(m)
    last_user = next((m["content"] for m in reversed(convo) if m.get("role") == "user"), "")

    # Confirmed live: an STT engine transcribed near-silent audio (a muted mic, and
    # separately a synthesized test tone) as "Thank you." — Whisper's single most common
    # hallucination on non-speech audio — and it reached here as if it were a real
    # utterance. This is the ONE chokepoint all three calling surfaces (HA's Ollama-native
    # /api/chat, HA's OpenAI-compatible /v1/chat/completions, and the Pi driver) funnel
    # through, so this is where every one of them gets covered — the Pi driver already had
    # its own copy of this same filter (clean_stt_text() in bmo_voice/bmo_driver.py) but
    # applied it BEFORE ever calling bmo_brain, so the HA-Assist/phone-app path (which is
    # what actually hit this) had zero protection until now. Deliberately no length-based
    # cutoff here (unlike bmo_driver.py's `len(text) <= 2`) — this project's FOLLOWUP_WINDOW
    # pattern means Friday routinely expects a bare one-word reply like "no" or "ok", and a
    # blanket short-text cutoff would silently eat those. Exact-match against a curated
    # phrase list only. On a match: skip vault recall, the LLM call, and memory storage
    # entirely and return silently — no tool_call can ever be generated for a phrase that
    # never reaches the model, so this single early return covers both the "wasted chatty
    # reply" case and the "phantom command" case in one place, not two separate checks.
    if _is_likely_stt_hallucination(last_user):
        print(f"[bmo-brain] dropped likely STT hallucination: {last_user!r}", flush=True)
        return "", None

    # Consult-Claude consent gate (see _CONSULT_OFFER). If the previous assistant turn offered a
    # consult and the user affirms THIS turn, call Claude — the single call site — and short-circuit
    # recall / the LLM / all tools for this turn. Gated on consult_available() (fail-closed on
    # key + monthly budget), so it is a hard no-op until the feature is armed.
    if claude_consult.consult_available():
        prev_assistant = next(
            (m.get("content") or "" for m in reversed(convo) if m.get("role") == "assistant"), "")
        if prev_assistant.rstrip().endswith(_CONSULT_OFFER):
            if _CONSULT_AFFIRM_RE.search(last_user or ""):
                question = _pending_consult_question(convo)
                if not question:
                    return "Remind me what you wanted me to ask Claude?", None
                print(f"[bmo-brain] consulting Claude on: {question[:120]!r}", flush=True)
                answer = await claude_consult.consult_claude(question)
                return _speechify(answer), None
            if _CONSULT_DECLINE_RE.search(last_user or ""):
                return "Okay, I'll leave it.", None

    for m in convo:
        if m.get("role") == "tool":
            print(f"[bmo-brain] incoming tool result: {str(m.get('content'))[:300]!r}", flush=True)
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            print(f"[bmo-brain] incoming prior tool_calls: {m['tool_calls']}", flush=True)
    local_mems = local_pending.search_local(last_user, VAULT_OWNER)
    # Run concurrently, not sequentially — otherwise a slow/unreachable vault costs
    # VAULT_TIMEOUT twice (once per call) instead of once, which would double worst-case
    # latency on every single request and defeat the point of the local-resilience tier.
    mems, pending_mems = await asyncio.gather(
        _vault_recall(last_user),
        _pending_recall(last_user, VAULT_OWNER),
    )
    pending_ctx_lines = [f"- Recent (may still be processing): {c}"
                         for c in (local_mems + pending_mems)]
    curated_ctx_lines = [f"- {c}" for c in mems]
    ctx_lines = pending_ctx_lines + curated_ctx_lines
    ctx = ("\n".join(ctx_lines)
           if ctx_lines else "(no specific vault memories matched this question)")
    parts = [PERSONA]
    status_q = _is_status_question(last_user)
    if status_q:
        live = await _live_status()
        parts.append("LIVE SYSTEM STATUS — probed just now. Treat this as CURRENT ground truth "
                     "and base any status/health answer on THIS, not on recalled memories:\n" + live)
    count_q = _is_count_question(last_user)
    if count_q:
        stats = await _vault_stats()
        parts.append("VAULT MEMORY COUNT — queried just now. Treat this as the exact, authoritative "
                     "count; state it plainly if asked how many memories exist. Do not guess a "
                     "different number:\n" + stats)
    parts.append(
        "I have access to a personal memory vault (also called MemPalace) — facts about "
        "your projects and infrastructure. If asked whether I have a vault or MemPalace, "
        "the answer is yes; below is whatever I recalled for this question specifically:\n" + ctx
    )
    parts.append("/no_think")
    system = "\n\n".join(parts)
    messages = [{"role": "system", "content": system}] + convo

    tool_failures = _count_trailing_tool_failures(convo) if tools else 0
    asked_for_clarity = False

    if tools:
        # Reactive synonym learning: ONLY when the immediately preceding round contains a
        # single failed attempt and the immediately following round contains a single
        # succeeded attempt of the same kind — i.e. a genuine single-target retry-
        # correction ("second floor hall" fails, the model's very next round tries
        # "Upstairs" and succeeds), never a batch of several independent targets in one
        # round. This restriction exists because of a confirmed live failure: a single
        # model turn batching three unrelated area commands ("Living Room", "deck",
        # "Upstairs" — one round, three targets) had Living Room and Upstairs succeed while
        # "deck" failed, and the original (round-blind) version of this logic wrongly
        # treated Living Room's unrelated success as a correction for deck's unrelated
        # failure, permanently teaching "deck" as a synonym for Living Room. Requiring
        # exactly one attempt per round, in adjacent rounds, rules that out: a batch round
        # has more than one attempt and is excluded entirely, so an ambiguous multi-target
        # round teaches nothing rather than guessing wrong.
        attempts = _extract_tool_attempts(convo)
        rounds = {}
        for round_index, kind, raw_phrase, success in attempts:
            rounds.setdefault(round_index, []).append((kind, raw_phrase, success))
        if rounds:
            last_round_idx = max(rounds)
            prev_round_idx = last_round_idx - 1
            last_round = rounds.get(last_round_idx, [])
            prev_round = rounds.get(prev_round_idx, [])
            if len(last_round) == 1 and len(prev_round) == 1:
                succeeded_kind, succeeded_phrase, succeeded_ok = last_round[0]
                failed_kind, failed_phrase, failed_ok = prev_round[0]
                if (succeeded_ok and not failed_ok
                        and succeeded_kind == failed_kind
                        and succeeded_phrase != failed_phrase):
                    # Cache-only lookup, not resolve() — this must never force a fresh HA
                    # registry fetch (up to REGISTRY_TTL's staleness window) in front of
                    # this turn's actual LLM call just to record a background synonym; a
                    # cold cache just means this correction isn't recorded this one time.
                    succeeded_result = hass_resolver.resolve_cached(succeeded_phrase, succeeded_kind, VAULT_OWNER)
                    if succeeded_result.target_id:
                        hass_resolver.learn_synonym(failed_kind, failed_phrase, succeeded_result.target_id,
                                                     "corrected", 1.0, VAULT_OWNER)
    else:
        attempts = []

    if tools and tool_failures >= HASS_CLARIFY_THRESHOLD:
        # HA drives this retry loop, not bmo_brain — there is no round cap of our own
        # unless we impose one. Past the threshold, stop guessing new tool-call variations
        # and force a text-only answer (tools withheld, so another guess is structurally
        # impossible) that asks a specific clarifying question using whatever context is
        # already in the conversation, rather than hoping the model decides to stop on its
        # own — a soft prompt instruction alone did not reliably work (observed a 37+
        # second, many-round stuck loop earlier tonight).
        last_failed = next((a for a in reversed(attempts) if not a[3]), None)
        near_miss = hass_resolver.top_candidates(last_failed[2], last_failed[1]) if last_failed else []
        clarify_hint = (
            "\n\nThe closest real area/device names in this home are: " + ", ".join(near_miss)
            + ". If one of these is what I meant, say its name plainly; otherwise tell me "
            "the right one."
        ) if near_miss else ""
        clarify_system = system + "\n\n" + (
            f"You have attempted this device command {tool_failures} times this exchange "
            "and it failed the same way every time. Do not try again blindly. Look at what "
            "you were attempting above and ask ME a short, specific clarifying question "
            "about it right now — which device or area I meant, or whether it might be "
            "listed under a different name. One short spoken sentence. You have no tools "
            "available for this response, so just answer in words."
        ) + clarify_hint
        clarify_messages = [{"role": "system", "content": clarify_system}] + convo
        text, tool_calls = await _ollama_chat(clarify_messages, tools=None)
        tool_calls = None  # belt-and-suspenders: this path must never emit a tool call
        asked_for_clarity = True
    elif tools and _REGISTRY_INTENT_RE.search(last_user or ""):
        # Registry-edit intent: offer bmo_brain's own registry tools and execute them here,
        # since HA can't. Ordinary on/off turns skip this entirely (regex miss) and stay on the
        # untouched single-call path below.
        text, tool_calls = await _passthrough_with_registry(messages, tools)
    elif tools:
        text, tool_calls = await _ollama_chat(messages, tools)
        tool_calls = await _sanitize_hass_tool_calls(tool_calls, VAULT_OWNER)
    else:
        # Self-executing (Pi) path. Offer the base tool set, and add the registry WRITE tools
        # ONLY when the turn looks like a registry edit — the same gate the passthrough path uses,
        # so an ordinary self-executed command can't expose or misfire a destructive registry edit.
        self_tools = TOOL_SCHEMAS + (REGISTRY_TOOL_SCHEMAS
                                     if _REGISTRY_INTENT_RE.search(last_user or "") else [])
        text, tool_calls = await _self_execute_tools(messages, self_tools)

    if not text and not tool_calls:
        text = "(no response)"
    print(f"[bmo-brain] memories={len(mems)} local_pending={len(local_mems)} "
          f"vault_pending={len(pending_mems)} status_probe={status_q} count_probe={count_q} "
          f"tool_failures={tool_failures} asked_for_clarity={asked_for_clarity} "
          f"tool_calls={len(tool_calls) if tool_calls else 0} answer_chars={len(text)}", flush=True)
    # Status/count answers are point-in-time snapshots (current health, current total) —
    # storing them as vault "facts" makes them go stale immediately, and a wrong one
    # (e.g. a guessed memory count) becomes self-reinforcing: future recalls surface the
    # stale answer as ground truth and can cause it to be restated and stored again.
    if not status_q and not count_q:
        tool_trace = _build_tool_trace(convo) if (tool_failures or asked_for_clarity) else ""
        asyncio.create_task(_store_memory(last_user, text, tool_trace))
    # Strip markdown/symbols from the spoken text so TTS doesn't read them aloud as gibberish.
    # Done here (not before _store_memory) so memory keeps the original; only the reply is cleaned.
    return _speechify(text), tool_calls


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    client_messages = body.get("messages", [])
    stream = bool(body.get("stream", False))
    model = body.get("model") or MODEL_NAME
    tools = body.get("tools")
    cid = "chatcmpl-bmo-" + uuid.uuid4().hex[:12]
    created = int(time.time())

    tool_calls = None
    try:
        text, tool_calls = await _answer(client_messages, tools=tools)
    except Exception as e:  # noqa: BLE001
        text = f"(BMO brain error: {e})"
        print(f"[bmo-brain] ERROR: {type(e).__name__}: {e}", flush=True)

    # Ollama's tool_calls.function.arguments is a parsed object; OpenAI's is a JSON string.
    openai_tool_calls = None
    if tool_calls:
        openai_tool_calls = [{
            "id": "call_" + uuid.uuid4().hex[:12],
            "type": "function",
            "function": {
                "name": tc.get("function", {}).get("name", ""),
                "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
            },
        } for tc in tool_calls]
        print(f"[bmo-brain] emitting tool_calls={[(tc['function']['name'], tc['function']['arguments']) for tc in openai_tool_calls]}", flush=True)
    finish_reason = "tool_calls" if openai_tool_calls else "stop"

    if stream:
        async def gen():
            if openai_tool_calls:
                yield ("data: " + json.dumps({
                    "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0,
                                 "delta": {"role": "assistant", "tool_calls": openai_tool_calls},
                                 "finish_reason": None}],
                }) + "\n\n")
            else:
                for delta in ({"role": "assistant"}, {"content": text}):
                    yield ("data: " + json.dumps({
                        "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                    }) + "\n\n")
            yield ("data: " + json.dumps({
                "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            }) + "\n\n")
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    message = {"role": "assistant", "content": None if openai_tool_calls else text}
    if openai_tool_calls:
        message["tool_calls"] = openai_tool_calls

    return JSONResponse({
        "id": cid, "object": "chat.completion", "created": created, "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


# ---------------------------------------------------------------------------
# Ollama-compatible surface — lets Home Assistant's native (no-HACS) Ollama
# integration use this shim as a local "model" by URL. Same vault-RAG core.
# ---------------------------------------------------------------------------
def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@app.get("/api/version")
async def ollama_version():
    return {"version": "0.5.0"}


@app.get("/api/tags")
async def ollama_tags():
    return {"models": [{
        "name": f"{MODEL_NAME}:latest", "model": f"{MODEL_NAME}:latest",
        "modified_at": _now_iso(), "size": 0, "digest": "bmo",
        "details": {"parent_model": "", "format": "gguf", "family": "bmo",
                    "families": ["bmo"], "parameter_size": "8B", "quantization_level": ""},
    }]}


@app.post("/api/show")
async def ollama_show(req: Request):
    # HA probes model capabilities here during setup; "tools" must be advertised for HA
    # to offer "Control Home Assistant" tool-calling for this model.
    return {
        "license": "", "modelfile": "", "parameters": "", "template": "{{ .Prompt }}",
        "details": {"parent_model": "", "format": "gguf", "family": "bmo",
                    "families": ["bmo"], "parameter_size": "8B", "quantization_level": ""},
        "model_info": {}, "capabilities": ["completion", "tools"],
    }


@app.post("/api/chat")
async def ollama_chat(req: Request):
    body = await req.json()
    messages = body.get("messages", [])
    stream = body.get("stream", True)
    model = body.get("model") or f"{MODEL_NAME}:latest"
    tools = body.get("tools")
    now = _now_iso()
    tool_calls = None
    try:
        text, tool_calls = await _answer(messages, tools=tools)
    except Exception as e:  # noqa: BLE001
        text = f"(BMO brain error: {e})"
        print(f"[bmo-brain] /api/chat ERROR: {type(e).__name__}: {e}", flush=True)

    if tool_calls:
        print(f"[bmo-brain] /api/chat emitting tool_calls="
              f"{[(tc.get('function', {}).get('name'), tc.get('function', {}).get('arguments')) for tc in tool_calls]}",
              flush=True)

    # Ollama's native tool_calls shape is passed through verbatim — HA's native Ollama
    # integration talks to this endpoint directly, so no translation is needed.
    message_body = {"role": "assistant", "content": text}
    if tool_calls:
        message_body["tool_calls"] = tool_calls

    if stream:
        async def gen():
            yield json.dumps({"model": model, "created_at": now,
                              "message": message_body, "done": False}) + "\n"
            yield json.dumps({"model": model, "created_at": _now_iso(),
                              "message": {"role": "assistant", "content": ""},
                              "done": True, "done_reason": "stop"}) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    return JSONResponse({"model": model, "created_at": now,
                         "message": message_body,
                         "done": True, "done_reason": "stop"})
