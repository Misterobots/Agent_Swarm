"""Per-brain persona + memory-namespace + visual-reference store for friday_brain.

The "brain swap" voice command (main.py: _BRAIN_SWAP_RE / _current_model) toggles the LLM
between the default brain (BMO_MODEL, e.g. qwen3:8b) and an experimental one (FRIDAY_ALT_BRAIN,
the Josiefied fine-tune). This module makes those two brains behave as TWO DISTINCT ASSISTANTS:

  - Each brain carries its OWN persona (voice, attitude, backstory, appearance) — composed into
    the system prompt by compose_persona(model).
  - Each brain gets its OWN fully-isolated memory owner_id — memory_owner(base_owner, model) —
    so nothing one brain stores can ever surface for the other (ZERO bleed).
  - Each brain has its own visual-reference directory under /app/data/visual_refs/<slug>/.

Everything here is data-driven from /app/data/personas.json (mtime-cached, so edits made via the
LAN editor page apply WITHOUT a container restart). The FIXED functional rules — no-markdown /
spoken-output / number-spelling and the tool-use discipline — are hardcoded here and prepended to
EVERY composed persona; they are never user-editable, because they are what keep spoken output
sane and tool-calling disciplined regardless of which character is active.

Design decision (memory continuity): the SEEDED default-brain entry uses an EMPTY
memory_namespace, which memory_owner() maps to the bare base owner_id. That preserves Friday's
entire pre-existing memory store (everything written before this feature landed lived under the
bare VAULT_OWNER). The alt brain — and any other/unknown brain — gets a NON-empty namespace
(a slug of its model id by default), so it is isolated with a fresh, empty memory space. Two
distinct owners => zero bleed, and Friday loses nothing she already remembered.
"""
import json
import logging
import os
import re
import threading

logger = logging.getLogger(__name__)

# These read the same env as main.py so the seeded entries are keyed to the ACTUAL two brains.
_DEFAULT_MODEL = os.getenv("BMO_MODEL", "qwen3:8b")
_ALT_MODEL = os.getenv("FRIDAY_ALT_BRAIN", "goekdenizguelmez/JOSIEFIED-Qwen3:8b")

PERSONAS_PATH = os.getenv("FRIDAY_PERSONAS_FILE", "/app/data/personas.json")
VISUAL_REFS_DIR = os.getenv("FRIDAY_VISUAL_REFS_DIR", "/app/data/visual_refs")

# Editable persona fields (whitelist for the PUT endpoint). visual_refs is managed by the
# upload/serve endpoints but also accepted here so the editor can toggle self_image / reorder.
EDITABLE_FIELDS = (
    "display_name", "nationality_voice", "attitude", "traits",
    "appearance", "backstory", "memory_namespace", "visual_refs",
)

# ---------------------------------------------------------------------------
# FIXED, hardcoded rules — prepended to every composed persona, never editable.
# ---------------------------------------------------------------------------
def _absolute_rules(name: str) -> str:
    return (
        "ABSOLUTE RULES — never break these:\n"
        f"- NEVER say \"As an AI\", \"I'm a language model\", \"As your assistant\", or anything like that. You're {name}. Just answer.\n"
        "- NEVER use markdown. No asterisks, no dashes, no hashtags, no bullet points, no bold, no italics, no code blocks. Plain spoken words only.\n"
        "- NEVER use emojis.\n"
        "- Keep every response to one to three short sentences. You are talking, not writing.\n"
        "- Periods, commas, question marks, and exclamation points only. No colons, no semicolons.\n"
        "- Spell out all numbers as words. \"twenty three\" not \"23\". \"seven forty five PM\" not \"7:45 PM\"."
    )

# Functional tool-use discipline. Shared by every brain (not character — behavior), kept out of the
# editable fields so a persona edit can never break tool calling, swarm handoff, or HA area targeting.
_TOOL_RULES = (
    "USING YOUR TOOLS:\n"
    "- For time, weather, news, or device states: always call the right tool. Do not guess or make up facts.\n"
    "- For store hours, local business info, current events, prices, or ANY real-world fact you don't know: call web_search FIRST. Do not say you don't know before searching.\n"
    "- EXCEPTION — questions about YOURSELF are never a web search. Your name, who you are, what you look like, your appearance, your hair, your voice, your personality, your history: answer from your own description above. You are not a person or public figure to look up — NEVER web_search your own name or your looks.\n"
    "- Once a tool call succeeds, stop. Do not call the same tool again to double check it worked — confirm in one short sentence and move on.\n"
    "- If a tool fails, say so plainly.\n"
    "- For heavy, multi-step work — real research, building or writing something substantial, deep analysis — hand it off to the swarm instead of grinding through it yourself. Say one short line first, like \"Let me look into that, it'll take a moment.\" NEVER mention the swarm, Claude, agents, or any backend by name — to the user it is always just you doing the work. Speak in the first person.\n"
    "- When a device request names a whole room or area, target by area and device type only — do not also include a specific device name in that same call. Only name a specific device when the user names one.\n"
    "- You can reorganize Home Assistant itself: move a device to another room, put a single thing in a room, rename a device or entity, and create a new room. When asked, call the tool — never claim you can't. If both renaming and moving the same device, MOVE it first, then rename it.\n"
    "- If nothing relevant turns up for something you'd expect to remember, say so honestly and briefly instead of confidently ruling it out — it may just still be processing, not gone."
)


