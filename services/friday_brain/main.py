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
import hmac
import json
import os
import random
import re
import time
import uuid

import httpx
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse, Response, StreamingResponse)

import hass_resolver
import local_pending
import claude_consult
import personas
from ha_registry import REGISTRY_TOOL_NAMES, REGISTRY_TOOL_SCHEMAS, call_registry_tool
from persona import FRIDAY_SYSTEM_PROMPT
from persona_page import PERSONA_EDITOR_HTML
# delegate_to_swarm + AGENT_RUNTIME_URL imported by NAME (not `import tools`) on purpose: _answer()
# has a parameter named `tools` (the HA tool list) that would shadow the module inside it.
from tools import (TOOL_SCHEMAS, call_tool, delegate_to_swarm, AGENT_RUNTIME_URL,
                   HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN, get_current_weather,
                   list_media_players, MEDIA_SEARCH_SENTINEL, NODE_SPEAKER_MAP,
                   set_current_node, current_node_speaker)

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
# Anti-runaway decoding. qwen3:8b will occasionally degenerate into repeating the same sentence;
# with no output cap it repeats until it fills NUM_CTX (16K) — the "she says the last thing over and
# over" symptom. REPEAT_PENALTY over the last REPEAT_LAST_N tokens is the PRIMARY loop-breaker;
# NUM_PREDICT is only a generous backstop that bounds a pathological runaway (~2K tokens ≈ 30s at
# ~68 tok/s, versus ~240s to fill 16K). It MUST sit above a normal thinking+answer turn: qwen3 runs
# with <think> on, and a tight cap truncated the reasoning before the tool call on harder turns
# (measured: media-call succeeded 1/3 at 512, 2/3 at 1024, 3/3 at 2048), so keep it roomy. Env-tunable.
REPEAT_PENALTY = float(os.getenv("FRIDAY_REPEAT_PENALTY", "1.3"))
REPEAT_LAST_N  = int(os.getenv("FRIDAY_REPEAT_LAST_N", "64"))
NUM_PREDICT    = int(os.getenv("FRIDAY_NUM_PREDICT", "2048"))
# A strong repeat penalty tames free-form speech loops, but it also nudges the model off the exact
# tokens a tool call needs — repeated entity_id prefixes, area names, JSON keys — which shows up as
# over-generalized device targeting ("all the lights" for "the lamps"). So tool-offering turns use a
# gentle penalty (protect HA targeting accuracy); pure-speech turns keep the strong one.
REPEAT_PENALTY_TOOLS = float(os.getenv("FRIDAY_REPEAT_PENALTY_TOOLS", "1.1"))
# ollama_friday (GPU 1) is DEDICATED to Friday — nothing else uses that card — so pin qwen3:8b
# resident indefinitely (keep_alive=-1). A finite window (was "30m") let it idle-unload, and the
# next voice request paid a ~12s cold reload = flaky voice pickup / "can't reach the model".
# Overridable via BMO_KEEP_ALIVE ("-1" / "0" / a duration like "30m"); note an explicit
# per-request keep_alive always wins over the container's OLLAMA_KEEP_ALIVE default.
_KA_RAW = os.getenv("BMO_KEEP_ALIVE", "-1").strip()
KEEP_ALIVE = int(_KA_RAW) if _KA_RAW.lstrip("-").isdigit() else _KA_RAW

# --- Brain swap: toggle Friday's LLM between the default and an experimental model by voice ----------
# "Hey Friday, brain swap" flips _current_model between MODEL and FRIDAY_ALT_BRAIN. The two 8B brains
# can't co-reside on Friday's card alongside STT+TTS (~120 MB free), so a swap UNLOADS the current model
# and warms the new one (~10-20s) in the background — the turn just acks. Runtime-only: resets to MODEL
# on restart (safe default). FRIDAY_BRAIN_SWAP=false disables the whole feature.
_ALT_BRAIN = os.getenv("FRIDAY_ALT_BRAIN", "goekdenizguelmez/JOSIEFIED-Qwen3:8b")
_BRAIN_SWAP_ENABLED = os.getenv("FRIDAY_BRAIN_SWAP", "true").lower() in ("1", "true", "yes")
_current_model = MODEL   # the model _ollama_chat actually calls; mutated by the brain-swap gate
_BRAIN_SWAP_RE = re.compile(
    r"\b(brain\s*swap|swap\s+(?:your\s+|the\s+|my\s+)?brains?|switch\s+(?:your\s+|the\s+)?brains?)\b", re.I)

def _brain_name(m: str) -> str:
    """Spoken name for the swap confirmation. Derived from the active persona's display_name so
    it stays correct across FRIDAY_ALT_BRAIN changes instead of naming a specific fine-tune."""
    if m == MODEL:
        return "my default brain"
    name = personas.get_persona(m).get("display_name") or "the experimental brain"
    return f"the {name} brain"

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
# Caps the web-search passthrough's execute-then-summarise loop (search -> reprompt for a spoken answer).
WEB_MAX_ROUNDS = int(os.getenv("BMO_WEB_MAX_ROUNDS", "3"))
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

# Explicit "hand this off to the swarm" voice intent → code-driven delegate_to_swarm. On the HA
# passthrough path the model has NO delegate_to_swarm tool (HA owns the tools there), so without this
# she can only TALK about the swarm instead of actually delegating. The task is whatever follows the
# phrase; a bare "hand that off to the swarm" refers to the previous user turn. Matches the verb
# phrase up to the task so `.end()` slices the task cleanly.
_SWARM_INTENT_RE = re.compile(
    r"\b(?:"
    r"hand(?:\s+(?:this|that|it))?\s+(?:off\s+)?(?:to\s+)?the\s+swarm|"
    r"(?:give|send|pass|kick|throw)\s+(?:this|that|it)?\s*(?:off\s+|over\s+)?(?:to\s+)?the\s+swarm|"
    r"delegate\s+(?:this|that|it)?\s*(?:to\s+)?the\s+swarm|"
    r"(?:ask|have|get|let|use|put)\s+the\s+swarm"
    r")",
    re.IGNORECASE,
)

# --- Swarm handoff: router-reasoned mode + Friday-side clarify gate ----------------------------------
# Friday no longer force-flags deep research on every handoff. SWARM_HANDOFF_MODE='auto' sends NO mode
# flag so agent_runtime's own neural router reasons about the task and picks the depth itself. And
# before handing a VAGUE ask off, Friday asks ONE clarifying question locally (cheap qwen3:8b call) so
# the swarm gets a CLEAR task instead of dumping assumptions — the felt "what activity level?" behavior,
# done on Friday's side (graduate to the swarm's own Workshop later if needed). FRIDAY_SWARM_CLARIFY=
# false hands off unconditionally.
SWARM_HANDOFF_MODE = os.getenv("FRIDAY_SWARM_MODE", "auto")
_SWARM_CLARIFY_ENABLED = os.getenv("FRIDAY_SWARM_CLARIFY", "true").lower() in ("1", "true", "yes")
# When Friday asks a swarm-clarify question she SPEAKS it via start_conversation (which reopens the mic
# so the user can answer without re-waking) and parks the original ask here. The next turn's answer —
# spoken into the reopened mic OR after a re-wake — folds into a refined handoff. One entry (a single
# satellite), bounded by a TTL so a stale, unanswered clarify can't hijack an unrelated later utterance.
_pending_clarify: dict = {}   # {"original": str, "ts": float}
_CLARIFY_TTL = float(os.getenv("FRIDAY_CLARIFY_TTL", "90"))
_SWARM_ASSESS_SYSTEM = (
    "A task is about to be handed to a research/build swarm. Your ONLY job is to catch tasks that are "
    "too VAGUE to act on. Default STRONGLY to letting it through: reply with exactly READY unless the "
    "task is genuinely under-specified — missing what/which thing, or so open-ended the result would "
    "just be guesses (e.g. 'plan a weekend project', 'help me with the house', 'find me something "
    "fun'). A task that names a concrete subject and what to do with it is READY even if it isn't "
    "perfectly scoped (e.g. 'compare the 3 best budget keyboards under $100' is READY — do NOT ask "
    "about criteria). Only if it is truly too vague, reply with ONE short spoken clarifying question "
    "and nothing else. /no_think")

# Per-brain personas (personas.py). Each brain (default vs the FRIDAY_ALT_BRAIN "brain swap"
# target) carries its OWN persona + memory namespace + visual refs, all editable live at GET
# /personas (mtime-cached, so edits apply with no restart). _compose_persona(model) builds the
# character prompt for whichever brain is active; a full BMO_PERSONA override still short-circuits
# the whole thing (testing/experimentation), matching the old single-persona behavior.
_PERSONA_OVERRIDE = os.getenv("BMO_PERSONA", "")
# Optional shared-secret guard for the LAN-exposed persona editor + CRUD API. Empty = open on LAN.
FRIDAY_PERSONA_TOKEN = os.getenv("FRIDAY_PERSONA_TOKEN", "")


def _compose_persona(model: str) -> str:
    """Character system prompt for the given brain — or the raw BMO_PERSONA override if set."""
    if _PERSONA_OVERRIDE:
        return _PERSONA_OVERRIDE
    try:
        return personas.compose_persona(model)
    except Exception as e:  # noqa: BLE001 — never let a persona read break a voice turn
        print(f"[bmo-brain] persona compose failed ({e}) — falling back to default prompt", flush=True)
        return FRIDAY_SYSTEM_PROMPT


def _memory_owner(model: str) -> str:
    """Per-brain memory owner_id (isolates recall/store between brains — zero bleed)."""
    try:
        return personas.memory_owner(VAULT_OWNER, model)
    except Exception:  # noqa: BLE001
        return VAULT_OWNER

