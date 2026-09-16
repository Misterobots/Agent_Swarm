"""Context policy for the local Qwen 3.8 provider.

The policy is deliberately provider-local.  Other Ollama models continue to
use the existing per-model configuration until the integration lead wires the
request profile through the shared API and run context.
"""

from __future__ import annotations

from dataclasses import dataclass


QWEN_MODEL = "qwen3.8:27b"
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
