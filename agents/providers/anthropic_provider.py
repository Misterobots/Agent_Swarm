"""
Anthropic Claude provider adapter for the Hive.

Normalises Anthropic Messages API responses into the same streaming
interface the rest of the swarm expects (chunked dicts identical to
the format produced by the Ollama / phi path).

Admin-only:  The caller (router / mars_loop) is responsible for
checking security_level == L3_ADMIN before invoking this provider.
This module does NOT enforce access control itself.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator

logger = logging.getLogger("anthropic_provider")

# ---------------------------------------------------------------------------
# Lazy import – the 'anthropic' package is optional; if it isn't installed
# the module still loads but calls will raise a clear error.
# ---------------------------------------------------------------------------
_anthropic = None


def _ensure_sdk():
    global _anthropic
    if _anthropic is None:
        try:
            import anthropic as _a  # type: ignore[import-untyped]

            _anthropic = _a
        except ImportError:
            raise RuntimeError(
                "The 'anthropic' Python package is required for Claude models. "
                "Install it:  pip install anthropic"
            )
    return _anthropic


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
# Default to Claude Sonnet 4.6 — the current production Sonnet. Starting with
# the 4.6 generation Anthropic uses dateless IDs as pinned snapshots, so no
# date suffix here. The previous default ("claude-sonnet-4-6-20250514") was
# a Frankenstein ID — Sonnet 4.6 paired with Opus-4's date suffix — and
# would 404 against the live API.
ANTHROPIC_DEFAULT_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# If ANTHROPIC_MAX_TOKENS is explicitly set in the environment we honour it
# (operators may want a tighter cap for cost control). When unset, we DO NOT
# fall back to a single hardcoded value — instead each call uses the
# per-model max from SUPPORTED_MODELS so Sonnet 4.6 / Opus aren't silently
# truncated at 4096 tokens. See _resolve_max_tokens() below.
_ANTHROPIC_MAX_TOKENS_ENV: int | None = (
    int(os.environ["ANTHROPIC_MAX_TOKENS"])
    if os.environ.get("ANTHROPIC_MAX_TOKENS", "").strip()
    else None
)
# Conservative floor used only when we can't resolve a per-model max
# (e.g. caller passes an unknown model name).
_FALLBACK_MAX_TOKENS: int = 4096

# Verified against https://platform.claude.com/docs/en/docs/about-claude/models/overview
# Naming convention notes:
#   - Pre-4.6 generation: dated IDs ("claude-opus-4-1-20250805") + dateless aliases.
#   - 4.6 generation onward: dateless IDs that ARE the pinned snapshot
#     (e.g. "claude-sonnet-4-6", "claude-opus-4-7").
#   - Haiku 4.5 still uses the dated form ("claude-haiku-4-5-20251001").
# Legacy entries are kept so users with stored model preferences don't break;
# they'll continue to work until Anthropic's published retirement date.
SUPPORTED_MODELS: dict[str, dict[str, Any]] = {
    # ── Current generation ─────────────────────────────────────────────
    "claude-opus-4-7":             {"label": "Claude Opus 4.7",   "context": 1_000_000, "max_output": 128_000},
    "claude-sonnet-4-6":           {"label": "Claude Sonnet 4.6", "context": 1_000_000, "max_output": 64_000},
    "claude-haiku-4-5-20251001":   {"label": "Claude Haiku 4.5",  "context":   200_000, "max_output": 64_000},

    # ── Legacy / still serving ─────────────────────────────────────────
    "claude-opus-4-6":             {"label": "Claude Opus 4.6 (legacy)",   "context": 1_000_000, "max_output": 128_000},
    "claude-sonnet-4-5-20250929":  {"label": "Claude Sonnet 4.5 (legacy)", "context":   200_000, "max_output":  64_000},
    "claude-haiku-3-5-20241022":   {"label": "Claude Haiku 3.5 (legacy)",  "context":   200_000, "max_output":   8_192},

    # ── Deprecated; retires 2026-06-15 ────────────────────────────────
    "claude-opus-4-20250514":      {"label": "Claude Opus 4 (deprecated)", "context": 200_000, "max_output": 32_000},
    "claude-sonnet-4-20250514":    {"label": "Claude Sonnet 4 (deprecated)", "context": 200_000, "max_output": 64_000},
}


def _resolve_max_tokens(model: str, explicit: int | None) -> int:
    """Pick the right max_tokens value.

    Priority:
      1. explicit caller-supplied value (e.g. mars_loop wants a hard cap)
      2. ANTHROPIC_MAX_TOKENS env var, if operator set one
      3. SUPPORTED_MODELS[model]['max_output'] — the model's real ceiling
      4. _FALLBACK_MAX_TOKENS — last resort for unknown models
    """
    if explicit is not None:
        return explicit
    if _ANTHROPIC_MAX_TOKENS_ENV is not None:
        return _ANTHROPIC_MAX_TOKENS_ENV
    spec = SUPPORTED_MODELS.get(model)
    if spec and "max_output" in spec:
        return int(spec["max_output"])
    return _FALLBACK_MAX_TOKENS


# Back-compat alias — some call sites import this directly. Resolves to the
# default model's true max-output rather than a flat 4096.
ANTHROPIC_MAX_TOKENS: int = _resolve_max_tokens(ANTHROPIC_DEFAULT_MODEL, None)


def is_available() -> bool:
    """Return True when the SDK is importable and an API key is set."""
    try:
        _ensure_sdk()
    except RuntimeError:
        return False
    return bool(ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Normalised streaming chunk — matches the dict shape the SSE layer emits
# ---------------------------------------------------------------------------
@dataclass
class StreamChunk:
    """One piece of a streaming assistant response."""

    type: str = "content"  # "content" | "status" | "thought" | "tool_call"
    content: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_call_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "content": self.content}
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.tool_input is not None:
            d["tool_input"] = self.tool_input
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------
class AnthropicProvider:
    """Thin wrapper that presents the same generate() interface used by
    the Ollama code path so the rest of the swarm stays LLM-agnostic."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        sdk = _ensure_sdk()
        self._api_key = api_key or ANTHROPIC_API_KEY
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._model = model or ANTHROPIC_DEFAULT_MODEL
        self._client = sdk.Anthropic(api_key=self._api_key)

    # ------------------------------------------------------------------ #
    # Non-streaming
    # ------------------------------------------------------------------ #
    def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        messages: list[dict[str, str]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Blocking call — returns the full assistant text."""
        api_messages = self._build_messages(prompt, messages)
        kwargs = self._base_kwargs(system, api_messages, tools, max_tokens, temperature)
        response = self._client.messages.create(**kwargs)
        return self._extract_text(response)

    # ------------------------------------------------------------------ #
    # Streaming
    # ------------------------------------------------------------------ #
    def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        messages: list[dict[str, str]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> Generator[StreamChunk, None, None]:
        """Yields StreamChunk objects as the model streams its response."""
        api_messages = self._build_messages(prompt, messages)
        kwargs = self._base_kwargs(system, api_messages, tools, max_tokens, temperature)

        with self._client.messages.stream(**kwargs) as stream:
            current_tool_name: str | None = None
            current_tool_id: str | None = None
            tool_input_json = ""

            for event in stream:
                event_type = getattr(event, "type", "")

                # --- Thinking / extended thinking blocks ---
                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", "") == "thinking":
                        yield StreamChunk(type="thought", content="Thinking...")
                    elif block and getattr(block, "type", "") == "tool_use":
                        current_tool_name = getattr(block, "name", "tool")
                        current_tool_id = getattr(block, "id", None)
                        tool_input_json = ""
                        yield StreamChunk(
                            type="tool_call",
                            content="",
                            tool_name=current_tool_name,
                            tool_call_id=current_tool_id,
                        )

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    delta_type = getattr(delta, "type", "")

                    if delta_type == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield StreamChunk(type="content", content=text)

                    elif delta_type == "thinking_delta":
                        text = getattr(delta, "thinking", "")
                        if text:
                            yield StreamChunk(type="thought", content=text)

                    elif delta_type == "input_json_delta":
                        tool_input_json += getattr(delta, "partial_json", "")

                elif event_type == "content_block_stop":
                    if current_tool_name:
                        try:
                            parsed_input = json.loads(tool_input_json) if tool_input_json else {}
                        except json.JSONDecodeError:
                            parsed_input = {"raw": tool_input_json}
                        yield StreamChunk(
                            type="tool_call",
                            content=f"Calling {current_tool_name}",
                            tool_name=current_tool_name,
                            tool_input=parsed_input,
                            tool_call_id=current_tool_id,
                        )
                        current_tool_name = None
                        current_tool_id = None
                        tool_input_json = ""

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_messages(
        prompt: str, messages: list[dict[str, str]] | None
    ) -> list[dict[str, str]]:
        if messages:
            return messages
        return [{"role": "user", "content": prompt}]

    def _base_kwargs(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int | None,
        temperature: float,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            # Resolves to: caller value → env override → per-model max from
            # SUPPORTED_MODELS → conservative 4096 fallback. Avoids the old
            # bug where Sonnet 4.6 was silently capped at 4096 of its 16K.
            "max_tokens": _resolve_max_tokens(self._model, max_tokens),
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        return kwargs

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", "") == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts)