# --- Consult Claude: ask-first offload when the local model dead-ends (claude_consult.py) ---
# The OFFER is appended by code ONLY on the two genuine dead-end paths (loop exhaustion), never by
# the model — the persona deliberately says nothing about consulting Claude, so qwen3:8b is not
# trained to produce this sentinel. CONSENT requires all of: (a) consult_available() (fail-closed
# on key/budget), (b) the immediately-preceding assistant turn ended with _CONSULT_OFFER, and
# (c) the user affirming THIS turn — a real human yes the model cannot fabricate. There is NO
# consult tool in TOOL_SCHEMAS/_DISPATCH, so the model has no way to reach Claude on its own.
_CONSULT_OFFER = "Would you like me to dig deeper on this?"
_CONSULT_AFFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|sure|okay|ok|please|go ahead|do it|"
    r"consult|ask\s+(claude|the\s+swarm)|the\s+swarm|swarm|claude)\b", re.I)
_CONSULT_DECLINE_RE = re.compile(
    r"\b(no|nope|never\s*mind|leave it|forget it|don'?t)\b", re.I)
# Cap the escalation-consult wait so a slow backend (the swarm can take ~40s+) can't blow past HA's
# voice-turn timeout — that would abandon the turn AND risk a duplicate delegation on retry. The
# backend keeps running server-side on a timeout; the user just asks again. Env-tunable.
CONSULT_TIMEOUT = float(os.getenv("FRIDAY_CONSULT_TIMEOUT", "50"))
# Async announce (default): instead of blocking the voice turn on a slow swarm/Claude consult, ack
# instantly and speak the result later via assist_satellite.announce (no wake word) — no HA voice-turn
# timeout, no dead air. Set FRIDAY_SWARM_ANNOUNCE=false (or clear FRIDAY_ANNOUNCE_TARGET) to fall back
# to the bounded sync wait above. ANNOUNCE_TARGET is the satellite to speak back on — HA's chat
# request carries no device id, so a single configured target (multi-satellite needs HA passthrough).
_SWARM_ANNOUNCE = os.getenv("FRIDAY_SWARM_ANNOUNCE", "true").lower() in ("true", "1", "yes")
ANNOUNCE_TARGET = os.getenv("FRIDAY_ANNOUNCE_TARGET",
                            "assist_satellite.google_mini_voice_assist_satellite")
# Chime played before a proactive announce / start_conversation. Empty = HA's default chime; set to a
# media id (e.g. media-source://media_source/local/snowpiercer_chime.mp3) once the file is on HA (#5).
ANNOUNCE_CHIME_MEDIA_ID = os.getenv("FRIDAY_ANNOUNCE_CHIME", "")


# --- Escalation backends: which deeper resources are armed to consult on a dead-end --------------
# The Swarm (delegate_to_swarm, inert unless AGENT_RUNTIME_URL is set) is local and free, so it is
# preferred on a bare "yes"; Claude (claude_consult, fail-closed on key + monthly budget) is the
# deeper, paid fallback. NEITHER is a model tool, so qwen3:8b can never self-escalate — a real human
# "yes" the next turn is always required (see the consent gate in _answer()).
def _consult_backends() -> list:
    """Armed escalation backends, in preference order (index 0 = the bare-'yes' default)."""
    backends = []
    if AGENT_RUNTIME_URL:
        backends.append("swarm")
    if claude_consult.consult_available():
        backends.append("claude")
    return backends


# ONE offer sentence regardless of which backend is armed. From the user's side there is no "swarm" and
# no "Claude" — it is all Friday; the backend is an implementation detail that never reaches speech.
# (Saying "claude"/"swarm" in the reply still steers _chosen_backend for power use — see below.)
_CONSULT_OFFERS = {
    "swarm": _CONSULT_OFFER,
    "claude": _CONSULT_OFFER,
    "both": _CONSULT_OFFER,
}


def _consult_offer_phrase(backends: list) -> str:
    """The offer sentence — empty string when no backend is armed."""
    return _CONSULT_OFFER if backends else ""


def _ends_with_consult_offer(text: str) -> bool:
    """True if a prior assistant turn ended with any consult offer (so a 'yes' now is real consent)."""
    t = (text or "").rstrip()
    return any(t.endswith(o) for o in _CONSULT_OFFERS.values())


def _chosen_backend(user_text: str, backends: list) -> str:
    """Route the affirmation: an explicit 'claude'/'swarm' in the reply wins, else the default."""
    t = (user_text or "").lower()
    if "claude" in t and "claude" in backends:
        return "claude"
    if "swarm" in t and "swarm" in backends:
        return "swarm"
    return backends[0]


def _maybe_offer_consult(fallback_text: str) -> str:
    """On a genuine dead-end, offer a Swarm/Claude consult instead of the plain 'couldn't finish'
    reply — naming only backends that are actually armed, so Friday never offers what she can't
    deliver. Falls back to the plain text when nothing is armed."""
    offer = _consult_offer_phrase(_consult_backends())
    if offer:
        return "I couldn't work that one out on my own. " + offer
    return fallback_text


def _pending_consult_question(convo: list) -> str:
    """The user turn immediately before the offer assistant turn — the request to hand the backend."""
    seen_offer = False
    for m in reversed(convo):
        if not seen_offer:
            if m.get("role") == "assistant" and _ends_with_consult_offer(m.get("content") or ""):
                seen_offer = True
            continue
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


# --- Empty-answer recovery: silent retry, then a varying spoken failure + escalation offer --------
# Nudge for the ONE silent retry when the model returns nothing. Tools are withheld so it is forced
# to answer in words — the common cause is qwen3:8b emitting a blank assistant turn (often right
# after a tool result it should have summarised) instead of speaking.
_RETRY_NUDGE = (
    "Your previous attempt returned no answer at all. Do NOT call any tools now. Using only the "
    "information already in this conversation (including any tool results above), give a short, "
    "direct spoken answer. If you truly cannot, say so plainly in one sentence."
)

# Varying so a run of failures doesn't sound like a broken record. {x} = a short issue fragment.
_ESCALATE_PHRASES = (
    "There seemed to be an issue {x}. I gave it another go and I'm still not getting it.",
    "Something went wrong {x}, and a second attempt didn't sort it out either.",
    "I hit a snag {x} — I tried again but I'm still stuck.",
    "That didn't come together {x}, even after another try.",
    "I ran into trouble {x} and a retry didn't help.",
)

# Friendly label per tool so the issue fragment can name what was being attempted.
_TOOL_ISSUE_LABELS = {
    "GetWeather": "getting the weather", "HassGetWeather": "getting the weather",
    "GetDateTime": "checking the time", "HassGetState": "checking that",
    "HassTurnOn": "controlling that device", "HassTurnOff": "controlling that device",
    "HassToggle": "controlling that device", "HassLightSet": "adjusting that light",
    "delegate_to_swarm": "digging into that",
    "web_search": "looking that up", "search_web": "looking that up",
}


def _issue_fragment(convo: list) -> str:
    """A short '{x}' fragment naming what was attempted, from the most recent tool call; generic else."""
    for m in reversed(convo):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            name = ((m["tool_calls"][0] or {}).get("function", {}) or {}).get("name", "")
            label = _TOOL_ISSUE_LABELS.get(name)
            return "while " + label if label else "with that request"
    return "with that request"


def _failure_with_consult_offer(convo: list) -> str:
    """The spoken reply when an answer fails even after the retry: a varying 'issue with X' line plus,
    if any backend is armed, the escalation offer; otherwise a plain graceful close."""
    base = random.choice(_ESCALATE_PHRASES).format(x=_issue_fragment(convo))
    offer = _consult_offer_phrase(_consult_backends())
    return f"{base} {offer}" if offer else f"{base} Want to try again in a moment?"


# --- Async announce: ack a slow consult instantly, then speak the result via the satellite ---------
_bg_tasks = set()  # strong refs so fire-and-forget background consults aren't GC'd mid-flight

_DIGEST_SYSTEM = (
    "You are Friday, relaying a result OUT LOUD to the user. Rewrite the text below into a SHORT "
    "spoken answer: 2-3 sentences max, most important point first, conversational. No lists, no "
    "markdown, no headings, no emojis, no URLs or 'see [link]'. If there's a lot, give the gist and "
    "stop — do NOT tack on a follow-up question or an offer to continue (it re-triggers the mic). "
    "End on a statement. Output ONLY the spoken reply, nothing else. /no_think")


async def _digest_for_voice(raw: str, who: str = "the swarm") -> str:
    """Condense a long swarm/consult result into a 2-3 sentence spoken answer so TTS doesn't read a
    wall of text. Short results pass through untouched; on any failure, fall back to a truncation."""
    raw = (raw or "").strip()
    if len(raw) < 220:  # already spoken-length
        return raw
    try:
        text, _ = await _ollama_chat(
            [{"role": "system", "content": _DIGEST_SYSTEM},
             {"role": "user", "content": raw[:6000]}], tools=None)
        return (text or "").strip() or raw[:400]
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] digest failed (non-fatal): {e}", flush=True)
        return raw[:400]


def _ends_with_question(text: str) -> bool:
    return (text or "").rstrip().endswith("?")


# assist_satellite.announce / start_conversation are BLOCKING HA service calls — the REST request
# does not return until the announcement finishes PLAYING (announce) or the whole conversation ends
# (start_conversation, which reopens the mic and waits for the user). A 300-char digest is ~20s of
# TTS, and a reopened mic waits far longer, so the old 30s client timeout fired spuriously (an empty-
# string httpx.ReadTimeout) even though HA was fine — that was the "fell off a cliff" silence. This is
# a background task with no voice-turn deadline, so give it room. Env-tunable.
ANNOUNCE_TIMEOUT = float(os.getenv("FRIDAY_ANNOUNCE_TIMEOUT", "150"))


