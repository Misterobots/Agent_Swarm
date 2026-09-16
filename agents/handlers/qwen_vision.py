"""Qwen-aware vision routing helpers.

The normal vision path remains backward compatible.  Qwen 3.8 is selected only
when the caller explicitly requests it or supplies a complete Qwen Team Builder
profile.  Every candidate is checked against the Ollama model inventory and its
declared capabilities before it is used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests
from providers.qwen_context import (
    QWEN_MODEL,
    QWEN_OUTPUT_RESERVE,
    decode_image_payload,
    ensure_context_headroom,
    estimate_messages_tokens,
    resolve_qwen_context,
)


QWEN_VISION_MODEL = "qwen3.8:27b"

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


def context_tokens(model: str, context_profile: str | None) -> tuple[str | None, int | None]:
    """Resolve context through the shared provider policy.

    Non-Qwen models deliberately return no Qwen profile or override so their
    existing provider options remain unchanged.
    """
    context = resolve_qwen_context(model, context_profile=context_profile, task_mode="vision")
    return context.context_profile, context.effective_context_tokens


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
        try:
            return decode_image_payload(value)
        except (ValueError, TypeError):
            continue
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
            def role_model(role: str) -> Any:
                role_value = normalized.get(role)
                if isinstance(role_value, Mapping):
                    for model_key in ("model", "model_id", "selected_model"):
                        if model_key in role_value:
                            return role_value[model_key]
                return role_value

            if required_roles.issubset(normalized) and all(
                role_model(role) == QWEN_VISION_MODEL for role in required_roles
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
    host_resolver: Callable[[str], str] | None = None,
) -> tuple[str | None, bool, str | None, str | None]:
    """Select Qwen when opted in, otherwise use verified legacy candidates."""
    requested = requested_qwen_model(ctx)
    candidates = ([QWEN_VISION_MODEL] if requested else []) + list(VISION_FALLBACKS)
    inventories: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        candidate_host = host_resolver(candidate) if host_resolver else host
        try:
            candidate_inventory = inventory if inventory is not None and candidate_host == host else inventories.get(candidate_host)
            if candidate_inventory is None:
                candidate_inventory = _model_inventory(candidate_host)
                inventories[candidate_host] = candidate_inventory
        except (requests.RequestException, ValueError, TypeError):
            continue
        if model_supports_vision(candidate_host, candidate, candidate_inventory):
            # A normal non-Qwen request is ordinary vision, not a Qwen fallback.
            fallback = bool(requested and candidate != requested)
            return candidate, fallback, requested, candidate_host
    return None, False, requested, None


def build_vision_payload(
    model: str, prompt: str, image_data: str, tokens: int | None
) -> dict[str, Any]:
    """Build the native Ollama image request with bounded Qwen output."""
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_data],
        "stream": False,
    }
    if tokens is not None:
        payload["options"] = {
            "num_ctx": tokens,
            "num_predict": QWEN_OUTPUT_RESERVE,
        }
    return payload


def validate_vision_headroom(
    model: str, prompt: str, image_data: str, effective_tokens: int | None
) -> None:
    """Fail closed for Qwen image requests before acquiring the GPU lease."""
    if model != QWEN_MODEL or effective_tokens is None:
        return
    input_tokens = estimate_messages_tokens(
        [{"role": "user", "content": prompt, "images": [image_data]}]
    )
    ensure_context_headroom(
        input_tokens=input_tokens,
        output_tokens=QWEN_OUTPUT_RESERVE,
        tool_tokens=0,
        effective_tokens=effective_tokens,
    )
