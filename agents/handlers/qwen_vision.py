"""Qwen-aware vision routing helpers.

The normal vision path remains backward compatible.  Qwen 3.8 is selected only
when the caller explicitly requests it or supplies a complete Qwen Team Builder
profile.  Every candidate is checked against the Ollama model inventory and its
declared capabilities before it is used.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, Mapping

import requests


QWEN_VISION_MODEL = "qwen3.8:27b"
CONTEXT_TOKENS = {
    "chat": 32768,
    "project": 65536,
    "long": 122880,
}

# Preserve the established lightweight order.  Each model still has to pass
# both the tag and capability checks before it becomes a fallback.
VISION_FALLBACKS = (
    "minicpm-v:latest",
    "llava:13b",
    "llava:7b",
    "llava:latest",
    "moondream:latest",
)

_DATA_URI_RE = re.compile(
    r"data:image/(?P<media>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\r\n]+)"
)
_RAW_IMAGE_RE = re.compile(r"^(?:/9j/|iVBOR)")


@dataclass(frozen=True)
class VisionSelection:
    requested_model: str | None
    actual_model: str
    host: str
    fallback: bool
    context_profile: str
    effective_context_tokens: int


def context_tokens(context_profile: str | None) -> tuple[str, int]:
    """Return the validated profile and token budget for a vision request."""
    profile = context_profile or "chat"
    if profile not in CONTEXT_TOKENS:
        raise ValueError(
            f"Invalid context profile {profile!r}; expected chat, project, or long."
        )
    return profile, CONTEXT_TOKENS[profile]


def extract_image_data(extracted_context: str, attachments: Any = None) -> str | None:
    """Extract one valid base64 image from the existing attachment plumbing."""
    candidates: list[str] = []
    if isinstance(attachments, (list, tuple)):
        for attachment in attachments:
            if isinstance(attachment, str):
                candidates.append(attachment)
            elif isinstance(attachment, Mapping):
                for key in ("data", "data_uri", "content", "url"):
                    value = attachment.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
                        break
    if isinstance(extracted_context, str):
        candidates.extend(match.group(0) for match in _DATA_URI_RE.finditer(extracted_context))
        stripped = extracted_context.strip()
        if _RAW_IMAGE_RE.match(stripped):
            candidates.append(stripped)

    for candidate in candidates:
        value = candidate.strip()
        match = _DATA_URI_RE.fullmatch(value)
        encoded = match.group("data") if match else value
        if not _RAW_IMAGE_RE.match(encoded):
            # Raw data is allowed only for the two formats already supported by
            # the legacy handler.  Other text must never become an image payload.
            if not match:
                continue
        try:
            base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            continue
        return encoded
    return None


def requested_qwen_model(ctx: Mapping[str, Any]) -> str | None:
    """Resolve explicit Qwen selection or a complete saved Qwen role profile."""
    for key in ("requested_model", "selected_model", "model"):
        value = ctx.get(key)
        if value == QWEN_VISION_MODEL:
            return QWEN_VISION_MODEL

    required_roles = {
        "coordinator", "architect", "coder", "devops",
        "researcher", "analyst", "verifier",
    }

    def contains_complete_profile(value: Any) -> bool:
        if isinstance(value, Mapping):
            normalized = {str(k).lower(): v for k, v in value.items()}
            if required_roles.issubset(normalized) and all(
                normalized[role] == QWEN_VISION_MODEL for role in required_roles
            ):
                return True
            return any(contains_complete_profile(child) for child in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_complete_profile(child) for child in value)
        return False

    for key in ("team_config", "saved_profile", "role_models", "profile", "team"):
        if contains_complete_profile(ctx.get(key)):
            return QWEN_VISION_MODEL
    return None


def _model_inventory(host: str, timeout: float = 3.0) -> dict[str, dict[str, Any]]:
    response = requests.get(f"{host}/api/tags", timeout=timeout)
    response.raise_for_status()
    models = response.json().get("models", [])
    return {
        model.get("name", ""): model
        for model in models
        if isinstance(model, Mapping) and model.get("name")
    }


def model_supports_vision(host: str, model: str, inventory: Mapping[str, Any] | None = None) -> bool:
    """Require an installed exact tag and Ollama's explicit vision capability."""
    try:
        inventory = inventory if inventory is not None else _model_inventory(host)
        if model not in inventory:
            return False
        response = requests.post(
            f"{host}/api/show", json={"name": model}, timeout=3.0
        )
        if response.status_code != 200:
            return False
        capabilities = response.json().get("capabilities", [])
        if isinstance(capabilities, list) and "vision" in capabilities:
            return True
        # Some Ollama versions place capabilities under details.
        details = response.json().get("details", {})
        return isinstance(details, Mapping) and "vision" in details.get("capabilities", [])
    except (requests.RequestException, ValueError, TypeError):
        return False


def select_vision_model(
    host: str,
    ctx: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any] | None = None,
) -> tuple[str | None, bool, str | None]:
    """Select Qwen when opted in, otherwise use verified legacy candidates."""
    requested = requested_qwen_model(ctx)
    try:
        inventory = inventory if inventory is not None else _model_inventory(host)
    except (requests.RequestException, ValueError, TypeError):
        return None, False, requested

    candidates = ([QWEN_VISION_MODEL] if requested else []) + list(VISION_FALLBACKS)
    for candidate in candidates:
        if model_supports_vision(host, candidate, inventory):
            return candidate, candidate != requested, requested
    return None, False, requested


def build_vision_payload(model: str, prompt: str, image_data: str, tokens: int) -> dict[str, Any]:
    """Build the native Ollama image request, including the context budget."""
    return {
        "model": model,
        "prompt": prompt,
        "images": [image_data],
        "stream": False,
        "options": {"num_ctx": tokens},
    }