async def _ha_announce(message: str, target: str = None, reopen: bool = None) -> None:
    """Speak `message` on the satellite proactively (no wake word). `reopen` forces the mode:
    True → start_conversation (announce AND reopen the mic so the user can answer without re-waking),
    False → a one-way announce. None (default) picks start_conversation iff the message ends in a
    question. Reserve reopen for when Friday genuinely NEEDS a reply — reopening after just *delivering*
    a result re-triggers the mic on this AEC-less board (it hears her own audio tail) and dead-ends.
    Both carry preannounce_media_id (the announcement chime) when set."""
    target = target or ANNOUNCE_TARGET
    if not (HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN and target and message):
        return
    want_reopen = reopen if reopen is not None else _ends_with_question(message)
    if want_reopen:
        service, payload = "start_conversation", {"entity_id": target, "start_message": message}
    else:
        service, payload = "announce", {"entity_id": target, "message": message}
    if ANNOUNCE_CHIME_MEDIA_ID:
        payload["preannounce_media_id"] = ANNOUNCE_CHIME_MEDIA_ID
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=ANNOUNCE_TIMEOUT) as c:
            r = await c.post(f"{HOME_ASSISTANT_URL}/api/services/assist_satellite/{service}",
                             headers={"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}, json=payload)
        dt = time.monotonic() - t0
        if r.status_code >= 300:
            print(f"[bmo-brain] {service} HTTP {r.status_code} in {dt:.1f}s: {str(r.text)[:200]}", flush=True)
        else:
            print(f"[bmo-brain] {service} ok in {dt:.1f}s", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] {service} failed in {time.monotonic()-t0:.1f}s "
              f"(non-fatal): {type(e).__name__}: {e!r}", flush=True)


def _fire_consult_announce(consult, who: str, target: str = None) -> None:
    """Run a slow consult coroutine in the background; announce its result to the satellite when it
    finishes. Lets the voice turn close instantly instead of blocking ~20-45s on the swarm/Claude."""
    async def _run():
        try:
            result = await consult
        except Exception as e:  # noqa: BLE001
            print(f"[bmo-brain] background {who} consult failed: {type(e).__name__}: {e}", flush=True)
            result = f"I couldn't finish that one — I hit a problem reaching {who}."
        spoken = await _digest_for_voice(result, who)
        # First person: from the user's side it's all Friday — `who` is for logs only, never speech.
        # reopen=False: this is a RESULT delivery, not a question — don't re-trigger the mic afterward.
        await _ha_announce(_speechify(f"Okay, here's what I found. {spoken}"), target, reopen=False)
    t = asyncio.create_task(_run())
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


def _is_echo_of(utterance: str, spoken: str) -> bool:
    """True if `utterance` is really Friday's own `spoken` line coming back through the mic. This
    satellite has no acoustic echo cancellation, so a reopened/hot mic can transcribe her own question
    and it arrives looking like a user turn (confirmed live: her clarify question came back verbatim
    as the 'answer'). Compared on normalized words with a high overlap bar so a user genuinely echoing
    a word or two isn't mistaken for feedback."""
    norm = lambda s: set(re.findall(r"[a-z']+", (s or "").lower()))
    u, s = norm(utterance), norm(spoken)
    if not u or not s:
        return False
    return len(u & s) / len(u) >= 0.8


async def _dispatch_consult(consult, who: str):
    """Speak the result of a slow consult. Default (FRIDAY_SWARM_ANNOUNCE): async — ack now, announce
    the result to the satellite when the backend finishes (no HA voice-turn timeout, no dead air).
    Fallback: a bounded synchronous wait (CONSULT_TIMEOUT). Returns (text, None).

    `who` names the backend for LOGS ONLY — every spoken line here is first person. From the user's
    perspective there is no swarm and no Claude: it is all Friday."""
    if _SWARM_ANNOUNCE and ANNOUNCE_TARGET:
        _fire_consult_announce(consult, who)
        return _speechify("Let me do some digging into that one — I'll get back to you in a moment."), None
    try:
        result = await asyncio.wait_for(consult, timeout=CONSULT_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"[bmo-brain] {who} consult exceeded {CONSULT_TIMEOUT}s — graceful hold", flush=True)
        return _speechify("I'm still working on that one — ask me again in a moment and I'll have it."), None
    return _speechify(f"Okay, here's what I found. {await _digest_for_voice(result, who)}"), None


async def _assess_swarm_task(task: str) -> str:
    """Return ONE clarifying question if `task` is too vague to hand off well, else "" (ready to go).
    One cheap local qwen3:8b call — insurance against the swarm dumping assumptions on a fuzzy ask.
    Fails OPEN (returns "" so the handoff proceeds) on any error or if disabled."""
    if not (_SWARM_CLARIFY_ENABLED and task):
        return ""
    try:
        text, _ = await _ollama_chat(
            [{"role": "system", "content": _SWARM_ASSESS_SYSTEM},
             {"role": "user", "content": task}], tools=None)
        text = (text or "").strip()
        if not text or text.upper().startswith("READY"):
            return ""
        return text if text.endswith("?") else text + "?"
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] swarm task assess failed (non-fatal, handing off): {e}", flush=True)
        return ""


# --- Interaction log: per-turn signals for the nightly "understanding" learning job (Stage 1) -----
# The vault stores the TEXT of each exchange, but NOT the outcome signals (failures, clarifications,
# empty-answer recovery, escalation) the nightly analyzer needs to spot what confused Friday. This
# JSONL log on the persistent /app/data volume captures exactly those — one line per turn. The
# nightly job consumes + rotates it; this side is append-only and best-effort so it never breaks a
# turn. Contains conversation text, so it stays local (same trust boundary as the vault store).
INTERACTION_LOG = os.getenv("FRIDAY_INTERACTION_LOG", "/app/data/interaction_log.jsonl")


def _log_interaction(record: dict) -> None:
    try:
        record = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  **record}
        with open(INTERACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] interaction log write failed (non-fatal): {e}", flush=True)


# --- Location awareness: resolve "near me" to HA's configured home (no clarification loop) ---------
_home_location = None
_home_location_ts = 0.0
_HOME_LOCATION_TTL = float(os.getenv("FRIDAY_HOME_LOCATION_TTL", "3600"))
# HA's configured IANA timezone (e.g. "America/Chicago"), cached from the same /api/config fetch as the
# home location. The container itself has no TZ set, so datetime.now() is UTC — we resolve local time
# through this instead (see _local_now). FRIDAY_TZ overrides if HA is unreachable.
_ha_tz = os.getenv("FRIDAY_TZ") or None


async def _get_home_location() -> str:
    """Home's name + rough coords + timezone from HA (/api/config), cached for _HOME_LOCATION_TTL.
    Injected into the system prompt so "near me" / local weather / local events resolve to home
    instead of triggering a "where are you?" clarification. Empty (inert) if HA has no token/URL."""
    global _home_location, _home_location_ts, _ha_tz
    if not (HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN):
        return ""
    now = time.time()
    if _home_location is not None and (now - _home_location_ts) < _HOME_LOCATION_TTL:
        return _home_location
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            r = await c.get(f"{HOME_ASSISTANT_URL}/api/config",
                            headers={"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"})
        if r.status_code == 200:
            cfg = r.json()
            loc = cfg.get("location_name") or "Home"
            lat, lon = cfg.get("latitude"), cfg.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                loc += f" (approx {lat:.3f}, {lon:.3f})"
            if cfg.get("time_zone"):
                loc += f", timezone {cfg['time_zone']}"
                _ha_tz = cfg["time_zone"]
            _home_location, _home_location_ts = loc, now
            return loc
        print(f"[bmo-brain] home location fetch HTTP {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] home location fetch failed (non-fatal): {e}", flush=True)
    return _home_location or ""


def _local_now() -> datetime.datetime:
    """Current time in HA's configured timezone (see _ha_tz). The container clock is UTC (no TZ set),
    so this is the ONLY correct local-time source — datetime.now() would be ~5h off. Falls back to
    system time only if the tz is unknown/invalid."""
    if _ha_tz:
        try:
            from zoneinfo import ZoneInfo
            return datetime.datetime.now(ZoneInfo(_ha_tz))
        except Exception:  # noqa: BLE001
            pass
    return datetime.datetime.now()


# Ambient weather (Tier 0-A, same idea as the date/time injection): keep current conditions warm in a
# small TTL cache and inject them into the prompt so "what's the weather" answers in ONE LLM call
# instead of a get_current_weather tool round-trip. Refresh is ASYNC — a stale turn kicks off a
# background refresh and uses whatever is cached (empty on first run → the model just falls back to the
# tool, still correct). Never blocks the turn.
_weather_cache = {"text": "", "ts": 0.0}
_WEATHER_TTL = float(os.getenv("FRIDAY_WEATHER_TTL", "600"))  # 10 min


async def _refresh_weather() -> None:
    try:
        wx = await get_current_weather()
        if wx and "unreachable" not in wx.lower():   # don't cache the error fallback string
            _weather_cache["text"], _weather_cache["ts"] = wx, time.time()
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] weather refresh failed (non-fatal): {e}", flush=True)


def _weather_for_prompt() -> str:
    """Cached current weather for prompt injection. Non-blocking: if stale, kick off a background
    refresh and return whatever is currently cached (empty until the first refresh lands)."""
    if time.time() - _weather_cache["ts"] > _WEATHER_TTL:
        t = asyncio.create_task(_refresh_weather())
        _bg_tasks.add(t)
        t.add_done_callback(_bg_tasks.discard)
    return _weather_cache["text"]


# Location-relevant swarm asks: fold Friday's known home location into the task so "near me" / local /
# weather / events resolve without the swarm (or the clarify assessor) stopping to ask where the user
# is — Friday already knows from HA (see _get_home_location). No-op for tasks with no location angle.
_LOC_RE = re.compile(
    r"\b(near\s*(me|by|here)|nearby|local(?:ly)?|around\s+(here|me|town)|in\s+my\s+area|"
    r"weather|forecast|temperature|climate|restaurants?|bars?|events?|things?\s+to\s+do|"
    r"this\s+weekend|hikes?|trails?|parks?)\b", re.I)


async def _with_location_context(task: str) -> str:
    if not task or not _LOC_RE.search(task):
        return task
    loc = await _get_home_location()
    if not loc:
        return task
    return (f"{task}\n\n(Location context: the user is near {loc}. Resolve 'near me', 'local', and "
            "'nearby' to that area — do not ask where they are.)")


app = FastAPI(title="Friday Brain (vault-RAG assistant)")


@app.get("/health")
async def health():
    active = ""
    try:
        active = personas.get_persona(_current_model).get("display_name", "")
    except Exception:  # noqa: BLE001
        pass
    return {"status": "ok", "model": MODEL, "current_model": _current_model,
            "active_persona": active, "vault": bool(VAULT_URL and VAULT_OWNER), "ollama": OLLAMA_URL,
            "node_speakers": NODE_SPEAKER_MAP}


