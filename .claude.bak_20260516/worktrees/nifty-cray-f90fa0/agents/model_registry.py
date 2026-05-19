"""
model_registry.py — Centralized model catalog for the Agent Swarm.

Single source of truth for:
- Available Ollama models and their VRAM cost
- VRAM tier classification (SMALL ≤ LARGE_THRESHOLD: bypass queue | LARGE: queued)
- Capability profiles
- Intended roles per model
- Alternative model suggestions for queue-aware UX

VRAM Tiers (Lovelace: dual RTX 5060 Ti, 32 GB total):
  SMALL  ≤ 8 GB   — can coexist with any single large model, no queue
  LARGE  > 8 GB   — mutually exclusive at full size; require large-model queue
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Threshold that separates small (no-queue) from large (queued) models
# ─────────────────────────────────────────────────────────────────────────────
LARGE_MODEL_VRAM_THRESHOLD_GB: float = 8.0

# Rough model-load time from NVMe to VRAM (seconds).
# Used for ETA estimation only — real time depends on disk speed and model.
_LOAD_TIME_ESTIMATES: dict[str, int] = {
    "gemma4:31b":          20,
    "gemma4:26b":          18,
    "qwen3.6:27b":         15,
    "qwen3:14b":           12,
    "qwen2.5-coder:14b":   12,
    "qwen3:8b":             6,
    "qwen2.5-coder:7b":     5,
    "llama3.2:3b":          3,
    "nomic-embed-text:latest": 2,
}

# Average inference job duration (seconds) — used for queue ETA projection
AVG_INFERENCE_SECONDS: int = 25


@dataclass
class ModelSpec:
    name: str
    vram_gb: float
    capabilities: List[str]               # text, code, vision, reasoning, embedding
    roles: List[str]                      # valid team-builder roles
    description: str
    alternatives: List[str] = field(default_factory=list)   # faster/lighter options
    available: bool = True                # False = not pulled locally yet
    recommended_for_roles: List[str] = field(default_factory=list)  # top pick for these roles

    @property
    def tier(self) -> str:
        return "large" if self.vram_gb > LARGE_MODEL_VRAM_THRESHOLD_GB else "small"

    @property
    def is_large(self) -> bool:
        return self.tier == "large"

    @property
    def estimated_load_seconds(self) -> int:
        return _LOAD_TIME_ESTIMATES.get(self.name, 20)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "vram_gb": self.vram_gb,
            "tier": self.tier,
            "capabilities": self.capabilities,
            "roles": self.roles,
            "recommended_for_roles": self.recommended_for_roles,
            "description": self.description,
            "alternatives": self.alternatives,
            "available": self.available,
            "estimated_load_seconds": self.estimated_load_seconds,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Model Catalog
# ─────────────────────────────────────────────────────────────────────────────
_ALL_ROLES = [
    "coordinator", "architect", "coder", "devops",
    "researcher", "analyst", "verifier",
]

MODELS: dict[str, ModelSpec] = {
    # ── Frontier reasoning models (large, queued) ─────────────────────────
    "gemma4:31b": ModelSpec(
        name="gemma4:31b",
        vram_gb=20.0,
        capabilities=["text", "vision", "code", "reasoning"],
        roles=_ALL_ROLES,
        recommended_for_roles=["coordinator", "architect", "verifier"],
        description="Google Gemma 4 31B Dense — best reasoning & coding, 256K ctx, vision",
        alternatives=["gemma4:26b", "qwen3.6:27b"],
        available=False,   # updated at runtime by check_available()
    ),
    "gemma4:26b": ModelSpec(
        name="gemma4:26b",
        vram_gb=18.0,
        capabilities=["text", "vision", "code", "reasoning"],
        roles=_ALL_ROLES,
        recommended_for_roles=["researcher", "analyst"],
        description="Google Gemma 4 26B MoE — fast inference (3.8B active params), 256K ctx",
        alternatives=["qwen3.6:27b", "qwen3:14b"],
        available=False,
    ),
    "qwen3.6:27b": ModelSpec(
        name="qwen3.6:27b",
        vram_gb=17.4,
        capabilities=["text", "vision", "code", "reasoning"],
        roles=_ALL_ROLES,
        recommended_for_roles=["coordinator", "architect", "researcher"],
        description="Qwen 3.6 27B — hybrid attention, 256K ctx, vision. Current default.",
        alternatives=["gemma4:26b", "qwen3:14b"],
        available=True,
    ),
    "qwen3:14b": ModelSpec(
        name="qwen3:14b",
        vram_gb=9.3,
        capabilities=["text", "code", "reasoning"],
        roles=["architect", "coder", "researcher", "analyst", "devops", "verifier"],
        recommended_for_roles=["analyst"],
        description="Qwen 3 14B — strong reasoning & code, fits alongside large models",
        alternatives=["qwen3:8b", "qwen2.5-coder:14b"],
        available=True,
    ),
    "qwen2.5-coder:14b": ModelSpec(
        name="qwen2.5-coder:14b",
        vram_gb=9.0,
        capabilities=["code"],
        roles=["coder", "devops"],
        recommended_for_roles=["coder"],
        description="Qwen 2.5 Coder 14B — specialized code generation and review",
        alternatives=["qwen2.5-coder:7b", "qwen3:14b"],
        available=True,
    ),
    # ── Lightweight models (small, no queue) ──────────────────────────────
    "qwen3:8b": ModelSpec(
        name="qwen3:8b",
        vram_gb=5.2,
        capabilities=["text", "code"],
        roles=["coder", "researcher", "analyst"],
        recommended_for_roles=[],
        description="Qwen 3 8B — fast, no queue, good for simple tasks",
        alternatives=[],
        available=True,
    ),
    "qwen2.5-coder:7b": ModelSpec(
        name="qwen2.5-coder:7b",
        vram_gb=4.7,
        capabilities=["code"],
        roles=["coder", "devops"],
        recommended_for_roles=[],
        description="Qwen 2.5 Coder 7B — fast code, no queue",
        alternatives=[],
        available=True,
    ),
    "llama3.2:3b": ModelSpec(
        name="llama3.2:3b",
        vram_gb=2.0,
        capabilities=["text"],
        roles=[],    # internal: BMO voice only
        recommended_for_roles=[],
        description="Llama 3.2 3B — BMO voice agent (internal, not user-selectable)",
        alternatives=[],
        available=True,
    ),
    "nomic-embed-text:latest": ModelSpec(
        name="nomic-embed-text:latest",
        vram_gb=0.3,
        capabilities=["embedding"],
        roles=[],    # internal: memory/search only
        recommended_for_roles=[],
        description="Nomic Embed Text — embedding (internal, not user-selectable)",
        alternatives=[],
        available=True,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_model(name: str) -> Optional[ModelSpec]:
    """Return a ModelSpec by exact name, or None if unknown."""
    return MODELS.get(name)


def get_models_for_role(role: str) -> List[ModelSpec]:
    """Return all models that support the given role, sorted by VRAM desc."""
    return sorted(
        [m for m in MODELS.values() if role in m.roles and m.available],
        key=lambda m: m.vram_gb,
        reverse=True,
    )


def get_user_selectable_models() -> List[ModelSpec]:
    """Return models that users can assign in the team builder (have at least one role)."""
    return [m for m in MODELS.values() if m.roles and m.available]


def is_large_model(name: str) -> bool:
    """True if the model exceeds the small-model VRAM threshold."""
    spec = MODELS.get(name)
    return spec.is_large if spec else True   # fail-safe: assume large if unknown


def get_alternatives(name: str, only_available: bool = True) -> List[ModelSpec]:
    """Return alternative models for the given model name."""
    spec = MODELS.get(name)
    if not spec:
        return []
    alts = [MODELS[a] for a in spec.alternatives if a in MODELS]
    if only_available:
        alts = [a for a in alts if a.available]
    return alts


def validate_role_model(role: str, model_name: str) -> tuple[bool, str]:
    """
    Validate that a model is appropriate for a role.

    Returns:
        (is_valid, warning_message)
        is_valid is False only for hard incompatibilities (e.g. embedding model as coordinator).
        A warning may accompany a valid assignment (e.g. low-capability model for critical role).
    """
    spec = MODELS.get(model_name)
    if spec is None:
        return False, f"Model '{model_name}' is not in the registry."

    if not spec.available:
        return False, f"Model '{model_name}' is not downloaded yet. Pull it first."

    if not spec.roles:
        return False, (
            f"Model '{model_name}' is an internal model (embedding/voice) "
            "and cannot be assigned to a team role."
        )

    if role not in spec.roles:
        return False, (
            f"Model '{model_name}' does not support the '{role}' role. "
            f"Supported roles: {', '.join(spec.roles)}."
        )

    # Soft warnings for sub-optimal but valid assignments
    if role in ("coordinator", "architect", "verifier") and spec.tier == "small":
        return True, (
            f"Warning: '{model_name}' ({spec.vram_gb} GB) is a lightweight model. "
            f"Consider a larger reasoning model for the '{role}' role for best results."
        )

    return True, ""


def check_available(ollama_host: str = "http://localhost:11434") -> None:
    """
    Query Ollama /api/tags and update `available` flags in the registry.
    Call this at startup or on demand. Fail-safe: does nothing on error.
    """
    import requests
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if resp.status_code != 200:
            return
        pulled = {m["name"] for m in resp.json().get("models", [])}
        for name, spec in MODELS.items():
            spec.available = name in pulled
    except Exception:
        pass  # Fail-open: keep existing available flags


def estimate_queue_wait(model_name: str, queue_position: int) -> int:
    """
    Rough ETA in seconds for a queued large-model request.

    queue_position: number of requests ahead of this one (0 = at front).
    """
    spec = MODELS.get(model_name)
    load_time = spec.estimated_load_seconds if spec else 20
    return queue_position * AVG_INFERENCE_SECONDS + load_time
