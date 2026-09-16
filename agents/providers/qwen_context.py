"""Context policy for the local Qwen 3.8 provider.

The policy is deliberately provider-local.  Other Ollama models continue to
use the existing per-model configuration until the integration lead wires the
request profile through the shared API and run context.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
from io import BytesIO
import json
import math
import re
import warnings
from typing import Any


QWEN_MODEL = "qwen3.8:27b"
QWEN_OUTPUT_RESERVE = 4_096
# Ollama vision tokenization depends on the loaded model and image dimensions.
# This is an intentionally unverified safety allowance, not a tokenizer result.
QWEN_IMAGE_TOKEN_ALLOWANCE = 2_048
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_DIMENSION = 8_192
QWEN_CONTEXT_TOKENS = {
    "chat": 32_768,
    "project": 65_536,
    "long": 122_880,
}
_PROJECT_TASK_MODES = {"code", "coding", "project", "swarm"}


@dataclass(frozen=True)
class QwenContext:
    profile: str | None
    effective_tokens: int | None

    @property
    def context_profile(self) -> str | None:
        """Compatibility name used by request/run metadata."""
        return self.profile

    @property
    def effective_context_tokens(self) -> int | None:
        """Compatibility name used by request/run metadata."""
        return self.effective_tokens


def resolve_qwen_context(
    model: str,
    context_profile: str | None = None,
    *,
    task_mode: str = "chat",
) -> QwenContext:
    """Resolve a Qwen 3.8 task profile without changing other models.

    An omitted profile follows the request mode: code/project/swarm requests
    get the project budget and ordinary chat/vision requests get chat.  The
    long profile is always explicit so a large resident context is a visible
    caller choice.
    """
    if model != QWEN_MODEL:
        return QwenContext(profile=None, effective_tokens=None)

    if context_profile is not None:
        if context_profile not in QWEN_CONTEXT_TOKENS:
            allowed = ", ".join(QWEN_CONTEXT_TOKENS)
            raise ValueError(f"Invalid Qwen context profile {context_profile!r}; choose {allowed}")
        profile = context_profile
    else:
        profile = "project" if task_mode.strip().lower() in _PROJECT_TASK_MODES else "chat"

    return QwenContext(profile=profile, effective_tokens=QWEN_CONTEXT_TOKENS[profile])


def ensure_context_headroom(
    *,
    input_tokens: int,
    output_tokens: int,
    effective_tokens: int,
    tool_tokens: int = 0,
) -> None:
    """Reject a request that cannot fit input, tools, and output.

    Ollama will otherwise accept the request and truncate or evict context in
    provider-specific ways.  The shared layer may use this check after it has
    measured the serialized prompt and tool schema.
    """
    if min(input_tokens, output_tokens, tool_tokens) < 0:
        raise ValueError("Context token counts must be non-negative")
    required = input_tokens + tool_tokens + output_tokens
    if required > effective_tokens:
        raise ValueError(
            f"Context budget exceeded: input={input_tokens}, tools={tool_tokens}, "
            f"output={output_tokens}, limit={effective_tokens}"
        )


def estimate_serialized_tokens(value: Any) -> int:
    """Estimate text/schema tokens from serialized JSON, not a real tokenizer."""
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return max(1, math.ceil(len(serialized) / 4))


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate text plus a fixed image allowance without counting image bytes.

    The base64 image bytes are replaced with a marker before the wire-size
    estimate.  Each image then receives QWEN_IMAGE_TOKEN_ALLOWANCE.  The
    allowance is conservative policy, not verified Qwen/Ollama tokenization;
    the lead-owned tokenizer measurement must supersede this estimate when it
    is available.
    """
    sanitized: list[dict[str, Any]] = []
    image_count = 0
    for message in messages:
        copy = dict(message)
        images = copy.get("images")
        if isinstance(images, list):
            image_count += len(images)
            copy["images"] = ["<image>"] * len(images)
        content = copy.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    image_count += 1
                    parts.append({"type": "image_url", "image_url": {"url": "<image>"}})
                else:
                    parts.append(part)
            copy["content"] = parts
        sanitized.append(copy)
    return estimate_serialized_tokens(sanitized) + image_count * QWEN_IMAGE_TOKEN_ALLOWANCE


def decode_image_payload(value: str) -> str:
    """Validate and normalize one bounded Ollama image payload.

    Pillow performs the actual container/decompression validation.  The byte
    and dimension limits run before/around decode to prevent oversized or
    decompression-bomb inputs.  This function returns raw base64 for Ollama;
    it does not claim to calculate model image tokens.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("Ollama image payload must be non-empty base64")
    match = re.fullmatch(
        r"data:(?P<mime>image/(?:png|jpeg|jpg|webp|gif));base64,(?P<data>[A-Za-z0-9+/]*={0,2})",
        value,
    )
    encoded = match.group("data") if match else value
    if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", encoded):
        raise ValueError("Ollama image payload must be strict base64 or data:image/*")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ValueError("Ollama image payload contains invalid base64") from None
    if not decoded:
        raise ValueError("Ollama image payload must not be empty")
    if len(decoded) > MAX_IMAGE_BYTES:
        raise ValueError(f"Ollama image payload exceeds {MAX_IMAGE_BYTES} byte limit")

    try:
        from PIL import Image

        expected_formats = {
            "image/png": "PNG",
            "image/jpeg": "JPEG",
            "image/jpg": "JPEG",
            "image/gif": "GIF",
            "image/webp": "WEBP",
        }
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(decoded)) as image:
                if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
                    raise ValueError("Ollama image dimensions exceed safety limit")
                image_format = (image.format or "").upper()
                mime = match.group("mime") if match else None
                if mime and image_format != expected_formats[mime]:
                    raise ValueError("Ollama image MIME does not match decoded image")
                image.verify()
            # verify() checks the container; load() checks actual pixel decode.
            with Image.open(BytesIO(decoded)) as image:
                image.load()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Ollama image payload failed decode: {exc}") from None
    return encoded