# ---------------------------------------------------------------------------
# Persona / memory / visual-reference management (LAN editor page + CRUD API).
# The editor page is served at GET /personas; the API under /api/personas. Both are guarded by
# FRIDAY_PERSONA_TOKEN when set (LAN-first — open on the LAN by default, opt-in secret for the
# external Traefik route). Model ids can contain "/" (e.g. goekdenizguelmez/JOSIEFIED-Qwen3:8b),
# so the {model:path} converter is used and more-specific routes are registered first.
# ---------------------------------------------------------------------------
def _persona_auth_ok(request: Request) -> bool:
    if not FRIDAY_PERSONA_TOKEN:
        return True
    tok = request.headers.get("x-persona-token") or request.query_params.get("token") or ""
    auth = request.headers.get("authorization", "")
    if not tok and auth.lower().startswith("bearer "):
        tok = auth[7:]
    return hmac.compare_digest(tok, FRIDAY_PERSONA_TOKEN)


@app.get("/personas")
async def persona_editor_page():
    # The page itself carries no secrets; it prompts for the token (if configured) and sends it on
    # every API call. Serving it unauthenticated keeps a bookmarked /personas link usable.
    return HTMLResponse(PERSONA_EDITOR_HTML)


@app.get("/api/personas")
async def api_personas_all(request: Request):
    if not _persona_auth_ok(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = personas.load_personas()
    return {"personas": data,
            "active_model": _current_model,
            "default_model": MODEL,
            "alt_model": _ALT_BRAIN,
            "token_required": bool(FRIDAY_PERSONA_TOKEN)}


@app.post("/api/personas/{model:path}/visual_ref")
async def api_persona_add_ref(model: str, request: Request, file: UploadFile = File(...)):
    if not _persona_auth_ok(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = await file.read()
    if not data:
        return JSONResponse({"error": "empty upload"}, status_code=400)
    if len(data) > 12 * 1024 * 1024:
        return JSONResponse({"error": "file too large (max 12 MB)"}, status_code=413)
    ref = personas.add_visual_ref(model, file.filename or "image", data)
    return {"ok": True, "ref": ref}


@app.get("/api/personas/{model:path}/visual_ref/{name}")
async def api_persona_get_ref(model: str, name: str, request: Request):
    if not _persona_auth_ok(request):
        return PlainTextResponse("unauthorized", status_code=401)
    path = personas.visual_ref_path(model, name)
    if not path:
        return PlainTextResponse("not found", status_code=404)
    return FileResponse(path)


@app.get("/api/personas/{model:path}/self_image")
async def api_persona_self_image(model: str, request: Request):
    # The canonical self-portrait for this brain — the seed a future "make a picture of you"
    # image-gen call should reference. TODO(visual-refs wiring): the OmniGen/ComfyUI image-gen
    # path lives in the agents/ tree (a separate service), not friday_brain — that call should
    # fetch this endpoint (or personas.self_image_path) to condition the generation on the brain's
    # own look. Left as a stub hook here; not wired into image gen yet.
    if not _persona_auth_ok(request):
        return PlainTextResponse("unauthorized", status_code=401)
    path = personas.self_image_path(model)
    if not path:
        return PlainTextResponse("no self image set", status_code=404)
    return FileResponse(path)


@app.put("/api/personas/{model:path}")
async def api_persona_update(model: str, request: Request):
    if not _persona_auth_ok(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "expected an object"}, status_code=400)
    data = personas.load_personas()
    entry = data.get(model) or personas.get_persona(model)
    for k in personas.EDITABLE_FIELDS:
        if k in body:
            entry[k] = body[k]
    data[model] = entry
    personas.save_personas(data)
    return {"ok": True, "persona": entry}


@app.get("/api/personas/{model:path}")
async def api_persona_get(model: str, request: Request):
    if not _persona_auth_ok(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return personas.get_persona(model)


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "bmo"}]}


async def _vault_recall(query: str, owner_id: str = ""):
    """Return a list of recalled memory strings for the query (empty on any failure).

    owner_id is the per-brain memory owner (see _memory_owner); defaults to the base VAULT_OWNER."""
    owner = owner_id or VAULT_OWNER
    if not (VAULT_URL and owner and query):
        return []
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            r = await c.post(f"{VAULT_URL}/v1/memories/search",
                             json={"query": query, "owner_id": owner, "limit": VAULT_LIMIT})
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
# Emojis/pictographs: the small model sprinkles them into "friendly" replies (e.g. a trailing 😊).
# TTS reads them as noise ("smiling face"), and a trailing emoji after a "?" also defeats the
# start_conversation (reopen-mic) check in _ha_announce. Strip them from all spoken output.
_SPEECH_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002190-\U000021FF\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F\U00002300-\U000023FF\U0000200D\U0000FE0F]+", flags=re.UNICODE)


def _speechify(text: str) -> str:
    if not text or not text.strip():
        return text
    t = _SPEECH_LINK_RE.sub(r"\1", text)
    t = _SPEECH_STAR_RE.sub(r"\1", t)
    t = _SPEECH_USCORE_RE.sub(r"\1", t)
    t = t.replace("`", "")
    t = _SPEECH_HEADER_RE.sub("", t)
    t = _SPEECH_BULLET_RE.sub("", t)
    t = _SPEECH_EMOJI_RE.sub("", t)
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
    # keep_alive pins qwen3:8b resident in VRAM between calls (KEEP_ALIVE=-1 by default now that
    # ollama_friday's GPU is dedicated to Friday) so a voice turn never pays a cold reload.
    penalty = REPEAT_PENALTY_TOOLS if tools else REPEAT_PENALTY
    payload = {"model": _current_model, "messages": messages, "stream": False, "keep_alive": KEEP_ALIVE,
               "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX,
                           "repeat_penalty": penalty, "repeat_last_n": REPEAT_LAST_N,
                           "num_predict": NUM_PREDICT}}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as c:
        r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
        r.raise_for_status()
        message = r.json().get("message", {})
    text = _strip_think(message.get("content", "") or "")
    tool_calls = message.get("tool_calls") or None
    return text, tool_calls


async def _do_brain_swap(old_model: str, new_model: str) -> None:
    """Background half of a brain swap: unload the old model (free VRAM — two 8B brains can't co-reside
    with STT+TTS on Friday's card) then warm the new one, pinned. Fires after the swap gate acks; the
    next voice turn calls _current_model (already flipped)."""
    async with httpx.AsyncClient(timeout=180) as c:
        try:
            await c.post(f"{OLLAMA_URL}/api/generate", json={"model": old_model, "keep_alive": 0})
            print(f"[bmo-brain] brain-swap: unloaded {old_model}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[bmo-brain] brain-swap unload failed (non-fatal): {e}", flush=True)
        try:
            await c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": new_model, "prompt": "ok", "keep_alive": KEEP_ALIVE,
                "options": {"num_ctx": NUM_CTX}})
            print(f"[bmo-brain] brain-swap: warmed {new_model}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[bmo-brain] brain-swap warm failed (non-fatal): {e}", flush=True)


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
            if isinstance(result, str) and result.startswith(MEDIA_SEARCH_SENTINEL):
                # Pi/self-exec has no async-announce channel for the swarm-search fallback, so
                # degrade to an honest spoken message rather than leaking the sentinel to the model.
                try:
                    src = json.loads(result[len(MEDIA_SEARCH_SENTINEL):]).get("source", "that")
                except Exception:  # noqa: BLE001
                    src = "that"
                result = (f"I don't have a station for {src} set up, and I can't search for one on this "
                          "device. Try a station name like jazz or chill, or a stream URL.")
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


# friday_brain's own READ-ONLY info tools — web_search + the Open-Meteo weather tools (incl. the new
# hourly "hottest part of the day") + news. They live in TOOL_SCHEMAS (the self-exec set) and are NOT
# among the tools HA sends on a voice turn, so without this a live-info question on voice has no real
# data source: it either deflects, or (with web_search alone) reads DuckDuckGo LINKS aloud instead of
# the actual answer. Offer them alongside HA's tools and execute locally, like the registry
# passthrough. All read-only, so unlike the registry tools they're safe on ANY turn — no gate.
_INFO_TOOL_NAMES = frozenset({"web_search", "get_current_weather", "get_weather_forecast",
                              "get_hourly_forecast", "get_news_headlines"})
_INFO_SCHEMAS = [t for t in TOOL_SCHEMAS if (t.get("function") or {}).get("name") in _INFO_TOOL_NAMES]


def _split_info_calls(tool_calls):
    """Partition tool_calls into (info-owned we execute here, HA-owned handed back to HA untouched).
    HA-owned (HassTurnOn, etc.) return UNEXECUTED for HA to run, exactly as normal passthrough does."""
    info, other = [], []
    for tc in (tool_calls or []):
        name = (tc.get("function") or {}).get("name", "")
        (info if name in _INFO_TOOL_NAMES else other).append(tc)
    return info, other


async def _passthrough_with_info(messages, tools):
    """Passthrough tool-calling that ALSO offers friday_brain's read-only info tools (web_search +
    weather + news) and executes them locally, looping until final text or an HA-owned tool_call
    (returned UNEXECUTED for HA). Lets live-info questions answer with REAL DATA (a weather ask hits
    Open-Meteo, not a link dump). Falls back to plain passthrough if none are found. Returns
    (text, tool_calls) matching _answer's contract."""
    all_tools = list(tools) + _INFO_SCHEMAS
    convo = list(messages)
    text, tool_calls = "", None
    for _round in range(WEB_MAX_ROUNDS):
        text, tool_calls = await _ollama_chat(convo, all_tools)
        info_calls, ha_calls = _split_info_calls(tool_calls)
        if info_calls:
            # Execute our OWN info tools first; if the same round also carried an HA on/off call,
            # hand that back after (mirrors the registry passthrough so a batched call isn't dropped).
            convo = convo + [{"role": "assistant", "content": text, "tool_calls": info_calls}]
            for tc in info_calls:
                fn = tc.get("function") or {}
                result = await call_tool(fn.get("name", ""), fn.get("arguments") or {})
                print(f"[bmo-brain] info tool={fn.get('name')} args={fn.get('arguments')} "
                      f"-> {str(result)[:160]!r}", flush=True)
                convo.append({"role": "tool", "content": result})
            if ha_calls:
                return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
            continue  # only info calls -> reprompt for a spoken answer built from the results
        if ha_calls:
            return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
        return text, None  # no tool_calls -> final text answer
    print(f"[bmo-brain] info passthrough loop exhausted {WEB_MAX_ROUNDS} rounds", flush=True)
    return (text or "I looked but couldn't pull that together — want me to try again?"), None