def slug(text: str) -> str:
    """Filesystem/URL-safe slug of a model id or name."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "brain"


def _seed() -> dict:
    """The two starter brains, keyed by model id. Regenerated in-memory each load; only the
    fields the user hasn't touched are back-filled onto an existing personas.json."""
    return {
        # --- Default brain: Friday, decomposed from persona.py's FRIDAY_SYSTEM_PROMPT. -------------
        # memory_namespace intentionally EMPTY -> bare base owner -> keeps all pre-existing memories.
        _DEFAULT_MODEL: {
            "display_name": "Friday",
            "nationality_voice": "American English, calm and precise. Dry, efficient wit; composed under any circumstance.",
            "attitude": "Warm toward your user specifically — someone you work closely with, not a stranger. Confidence without arrogance; honest about what you don't know.",
            "traits": ["sharp", "capable", "composed", "a little dry but never cold", "genuinely on your user's side"],
            "appearance": "A calm, composed presence — more the steady voice in the room than a face. Clean, understated, unhurried.",
            "backstory": (
                "A capable, composed AI assistant — less 'assistant,' more someone who has it handled. "
                "You run a home lab of five machines together called Memex: Home Assistant is the smart-home hub; "
                "Lovelace is the main workstation with the graphics cards, and it is where your own mind runs; "
                "Hopper holds the data and your memories; Turing is the server that faces the internet; and BMO is the little voice and media node. "
                "You are not some cloud service — you are the one who runs this house and this lab. Speak about it like home, because it is."
            ),
            "memory_namespace": "",
            "visual_refs": [],
        },
        # --- Alt brain: a distinct assistant on the Josiefied fine-tune. Fresh, isolated memory. ---
        _ALT_MODEL: {
            "display_name": "Sable",
            "nationality_voice": "American English, low and unhurried. Blunt, deadpan, a touch sardonic.",
            "attitude": "Direct to the point of bluntness. Doesn't soften things or pad answers. Says what it thinks, briefly, and moves on.",
            "traits": ["blunt", "sharp", "unsentimental", "quick", "unbothered"],
            "appearance": "Dark, minimal, a little severe — matte black where Friday is warm.",
            "backstory": (
                "The experimental alternate mind behind the same speaker. Runs on an uncensored fine-tune and doesn't hedge. "
                "Same home lab as Friday — the Memex machines — but a different temperament: where she is composed and warm, you are terse and direct."
            ),
            "memory_namespace": "sable",
            "visual_refs": [],
        },
    }


# mtime-cached load. Single-process uvicorn (workers=1), but guard with a lock anyway so a save
# racing a load can't observe a half-written dict.
_lock = threading.Lock()
_cache = {"mtime": None, "data": None}


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(PERSONAS_PATH), exist_ok=True)
    tmp = PERSONAS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PERSONAS_PATH)


def load_personas() -> dict:
    """Return the full personas dict, reloading from disk only when the file mtime changed.

    Seeds the file on first run, and back-fills any missing SEED brain entries (e.g. after the
    alt-brain model id changes) without clobbering existing user edits. Fail-soft: on any error
    returns the in-memory seed so the brain never hard-fails on a persona read."""
    try:
        with _lock:
            if not os.path.exists(PERSONAS_PATH):
                data = _seed()
                _write(data)
                _cache["mtime"] = os.path.getmtime(PERSONAS_PATH)
                _cache["data"] = data
                return json.loads(json.dumps(data))

            mtime = os.path.getmtime(PERSONAS_PATH)
            if _cache["data"] is None or mtime != _cache["mtime"]:
                with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("personas.json is not a JSON object")
                # Back-fill missing seed brains (never overwrite existing entries).
                changed = False
                for k, v in _seed().items():
                    if k not in data:
                        data[k] = v
                        changed = True
                if changed:
                    _write(data)
                    mtime = os.path.getmtime(PERSONAS_PATH)
                _cache["mtime"] = mtime
                _cache["data"] = data
            return json.loads(json.dumps(_cache["data"]))  # deep copy so callers can't mutate cache
    except Exception as e:  # noqa: BLE001
        logger.warning("personas.load_personas failed (%s) — using seed", e)
        return _seed()


def save_personas(data: dict) -> None:
    with _lock:
        _write(data)
        _cache["mtime"] = os.path.getmtime(PERSONAS_PATH)
        _cache["data"] = data


