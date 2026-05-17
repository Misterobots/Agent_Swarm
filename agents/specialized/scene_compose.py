"""Scene Composition orchestrator.

Decomposes a long narrative scene description into:
  - one establishing-shot prompt (FLUX dev generates the empty scene)
  - N character hero-shot prompts (FLUX dev generates each character portrait)
and then composes all of them into a single coherent image via OmniGen2.

UX model (per design discussion):
  1. User submits a complex prompt
  2. Ollama decomposes it → returns {establishing_shot, characters: [...]}
  3. Parent job spawns N+1 child image gens through the existing /v1/art/generate/image
     machinery (with the swarm-panel-style card grid in the UI)
  4. User can regenerate or approve each card
  5. When all cards approved → trigger OmniGen2 /compose with the approved set
  6. Final composite delivered to gallery

Status: scaffold. The Ollama decomposer and the OmniGen2 HTTP wrapper are
sketched but not yet integration-tested.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from logger_setup import setup_logger

logger = setup_logger("SceneCompose")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OMNIGEN_HOST = os.getenv("OMNIGEN_HOST", "http://omnigen_service:8190")
SCENE_DECOMPOSE_MODEL = os.getenv("SCENE_DECOMPOSE_MODEL", "qwen2.5-coder:14b")

# Complexity trigger: longer than this AND mentions 2+ named subjects → decompose.
SCENE_COMPLEX_CHARS = 1800
SCENE_MAX_CHARACTERS = 6  # hard cap to keep child job count bounded

_DECOMPOSE_SYSTEM = (
    "You decompose long narrative scene descriptions into a structured JSON "
    "object suitable for generating image assets that will later be composited.\n\n"
    "Output schema (and ONLY this JSON, no preamble, no markdown):\n"
    "{\n"
    '  "establishing_shot": "<a single FLUX-friendly prompt for the empty scene: '
    'setting, lighting, atmosphere, color palette — NO characters>",\n'
    '  "characters": [\n'
    '    {"name": "<short label>", "prompt": "<single hero-shot prompt: '
    "appearance, costume, pose, expression, lighting matching the scene — "
    'no other characters mentioned>"},\n'
    "    ...\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Each prompt is 80-150 tokens, visual-noun-heavy, FLUX-friendly.\n"
    "- Drop quoted dialogue, abstract mood adjectives, and meta instructions.\n"
    "- Each character prompt is portrait-framing (3/4 body or closer), one subject only.\n"
    "- Establishing shot has no characters in it.\n"
    "- Max 6 characters; if the source mentions more, pick the most narratively important."
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CharacterPrompt:
    name: str
    prompt: str


@dataclass
class SceneDecomposition:
    establishing_shot: str
    characters: list[CharacterPrompt] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Decomposer
# ---------------------------------------------------------------------------

def is_complex_scene(prompt: str) -> bool:
    """Heuristic: long AND contains multiple character-introduction markers.
    Cheap pre-check before paying the Ollama tax."""
    if len(prompt) < SCENE_COMPLEX_CHARS:
        return False
    # Crude "names a character" detector — strings like "The Decker", "The Mage",
    # "Character Name:", or multiple capitalized name-followed-by-colon patterns.
    markers = sum(1 for m in ("The ", ": A ", ": A lean", ": A tall", ": A burly", ": A towering") if m in prompt)
    return markers >= 2


def decompose_scene(prompt: str) -> Optional[SceneDecomposition]:
    """Call Ollama to split a complex prompt into establishing shot + N hero shots.
    Returns None on any failure — caller falls back to single-image generation."""
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": SCENE_DECOMPOSE_MODEL,
                "system": _DECOMPOSE_SYSTEM,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Ollama JSON-mode forces valid JSON output
                # num_predict=800 covers the expected JSON output (~500-700 tokens)
                # without making the model run to completion for verbose ramble.
                "options": {"temperature": 0.2, "num_predict": 800, "keep_alive": "1h"},
            },
            # 240s: a long FLUX-narrative prompt (~3000 chars) is ~750 tokens of input;
            # qwen2.5-coder:14b at ~25 tok/s needs ~30s for output + prefill time.
            # 120s was too tight when the prompt hit the prefill phase.
            timeout=240,
        )
        if resp.status_code != 200:
            logger.warning(f"[SceneCompose] decompose HTTP {resp.status_code}")
            return None
        raw = (resp.json().get("response") or "").strip()
        data = json.loads(raw)
        chars = [
            CharacterPrompt(name=c["name"], prompt=c["prompt"])
            for c in (data.get("characters") or [])[:SCENE_MAX_CHARACTERS]
        ]
        decomp = SceneDecomposition(
            establishing_shot=data.get("establishing_shot", "").strip(),
            characters=chars,
        )
        logger.info(
            f"[SceneCompose] Decomposed into 1 establishing shot + {len(decomp.characters)} characters"
        )
        return decomp
    except Exception as e:
        logger.warning(f"[SceneCompose] decompose failed: {e}")
        return None


# ---------------------------------------------------------------------------
# OmniGen2 HTTP wrapper
# ---------------------------------------------------------------------------

def _read_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def compose_via_omnigen(
    scene_prompt: str,
    character_image_paths: list[tuple[str, str]],  # [(name, path), ...]
    establishing_shot_path: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 50,
    guidance_scale: float = 3.0,
    seed: int = -1,
    output_dir: str = "/tmp/comfyui_images",
) -> Optional[str]:
    """POST to OmniGen2 /compose with all references. Returns saved filename or None."""
    refs = []
    for name, path in character_image_paths:
        refs.append({"role": "character", "name": name, "image_b64": _read_image_b64(path)})
    if establishing_shot_path:
        refs.append({"role": "establishing_shot", "image_b64": _read_image_b64(establishing_shot_path)})

    try:
        resp = requests.post(
            f"{OMNIGEN_HOST}/compose",
            json={
                "scene_prompt": scene_prompt,
                "reference_images": refs,
                "width": width,
                "height": height,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "seed": seed,
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[SceneCompose] OmniGen2 compose request failed: {e}")
        return None

    filename = data.get("filename")
    img_b64 = data.get("image_b64")
    if not filename or not img_b64:
        logger.error("[SceneCompose] Compose response missing filename or image_b64")
        return None

    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, filename)
    with open(dest, "wb") as f:
        f.write(base64.b64decode(img_b64))
    logger.info(f"[SceneCompose] Saved composite {filename} in {data.get('elapsed', 0):.1f}s")
    return filename


# ---------------------------------------------------------------------------
# Parent-job state machine (skeleton)
# ---------------------------------------------------------------------------
# The actual job storage hooks into _art_job_create / _art_job_finish in main.py.
# We keep this module pure (no FastAPI imports) so it can be unit-tested.

@dataclass
class CardState:
    card_id: str
    role: str              # "establishing_shot" or "character"
    name: str              # "Decker" / "Rigger" / "scene"
    prompt: str            # the FLUX-bound prompt for this card
    child_job_id: Optional[str] = None
    image_path: Optional[str] = None
    status: str = "pending"   # pending → generating → ready → approved | rejected
    seed: int = -1


@dataclass
class SceneJob:
    parent_job_id: str
    user_prompt: str
    cards: list[CardState] = field(default_factory=list)
    engine: str = "omnigen"  # "omnigen" | "flux-inpaint" (future)
    state: str = "decomposing"  # decomposing → generating → awaiting_approval → composing → done | error
    composite_path: Optional[str] = None


def build_scene_job(parent_job_id: str, user_prompt: str, decomp: SceneDecomposition) -> SceneJob:
    """Build a SceneJob from a decomposition. Caller is responsible for
    persisting it (Redis hash, in-memory dict, whatever main.py uses for the
    existing art jobs)."""
    import uuid
    cards: list[CardState] = []
    cards.append(CardState(
        card_id=uuid.uuid4().hex[:8],
        role="establishing_shot",
        name="scene",
        prompt=decomp.establishing_shot,
    ))
    for c in decomp.characters:
        cards.append(CardState(
            card_id=uuid.uuid4().hex[:8],
            role="character",
            name=c.name,
            prompt=c.prompt,
        ))
    return SceneJob(parent_job_id=parent_job_id, user_prompt=user_prompt, cards=cards)