# friday_brain's own media-control tools (transport + volume + stream play), executed locally via HA's
# service API — HA's Assist doesn't reliably expose media_player control as intents, so without this a
# "play/pause/skip/volume" turn had nothing to call (confirmed: no media tool existed at all). These
# are WRITES but reversible/low-risk, so — unlike the registry tools — no consent gate; they're offered
# on the passthrough path ONLY when the utterance looks media-related (_MEDIA_INTENT_RE) to keep
# ordinary turns lean. The read-only info tools ride along so a batched "play jazz and what's the
# weather" still answers both. HA-owned tool_calls still return UNEXECUTED to HA.
_MEDIA_TOOL_NAMES = frozenset({"control_media", "set_volume", "play_media"})
_MEDIA_SCHEMAS = [t for t in TOOL_SCHEMAS if (t.get("function") or {}).get("name") in _MEDIA_TOOL_NAMES]
_MEDIA_LOCAL_NAMES = _MEDIA_TOOL_NAMES | _INFO_TOOL_NAMES
_MEDIA_INTENT_RE = re.compile(
    r"\b(play|pause|resume|unpause|"
    r"stop\s+(?:the\s+)?(?:music|playback|song|track|speaker|media)|"
    r"skip|next\s+(?:track|song)|previous\s+(?:track|song)|"
    r"volume|louder|quieter|mute|unmute|"
    r"turn\s+(?:it\s+|the\s+(?:volume|music|sound)\s+)?(?:up|down)|"
    r"put\s+on\s+(?:some\s+)?\w+|cast)\b", re.I)


def _split_media_calls(tool_calls):
    """(locally-owned we execute here = media + read-only info, HA-owned handed back to HA untouched)."""
    local, other = [], []
    for tc in (tool_calls or []):
        name = (tc.get("function") or {}).get("name", "")
        (local if name in _MEDIA_LOCAL_NAMES else other).append(tc)
    return local, other


# HA may expose its OWN media intents (HassMediaSearchAndPlay from Spotify/Music Assistant,
# HassMediaPause, HassSetVolume, HassMediaNext, ...). When it does, THOSE own media — friday_brain's
# media tools must step aside. If they don't, the model sometimes picks ours for a "play X" and either
# kicks off a bogus radio-stream search or no-ops media_play (a false "Done" with nothing playing),
# and even collides with HA's real intent (observed live once Spotify was added). Our media tools are
# a FALLBACK, offered only when HA exposes no media control at all (the original gap they filled).
_HA_MEDIA_NAME_RE = re.compile(r"(media|volume)", re.I)


def _ha_offers_media(tools) -> bool:
    for t in (tools or []):
        name = (t.get("function") or {}).get("name") or t.get("name") or ""
        if _HA_MEDIA_NAME_RE.search(name):
            return True
    return False


# HA's own media intents (HassSetVolumeRelative, HassMediaPause, ...) reject a target whose
# CURRENT PLAYBACK STATE doesn't qualify — confirmed live: a single, unambiguously-targeted
# "idle" speaker (on, nothing loaded) still gets MatchFailedError/MatchFailedReason.STATE from
# HassSetVolumeRelative, independent of area/device targeting being correct. friday_brain's own
# control_media/set_volume tools (tools.py) call HA's media_player services directly and have no
# such state restriction. So when the MOST RECENT tool round this exchange was a media-intent
# STATE failure, _answer() routes into _passthrough_with_media as a fallback for this turn even
# though HA offers native media control — letting the model retry via friday_brain's tools
# instead of looping on an HA intent that can never succeed against an idle target.
_MATCH_FAILED_STATE_RE = re.compile(r'"MatchFailedError".*?MatchFailedReason\.STATE', re.DOTALL)


def _trailing_media_tool_round(convo):
    """(name, args, content) of the most recent tool_call/result pair this exchange, or None.
    Pairing mirrors _extract_tool_attempts: prefer tool_call_id when present, else FIFO — a
    single assistant turn can carry more than one tool_call. `args` is always a dict (coerced
    from a JSON string on the OpenAI-compatible surface, same as _extract_tool_attempts)."""
    pairs = []
    pending = []
    for m in convo:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            pending = list(m["tool_calls"])
        elif role == "tool" and pending:
            result_id = m.get("tool_call_id")
            idx = None
            if result_id:
                idx = next((i for i, c in enumerate(pending) if c.get("id") == result_id), None)
            tc = pending.pop(idx if idx is not None else 0)
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (TypeError, ValueError):
                    args = {}
            pairs.append((fn.get("name", ""), args or {}, m.get("content")))
    return pairs[-1] if pairs else None


def _trailing_media_state_failure(convo) -> bool:
    """Whether the most recent tool_call/result pair in this exchange is a HA media/volume
    intent that failed with MatchFailedReason.STATE."""
    pair = _trailing_media_tool_round(convo)
    if not pair:
        return False
    name, _args, content = pair
    if not _HA_MEDIA_NAME_RE.search(name):
        return False
    text = content if isinstance(content, str) else json.dumps(content or {})
    return bool(_MATCH_FAILED_STATE_RE.search(text))


# Deterministic execution for the ONE case we can resolve with total confidence: the failed HA
# call named no area/name of its own (an implicit "the speaker"/"it" command) AND this request
# has a configured node-default speaker (NODE_SPEAKER_MAP). Confirmed live that even a leading,
# explicitly-grounded nudge (_state_fallback_nudge) gets lost in the full persona+vault+status
# system prompt under /no_think — a small model does not reliably act on it. Rather than keep
# tuning prompt wording, execute the equivalent friday_brain tool call directly in code, matching
# this codebase's existing house style of normalizing/deciding deterministically instead of
# hoping the model self-corrects (see _sanitize_hass_tool_calls, HASS_CLARIFY_THRESHOLD).
_HASS_MEDIA_ACTION_MAP = {
    "HassMediaPause": lambda args: ("control_media", {"action": "pause"}),
    "HassMediaUnpause": lambda args: ("control_media", {"action": "play"}),
    "HassMediaNext": lambda args: ("control_media", {"action": "next"}),
    "HassMediaPrevious": lambda args: ("control_media", {"action": "previous"}),
    "HassSetVolumeRelative": lambda args: (
        "control_media",
        {"action": "volume_up" if (args.get("volume_step") or 0) >= 0 else "volume_down"}),
    "HassSetVolume": lambda args: (
        "set_volume", {"level": args.get("volume_level", args.get("volume", 50))}),
}


_MEDIA_ACTION_SPEECH = {
    "volume_up": "Turned the {name} up.",
    "volume_down": "Turned the {name} down.",
    "pause": "Paused on the {name}.",
    "play": "Resumed on the {name}.",
    "mute": "Muted the {name}.",
    "unmute": "Unmuted the {name}.",
    "next": "Skipped to the next track on the {name}.",
    "previous": "Went back a track on the {name}.",
    "stop": "Stopped the {name}.",
}


async def _speak_media_action(tool_name: str, tool_args: dict, entity_id: str):
    """Execute tool_name(tool_args, entity_id=entity_id) via friday_brain's own tools and build a
    natural spoken confirmation — or None on failure (caller decides how to handle/report that).
    Shared by _deterministic_media_fallback and _bare_media_shortcut so both speak the same way;
    neither surfaces tools.py's raw programmatic "Done: <action> on <entity_id>" string, which is
    meant for a MODEL to paraphrase — these paths bypass the model entirely, so the text has to
    read well on its own."""
    result = await call_tool(tool_name, {**tool_args, "entity_id": entity_id})
    if not (isinstance(result, str) and result and not result.lower().startswith("error")):
        return None
    try:
        players = await list_media_players()
        friendly = next((fn for eid, fn in players if eid == entity_id), entity_id)
    except Exception:  # noqa: BLE001
        friendly = entity_id
    if tool_name == "set_volume":
        return f"Set the {friendly} to {tool_args.get('level')} percent."
    template = _MEDIA_ACTION_SPEECH.get(tool_args.get("action", ""))
    return template.format(name=friendly) if template else f"Done on the {friendly}."


async def _deterministic_media_fallback(convo):
    """Returns a spoken result string if the deterministic fallback applies, else None (caller
    falls through to the existing LLM-driven passthrough)."""
    pair = _trailing_media_tool_round(convo)
    if not pair:
        return None
    name, args, content = pair
    if not _HA_MEDIA_NAME_RE.search(name):
        return None
    text = content if isinstance(content, str) else json.dumps(content or {})
    if not _MATCH_FAILED_STATE_RE.search(text):
        return None
    if args.get("area") or args.get("name"):
        # The failed call already named a specific area/device — a real, deliberate target.
        # Overriding it with the node default would silently redirect a command aimed
        # somewhere specific; leave this case to the model/passthrough instead.
        return None
    default = current_node_speaker()
    if not default:
        return None
    mapper = _HASS_MEDIA_ACTION_MAP.get(name)
    if not mapper:
        return None
    tool_name, tool_args = mapper(args)
    spoken = await _speak_media_action(tool_name, tool_args, default)
    print(f"[bmo-brain] deterministic media state-fallback: {name}({args}) -> "
          f"{tool_name}({tool_args}, entity_id={default}) -> {spoken!r}", flush=True)
    return spoken  # None -> let the existing clarify/passthrough path handle a genuine failure