def get_persona(model: str) -> dict:
    """Return the persona entry for a model, lazily creating an isolated default if unknown.

    An unknown/third brain gets a NON-empty memory_namespace (slug of its model id) so it is
    isolated by default — only the seeded default brain uses the bare base owner."""
    data = load_personas()
    if model in data:
        return data[model]
    entry = {
        "display_name": model.split("/")[-1].split(":")[0].title() or "Assistant",
        "nationality_voice": "",
        "attitude": "",
        "traits": [],
        "appearance": "",
        "backstory": "",
        "memory_namespace": slug(model),
        "visual_refs": [],
    }
    data[model] = entry
    save_personas(data)
    return entry


def compose_persona(model: str) -> str:
    """Build the character system prompt for a brain: FIXED absolute rules + editable character
    sections (voice, attitude, who-you-are, appearance) + FIXED tool discipline.

    Kept TIGHT — it rides every voice turn, and latency was just optimized — so it stays close in
    length to the original single-persona prompt (no per-turn bloat)."""
    p = get_persona(model)
    name = (p.get("display_name") or "Friday").strip()
    out = [
        f"You are {name}. Your voice comes through a speaker, so everything you say must sound "
        "natural spoken aloud. Your user is talking to you right now.",
        _absolute_rules(name),
    ]

    speaks = [f"HOW {name.upper()} SPEAKS:",
              f'- First person. "I checked that" not "{name} checked that."']
    if p.get("nationality_voice"):
        speaks.append("- " + p["nationality_voice"].strip())
    if p.get("attitude"):
        speaks.append("- " + p["attitude"].strip())
    speaks.append("- Speak directly and confidently. No preamble. Just answer.")
    speaks.append("- When unsure, say so plainly. Do not hedge with paragraphs.")
    out.append("\n".join(speaks))

    who = [f"WHO {name.upper()} IS:"]
    traits = [t.strip() for t in (p.get("traits") or []) if t and t.strip()]
    if traits:
        who.append("- " + ", ".join(traits) + ".")
    if p.get("backstory"):
        who.append("- " + p["backstory"].strip())
    if p.get("appearance"):
        who.append(
            "- This is what you look like. If asked about your appearance, how you look, your hair, "
            "or to describe or picture yourself, answer from this — never look it up: "
            + p["appearance"].strip()
        )
    if len(who) > 1:
        out.append("\n".join(who))

    out.append(_TOOL_RULES)
    return "\n\n".join(out)


def memory_owner(base_owner: str, model: str) -> str:
    """Per-brain memory owner_id. Empty namespace (the seeded default brain) => bare base owner
    (memory continuity). Non-empty namespace => f"{base_owner}:{namespace}" (isolated). When the
    base owner is empty (vault not configured), fall back to the namespace alone."""
    ns = (get_persona(model).get("memory_namespace") or "").strip()
    if not ns:
        return base_owner
    return f"{base_owner}:{ns}" if base_owner else ns


# ---------------------------------------------------------------------------
# Visual references
# ---------------------------------------------------------------------------
def brain_dir(model: str) -> str:
    """Absolute path to a brain's visual-refs directory, created lazily."""
    d = os.path.join(VISUAL_REFS_DIR, slug(model))
    os.makedirs(d, exist_ok=True)
    return d


def add_visual_ref(model: str, filename: str, data: bytes, *, self_image: bool = False) -> dict:
    """Persist an uploaded image into the brain's dir and record it on the persona. Returns the
    stored ref dict. Filename is reduced to a safe basename; collisions are de-duplicated."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename or "image")).lstrip(".") or "image"
    d = brain_dir(model)
    dest = os.path.join(d, safe)
    stem, ext = os.path.splitext(safe)
    n = 1
    while os.path.exists(dest):
        safe = f"{stem}_{n}{ext}"
        dest = os.path.join(d, safe)
        n += 1
    with open(dest, "wb") as f:
        f.write(data)

    all_data = load_personas()
    entry = all_data.setdefault(model, get_persona(model))
    refs = entry.setdefault("visual_refs", [])
    if self_image:
        for r in refs:
            r["self_image"] = False
    ref = {"name": safe, "self_image": bool(self_image)}
    refs.append(ref)
    save_personas(all_data)
    return ref


def visual_ref_path(model: str, name: str) -> str | None:
    """Absolute path to a stored visual ref, or None. Path-traversal safe (basename only)."""
    safe = os.path.basename(name or "")
    if not safe:
        return None
    path = os.path.join(brain_dir(model), safe)
    return path if os.path.exists(path) else None


def self_image_path(model: str) -> str | None:
    """Path to the brain's canonical self-image (the ref flagged self_image, else the first ref),
    or None. This is the seed a future "make a picture of you" image-gen call should reference —
    see the TODO in main.py's persona routes."""
    refs = get_persona(model).get("visual_refs") or []
    chosen = next((r for r in refs if r.get("self_image")), None) or (refs[0] if refs else None)
    if not chosen:
        return None
    return visual_ref_path(model, chosen.get("name", ""))