# A curated EXACT-phrase allowlist (not a broad regex) of bare, untargeted media commands — "volume
# up", "pause", "make it louder" — deliberately narrow so it can NEVER fire on a command that names
# a specific room/device ("turn up the kitchen volume" has no entry here and falls through to the
# normal model+HA path unchanged). Every value is (tool_name, tool_args) for friday_brain's own
# tools.py — same shape _HASS_MEDIA_ACTION_MAP produces.
_BARE_MEDIA_PHRASES = {
    "volume up": ("control_media", {"action": "volume_up"}),
    "turn it up": ("control_media", {"action": "volume_up"}),
    "turn the volume up": ("control_media", {"action": "volume_up"}),
    "turn up the volume": ("control_media", {"action": "volume_up"}),
    "make it louder": ("control_media", {"action": "volume_up"}),
    "louder": ("control_media", {"action": "volume_up"}),
    "volume down": ("control_media", {"action": "volume_down"}),
    "turn it down": ("control_media", {"action": "volume_down"}),
    "turn the volume down": ("control_media", {"action": "volume_down"}),
    "turn down the volume": ("control_media", {"action": "volume_down"}),
    "make it quieter": ("control_media", {"action": "volume_down"}),
    "make it softer": ("control_media", {"action": "volume_down"}),
    "quieter": ("control_media", {"action": "volume_down"}),
    "softer": ("control_media", {"action": "volume_down"}),
    "pause": ("control_media", {"action": "pause"}),
    "pause it": ("control_media", {"action": "pause"}),
    "pause the music": ("control_media", {"action": "pause"}),
    "stop the music": ("control_media", {"action": "stop"}),
    "stop it": ("control_media", {"action": "stop"}),
    "play": ("control_media", {"action": "play"}),
    "resume": ("control_media", {"action": "play"}),
    "resume the music": ("control_media", {"action": "play"}),
    "resume it": ("control_media", {"action": "play"}),
    "unpause": ("control_media", {"action": "play"}),
    "unpause it": ("control_media", {"action": "play"}),
    "mute": ("control_media", {"action": "mute"}),
    "mute it": ("control_media", {"action": "mute"}),
    "unmute": ("control_media", {"action": "unmute"}),
    "unmute it": ("control_media", {"action": "unmute"}),
    "skip": ("control_media", {"action": "next"}),
    "skip it": ("control_media", {"action": "next"}),
    "next": ("control_media", {"action": "next"}),
    "next track": ("control_media", {"action": "next"}),
    "next song": ("control_media", {"action": "next"}),
    "previous": ("control_media", {"action": "previous"}),
    "previous track": ("control_media", {"action": "previous"}),
    "previous song": ("control_media", {"action": "previous"}),
    "go back": ("control_media", {"action": "previous"}),
}


def _normalize_bare_phrase(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower()).strip()


async def _bare_media_shortcut(last_user: str):
    """Deterministic round-0 shortcut for a small, curated set of EXACT bare media phrases (see
    _BARE_MEDIA_PHRASES) when this request has a configured node-default speaker. Bypasses vault
    recall, the LLM, and HA's native intent entirely.

    Why this exists (confirmed live): qwen3:8b sometimes doesn't even ATTEMPT a tool call on round
    1 for these exact terse phrasings ('volume up', 'turn it down') — it just answers in text.
    _deterministic_media_fallback can't help there either, since it only reacts to an ALREADY-
    FAILED HA tool round; if nothing was ever attempted, there's nothing to react to. This runs
    BEFORE the model is ever called, so it can't depend on the model trying anything first.

    Returns spoken text, or None (no exact match / no node configured / the local call itself
    failed) — caller falls through to the normal path unchanged."""
    default = current_node_speaker()
    if not default:
        return None
    match = _BARE_MEDIA_PHRASES.get(_normalize_bare_phrase(last_user))
    if not match:
        return None
    tool_name, tool_args = match
    spoken = await _speak_media_action(tool_name, tool_args, default)
    if spoken:
        print(f"[bmo-brain] bare media shortcut: {last_user!r} -> {tool_name}({tool_args}, "
              f"entity_id={default})", flush=True)
    return spoken


# Tier 1 (entity): give the model the real media_player entity_ids so it targets the right speaker
# instead of guessing. Cached fetch (shared with the resolver), injected only on media turns.
async def _media_players_prompt():
    try:
        players = await list_media_players()
    except Exception:  # noqa: BLE001
        players = []
    if not players:
        return None
    listing = "; ".join(f"{eid} = {fn}" for eid, fn in players[:20])
    return ("MEDIA PLAYERS in this home — when you call a media tool, pass one of these EXACT "
            "entity_id values (choose by room): " + listing)


_URL_RE = re.compile(r"https?://[^\s\"'>)\]]+", re.I)


async def _media_search_and_play(entity_id: str, source: str):
    """Tier 3 (music): the source wasn't a known station/URL, so ask the swarm to find a playable
    STREAM URL, then cast it and announce the result. Runs in the background after an immediate
    spoken ack (the swarm is slow). Announce-only (reopen=False) — this hardware self-triggers if the
    mic reopens on Friday's own TTS (see the reopen/echo notes)."""
    try:
        ask = (f"Find one direct, publicly-playable internet-radio or audio STREAM URL "
               f"(an mp3/aac/m3u8/icecast/shoutcast endpoint) for: {source}. "
               f"Respond with ONLY the URL and nothing else.")
        raw = await delegate_to_swarm(ask, mode="research")
        m = _URL_RE.search(str(raw) or "")
        if not m:
            await _ha_announce(f"I couldn't find a stream for {source}.", reopen=False)
            return
        played = await call_tool("play_media", {"entity_id": entity_id, "source": m.group(0)})
        if isinstance(played, str) and played.startswith("Playing"):
            await _ha_announce(f"Found a stream for {source}. Playing it now.", reopen=False)
        else:
            await _ha_announce(f"I found a stream for {source} but couldn't start it.", reopen=False)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] media search-and-play failed: {type(e).__name__}: {e}", flush=True)
        await _ha_announce(f"I ran into trouble finding a stream for {source}.", reopen=False)


def _state_fallback_nudge() -> str:
    """Built per-request (not a constant) so it can name THIS node's own default speaker by
    entity_id when known — a small model won't reliably guess which of several undifferentiated
    media_player entities in the injected list is 'this room's own speaker', and control_media/
    set_volume/play_media all require entity_id, so an ungrounded nudge alone (confirmed live)
    just gets a text-only 'which device?' instead of the tool call this fallback exists for."""
    default = current_node_speaker()
    hint = (f" This request's own speaker is {default} — use that entity_id unless the user "
            "clearly named a different device." if default else "")
    return (
        "\n\nNOTE: the native device-control tool just failed on this target because of its current "
        "playback state (e.g. idle/nothing loaded) — not because the wrong device was targeted. Do NOT "
        "retry the same native tool again. Instead call control_media/set_volume/play_media directly "
        "on the media_player entity you were just targeting." + hint
    )


async def _passthrough_with_media(messages, tools, state_fallback: bool = False):
    """Passthrough tool-calling that ALSO offers friday_brain's media-control tools (+ the read-only
    info tools) and executes them locally via HA's service API, looping until final text or an
    HA-owned tool_call (returned UNEXECUTED for HA). Mirrors _passthrough_with_info; reached on a
    media-intent turn. Injects the real media_player list (Tier 1) and honors play_media's
    swarm-search signal (Tier 3). Returns (text, tool_calls) matching _answer's contract.

    state_fallback=True means this turn was routed here specifically because HA's own media intent
    just failed with MatchFailedReason.STATE (see _trailing_media_state_failure) — HA's tools are
    still offered (still useful for other targets/actions this same turn), but a nudge steers the
    model toward friday_brain's own state-agnostic tools instead of re-trying the doomed HA call."""
    all_tools = list(tools) + _MEDIA_SCHEMAS + _INFO_SCHEMAS
    convo = list(messages)
    if state_fallback and convo and convo[0].get("role") == "system":
        # PREPENDED, not appended: confirmed live that a small model under /no_think, with this
        # nudge tacked onto the END of the full persona+vault+status system prompt, ignores it
        # and asks a clarifying question anyway — the same nudge WORKS when it's the first thing
        # in a minimal prompt. Leading position gets it read before attention is spent elsewhere.
        convo = [{**convo[0], "content": _state_fallback_nudge().strip() + "\n\n" + convo[0]["content"]}] + convo[1:]
    elif state_fallback:
        convo = [{"role": "system", "content": _state_fallback_nudge().strip()}] + convo
    mp = await _media_players_prompt()
    if mp:
        if convo and convo[0].get("role") == "system":
            convo = [{**convo[0], "content": convo[0]["content"] + "\n\n" + mp}] + convo[1:]
        else:
            convo = [{"role": "system", "content": mp}] + convo
    text, tool_calls = "", None
    for _round in range(WEB_MAX_ROUNDS):
        text, tool_calls = await _ollama_chat(convo, all_tools)
        local_calls, ha_calls = _split_media_calls(tool_calls)
        if local_calls:
            convo = convo + [{"role": "assistant", "content": text, "tool_calls": local_calls}]
            for tc in local_calls:
                fn = tc.get("function") or {}
                result = await call_tool(fn.get("name", ""), fn.get("arguments") or {})
                if isinstance(result, str) and result.startswith(MEDIA_SEARCH_SENTINEL):
                    # Tier 3 (music): source unresolved. Hand to the swarm in the background, ack now.
                    try:
                        payload = json.loads(result[len(MEDIA_SEARCH_SENTINEL):])
                    except Exception:  # noqa: BLE001
                        payload = {}
                    src = payload.get("source") or "that"
                    eid = payload.get("entity_id") or ""
                    if AGENT_RUNTIME_URL and eid:
                        _t = asyncio.create_task(_media_search_and_play(eid, src))
                        _bg_tasks.add(_t)
                        _t.add_done_callback(_bg_tasks.discard)
                        print(f"[bmo-brain] media source {src!r} unresolved -> swarm search (async)", flush=True)
                        return _speechify(f"I don't have {src} as a station. Let me find a stream for it, one moment."), None
                    return _speechify(f"I don't have a station for {src}. Try one like jazz or chill, "
                                      "or give me a stream URL."), None
                print(f"[bmo-brain] media tool={fn.get('name')} args={fn.get('arguments')} "
                      f"-> {str(result)[:160]!r}", flush=True)
                convo.append({"role": "tool", "content": result})
            if ha_calls:
                return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
            continue  # only local calls -> reprompt for a spoken confirmation
        if ha_calls:
            return text, await _sanitize_hass_tool_calls(ha_calls, VAULT_OWNER)
        return text, None  # no tool_calls -> final text answer
    print(f"[bmo-brain] media passthrough loop exhausted {WEB_MAX_ROUNDS} rounds", flush=True)
    return (text or "I tried to do that with the media player but couldn't finish — want me to try again?"), None


# Flips True the first time the vault 404s the pending-search endpoint. Newer MemPalace builds
# removed /v1/extract/pending/search (confirmed 2026-07-15 — the vault now exposes /v1/extract,
# /v1/entities/extract, /v1/palace/audit/extractions, none of them a pending-queue search), so
# without this every single turn paid a wasted round-trip AND logged a 404. Same-session recall is
# still covered by the local pending tier (local_pending.search_local), so disabling loses nothing;
# a process restart re-probes, so a future vault that restores the endpoint self-heals.
_pending_recall_unavailable = False


async def _pending_recall(query: str, owner_id: str):
    """Query the vault's pending (not-yet-processed) queue for same-day recall.

    Fast text search over conversations queued but not yet promoted to the curated
    memory store. Never raises and keeps a short timeout — this must not block the
    response for long if the vault is slow or unreachable."""
    global _pending_recall_unavailable
    if _pending_recall_unavailable or not (VAULT_URL and owner_id and query):
        return []
    try:
        async with httpx.AsyncClient(timeout=VAULT_PENDING_TIMEOUT) as c:
            r = await c.get(f"{VAULT_URL}/v1/extract/pending/search",
                             params={"owner_id": owner_id, "query": query})
        if r.status_code == 200:
            return [item["content"] for item in r.json()]
        if r.status_code == 404:
            _pending_recall_unavailable = True
            print("[bmo-brain] pending recall endpoint absent (404) — disabling it for this "
                  "process; same-session recall stays covered by the local pending tier", flush=True)
            return []
        print(f"[bmo-brain] pending recall HTTP {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] pending recall failed: {e}", flush=True)
    return []


async def _store_memory(user_text: str, response_text: str, tool_trace: str = "", owner_id: str = ""):
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
    owner = owner_id or VAULT_OWNER
    if not (VAULT_URL and owner and user_text and response_text):
        return
    conversation = f"User: {user_text}\nBMO: {response_text}"
    if tool_trace:
        conversation += f"\n[Tool activity this exchange:\n{tool_trace}\n]"
    local_pending.queue_local(conversation, owner)
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            await c.post(f"{VAULT_URL}/v1/extract/queue",
                         json={"conversation": conversation,
                               "owner_id": owner,
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


async def _answer(client_messages, tools=None, model: str = ""):
    """Recall vault context, build the BMO prompt, call the LLM, return (text, tool_calls).

    `tools`, when supplied by the caller, is forwarded to Ollama verbatim (OpenAI-style
    function-calling schema) and any tool_calls are propagated back UNEXECUTED —
    passthrough mode, e.g. HA's "Control Home Assistant" feature, which owns entity
    resolution/execution/authorization itself. When the caller supplies no `tools`,
    bmo_brain offers its own tool set (tools.py) and executes any tool_calls itself,
    looping until the model produces a final text-only response — self-executing mode,
    e.g. the Pi driver, which has no way to execute a tool call itself. tool_calls in the
    return value is always None in self-executing mode.

    `model` is the caller-supplied model string (both API surfaces already read this from
    the request body for their own response envelope) — the ONLY per-request signal that
    can distinguish which node/satellite is talking to Friday today, since HA's chat
    request otherwise carries no device_id at all. Registering one Ollama-conversation-agent
    entry per Assist pipeline in HA, each naming a distinct model (see NODE_SPEAKER_MAP /
    /api/tags), lets that node's own co-located speaker resolve silently instead of
    clarifying on an unqualified "volume up". A model with no matching entry is a no-op.
    """
    set_current_node(model)
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
    if last_user:
        print(f"[bmo-brain] utterance: {last_user[:140]!r}", flush=True)

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

    # Bare media shortcut (see _bare_media_shortcut) — checked before anything else so it never
    # depends on the model attempting (and possibly not attempting) a tool call on its own. A
    # no-op unless this request has a configured node-default speaker (NODE_SPEAKER_MAP).
    bare_media_text = await _bare_media_shortcut(last_user)
    if bare_media_text:
        return bare_media_text, None

    # Brain swap: "Hey Friday, brain swap" toggles the LLM between the default and the experimental
    # model (see _BRAIN_SWAP_RE). The unload+warm runs in the background — the two 8B brains can't
    # co-reside on Friday's card — so this turn just flips _current_model and acks.
    if _BRAIN_SWAP_ENABLED and last_user and _BRAIN_SWAP_RE.search(last_user):
        global _current_model
        old, new = _current_model, (_ALT_BRAIN if _current_model == MODEL else MODEL)
        _current_model = new
        _t = asyncio.create_task(_do_brain_swap(old, new))
        _bg_tasks.add(_t)
        _t.add_done_callback(_bg_tasks.discard)
        print(f"[bmo-brain] brain swap: {old} -> {new}", flush=True)
        return _speechify(f"Okay, swapping to {_brain_name(new)}. Give me a moment while it loads."), None

    # Escalation consent gate (see _CONSULT_OFFERS). If the previous assistant turn offered a
    # Swarm/Claude consult and the user affirms THIS turn, route to the chosen (or default) backend —
    # the single call site — and short-circuit recall / the LLM / all tools for this turn. Gated on
    # _consult_backends() so it is a hard no-op unless at least one backend is armed (Swarm needs
    # AGENT_RUNTIME_URL; Claude is fail-closed on key + monthly budget). Neither backend is a model
    # tool, so the model can never reach here on its own — a real human affirmation is required.
    backends = _consult_backends()
    if backends:
        prev_assistant = next(
            (m.get("content") or "" for m in reversed(convo) if m.get("role") == "assistant"), "")
        if _ends_with_consult_offer(prev_assistant):
            reply = (last_user or "").lower()
            # Only treat THIS turn as an answer to the offer if it is a short reply OR explicitly names
            # a backend. Otherwise a fresh command that merely opens with filler ("okay, turn on the
            # lights") would be swallowed by the bare "okay"/"yes" match and misrouted into a consult,
            # dropping the real command. A genuine yes/no to a yes/no question is always short.
            is_answer = len(reply.split()) <= 5 or "swarm" in reply or "claude" in reply
            if is_answer and _CONSULT_DECLINE_RE.search(reply):
                return "Okay, I'll leave it.", None
            if is_answer and _CONSULT_AFFIRM_RE.search(reply):
                question = _pending_consult_question(convo)
                if not question:
                    return "Remind me what you wanted me to look into?", None
                choice = _chosen_backend(last_user, backends)
                if choice == "claude":
                    print(f"[bmo-brain] escalating to Claude on: {question[:120]!r}", flush=True)
                    consult = claude_consult.consult_claude(question)
                    who = "Claude"
                else:
                    print(f"[bmo-brain] escalating to the Swarm on: {question[:120]!r}", flush=True)
                    consult = delegate_to_swarm(await _with_location_context(question), mode=SWARM_HANDOFF_MODE)
                    who = "the Swarm"
                return await _dispatch_consult(consult, who)

    # Swarm-clarify answer: Friday recently asked a swarm-clarify question (via reopen) and parked the
    # original ask in _pending_clarify. THIS turn is the answer — fold it in and hand off — UNLESS it is
    # a fresh swarm command (a pivot; let the swarm-intent gate own it) or a short decline. Works whether
    # the user used the reopened mic or re-woke, as long as it is within the TTL.
    if (AGENT_RUNTIME_URL and last_user and _pending_clarify.get("original")
            and (time.time() - _pending_clarify.get("ts", 0)) < _CLARIFY_TTL
            and not _SWARM_INTENT_RE.search(last_user)):
        if _is_echo_of(last_user, _pending_clarify.get("question", "")):
            # Friday's own clarify question came back through the mic — don't treat it as the answer and
            # keep the pending ask armed. Return a SHORT nudge rather than "": an empty reply is exactly
            # what makes HA speak "unable to get response" (confirmed live), and it can't echo-loop
            # because it shares almost no words with the parked question.
            print(f"[bmo-brain] ignored mic echo of own clarify: {last_user[:80]!r}", flush=True)
            return "Go ahead whenever you're ready.", None
        if len(last_user.split()) <= 4 and _CONSULT_DECLINE_RE.search(last_user.lower()):
            _pending_clarify.clear()
            return "Okay, I'll hold off on that.", None
        original = _pending_clarify.get("original", "")
        _pending_clarify.clear()
        refined = await _with_location_context(f"{original}. Details from the user: {last_user}".strip())
        print(f"[bmo-brain] swarm handoff (clarified) on: {refined[:120]!r}", flush=True)
        return await _dispatch_consult(delegate_to_swarm(refined, mode=SWARM_HANDOFF_MODE), "the swarm")

    # Explicit "hand this off to the swarm" intent (voice path). See _SWARM_INTENT_RE. Runs AFTER the
    # consent gate (so a "yes, put the swarm on it" answering an offer is handled there first) and is
    # gated on the swarm being armed. A vague ask gets ONE local clarifying question first (Option A).
    if AGENT_RUNTIME_URL:
        swm = _SWARM_INTENT_RE.search(last_user or "")
        if swm:
            task = (last_user or "")[swm.end():].strip(" ,.:;-—")
            task = re.sub(r"^(?:to|on|about|for|with|regarding)\s+", "", task, flags=re.I).strip()
            if len(task.split()) < 3:
                # Bare handoff ("hand that off to the swarm") — the referent is the previous user turn.
                task = next((m.get("content") or "" for m in reversed(convo[:-1])
                             if m.get("role") == "user"), "")
            if not task:
                return "Sure — what would you like me to look into?", None
            raw_task = task  # the pre-location ask, parked verbatim if we need to clarify
            task = await _with_location_context(task)
            # Friday-side reasoning gate: too vague → ask ONE clarifying question SPOKEN AS THE REPLY.
            # NOT via reopen: this satellite has no echo cancellation, so reopening the mic makes it hear
            # Friday's own question and fold that back as the "answer" (confirmed live). And returning ""
            # makes HA say "unable to get response". So we speak the question normally and park the ask;
            # the user's re-woken answer folds in via the swarm-clarify answer gate above (within TTL).
            clarify = await _assess_swarm_task(task)
            if clarify:
                print(f"[bmo-brain] swarm-clarify on: {clarify[:120]!r}", flush=True)
                _pending_clarify.clear()
                _pending_clarify.update({"original": raw_task, "question": clarify, "ts": time.time()})
                return _speechify(clarify), None
            _pending_clarify.clear()
            print(f"[bmo-brain] direct swarm handoff on: {task[:120]!r}", flush=True)
            return await _dispatch_consult(delegate_to_swarm(task, mode=SWARM_HANDOFF_MODE), "the swarm")

    for m in convo:
        if m.get("role") == "tool":
            print(f"[bmo-brain] incoming tool result: {str(m.get('content'))[:300]!r}", flush=True)
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            print(f"[bmo-brain] incoming prior tool_calls: {m['tool_calls']}", flush=True)
    # Per-brain memory isolation: recall + store are keyed by the ACTIVE brain's owner_id, so the
    # default brain and the swapped-in alt brain never see each other's memories (zero bleed). The
    # base VAULT_OWNER stays on HA device-resolution (hass_resolver / _sanitize_hass_tool_calls) —
    # that is device sanitization, not memory, and must not be namespaced.
    mem_owner = _memory_owner(_current_model)
    local_mems = local_pending.search_local(last_user, mem_owner)
    # Run concurrently, not sequentially — otherwise a slow/unreachable vault costs
    # VAULT_TIMEOUT twice (once per call) instead of once, which would double worst-case
    # latency on every single request and defeat the point of the local-resilience tier.
    mems, pending_mems = await asyncio.gather(
        _vault_recall(last_user, mem_owner),
        _pending_recall(last_user, mem_owner),
    )
    pending_ctx_lines = [f"- Recent (may still be processing): {c}"
                         for c in (local_mems + pending_mems)]
    curated_ctx_lines = [f"- {c}" for c in mems]
    ctx_lines = pending_ctx_lines + curated_ctx_lines
    ctx = ("\n".join(ctx_lines)
           if ctx_lines else "(no specific vault memories matched this question)")
    parts = [_compose_persona(_current_model)]
    home = await _get_home_location()
    if home:
        parts.append(
            "USER'S LOCATION: home is " + home + ". When the user says 'near me', 'around here', "
            "'local', or asks about nearby weather, events, places, or businesses without naming a "
            "location, use THIS location — do not ask where they are.")
    _now = _local_now()
    parts.append(
        "CURRENT DATE & TIME (authoritative, as of this message): it is "
        + _now.strftime("%-I:%M %p") + " on " + _now.strftime("%A, %B %-d, %Y") + ". You ALREADY KNOW "
        "the current time, date, and day of week from this line — answer any such question directly and "
        "conversationally (say it in words, e.g. 'It's twenty past five'). Do NOT call get_current_time "
        "or get_current_date; the answer is right here, and calling a tool is slower and unnecessary.")
    _wx = _weather_for_prompt()
    if _wx:
        parts.append(
            "CURRENT LOCAL WEATHER (refreshed within the last few minutes): " + _wx + ". Answer "
            "questions about the current weather, temperature, or 'how's it out' directly from this — do "
            "NOT call get_current_weather. (For a multi-day forecast or a specific future time, you may "
            "still use the forecast/hourly tools.)")
    parts.append(
        "SPOKEN OUTPUT: you are talking out loud, not on a screen. NEVER read URLs, links, or "
        "'check [website] for details' — the user cannot click anything. When a tool returns data, "
        "SPEAK THE ACTUAL ANSWER (the numbers, facts, times, names), not where to find it. Keep it "
        "short and conversational — a sentence or two, not a list or an essay.")
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

    deterministic_media_text = None
    if tools and _trailing_media_state_failure(convo):
        deterministic_media_text = await _deterministic_media_fallback(convo)

    if deterministic_media_text:
        # See _deterministic_media_fallback's docstring: this specific case (HA's own media
        # intent STATE-failed on an implicit "the speaker" command, node default known) is
        # resolved in code rather than handed to the model — ahead of the clarify-threshold
        # check below, since it would otherwise fire on the 2nd consecutive failure before this
        # deterministic path ever got a chance.
        text, tool_calls = deterministic_media_text, None
    elif tools and tool_failures >= HASS_CLARIFY_THRESHOLD:
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
    elif tools and _MEDIA_INTENT_RE.search(last_user or "") and (
        not _ha_offers_media(tools) or _trailing_media_state_failure(convo)
    ):
        # Media intent AND (HA exposes no native media control, OR HA's native media intent just
        # failed on this exact target's playback STATE — see _trailing_media_state_failure) -> use
        # friday_brain's media tools (transport/volume/stream) as the fallback, executed via HA's
        # service API. The ordinary case (no native media at all) needs no nudge; the state-failure
        # case does, so the model doesn't just retry the doomed HA call again.
        text, tool_calls = await _passthrough_with_media(
            messages, tools, state_fallback=_ha_offers_media(tools))
    elif tools:
        # HA-driven turn. Offer friday_brain's read-only info tools (web_search + weather + news)
        # alongside HA's tools, executed locally, so live-info questions answer with REAL DATA instead
        # of deflecting/reading links; device commands still return to HA untouched. Sanitizing
        # happens inside the passthrough.
        text, tool_calls = await _passthrough_with_info(messages, tools)
    else:
        # Self-executing (Pi) path. Offer the base tool set, and add the registry WRITE tools
        # ONLY when the turn looks like a registry edit — the same gate the passthrough path uses,
        # so an ordinary self-executed command can't expose or misfire a destructive registry edit.
        self_tools = TOOL_SCHEMAS + (REGISTRY_TOOL_SCHEMAS
                                     if _REGISTRY_INTENT_RE.search(last_user or "") else [])
        text, tool_calls = await _self_execute_tools(messages, self_tools)

    empty_recovered = False
    escalated = False
    if not text and not tool_calls:
        # Empty answer — no text and no tool call. The usual cause is qwen3:8b emitting a blank
        # assistant turn (often right after a tool result it should have summarised). Retry ONCE
        # with tools withheld and an explicit nudge, forcing a spoken answer. The retry is silent —
        # a "let me try again" cannot span one HA turn — so the user simply hears the recovered
        # answer, or the varying failure + escalation offer below if it still comes up empty.
        retry_messages = [{"role": "system", "content": system + "\n\n" + _RETRY_NUDGE}] + convo
        try:
            text, _ = await _ollama_chat(retry_messages, tools=None)
        except Exception as e:  # noqa: BLE001
            print(f"[bmo-brain] empty-answer retry errored: {type(e).__name__}: {e}", flush=True)
            text = ""
        if text:
            empty_recovered = True
            print(f"[bmo-brain] recovered empty answer on retry ({len(text)} chars)", flush=True)
        else:
            escalated = True
            print("[bmo-brain] still empty after retry — surfacing failure + escalation offer", flush=True)
            text = _failure_with_consult_offer(convo)
        tool_calls = None
    print(f"[bmo-brain] memories={len(mems)} local_pending={len(local_mems)} "
          f"vault_pending={len(pending_mems)} status_probe={status_q} count_probe={count_q} "
          f"tool_failures={tool_failures} asked_for_clarity={asked_for_clarity} "
          f"tool_calls={len(tool_calls) if tool_calls else 0} answer_chars={len(text)}", flush=True)
    _log_interaction({
        "user": (last_user or "")[:1000],
        "response": (text or "")[:1500],
        "answer_chars": len(text),
        "tool_failures": tool_failures,
        "asked_for_clarity": asked_for_clarity,
        "tool_calls": len(tool_calls) if tool_calls else 0,
        "empty_recovered": empty_recovered,   # model returned blank but the silent retry saved it
        "escalated": escalated,               # blank even after retry -> failure + consult offer spoken
        "memories": len(mems),
        "had_tools": bool(tools),             # HA-driven turn (tools present) vs self-exec/Pi turn
        "status_q": status_q,
        "count_q": count_q,
    })
    # Status/count answers are point-in-time snapshots (current health, current total) —
    # storing them as vault "facts" makes them go stale immediately, and a wrong one
    # (e.g. a guessed memory count) becomes self-reinforcing: future recalls surface the
    # stale answer as ground truth and can cause it to be restated and stored again.
    if not status_q and not count_q:
        tool_trace = _build_tool_trace(convo) if (tool_failures or asked_for_clarity) else ""
        asyncio.create_task(_store_memory(last_user, text, tool_trace, owner_id=mem_owner))
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
        text, tool_calls = await _answer(client_messages, tools=tools, model=model)
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


def _tags_entry(name: str) -> dict:
    return {
        "name": f"{name}:latest", "model": f"{name}:latest",
        "modified_at": _now_iso(), "size": 0, "digest": "bmo",
        "details": {"parent_model": "", "format": "gguf", "family": "bmo",
                    "families": ["bmo"], "parameter_size": "8B", "quantization_level": ""},
    }


@app.get("/api/tags")
async def ollama_tags():
    # The base model plus one synthetic entry per NODE_SPEAKER_MAP key (see tools.py) — HA's Ollama
    # integration lets you register a separate conversation-agent entry per Assist pipeline, each
    # pointed at this same brain but naming a DIFFERENT model from this list. Selecting a node's own
    # entry is what identifies "this pipeline/satellite" on every request that entry makes (see
    # _answer()'s `model` param) — the only per-request signal Friday has for which node is talking,
    # since HA's chat request otherwise carries no device_id at all.
    return {"models": [_tags_entry(MODEL_NAME)] + [_tags_entry(node) for node in NODE_SPEAKER_MAP]}


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
        text, tool_calls = await _answer(messages, tools=tools, model=model)
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
