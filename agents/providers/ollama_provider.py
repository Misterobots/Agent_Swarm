"""
ollama_provider.py — local Ollama adapter for the dev harness (default backend).

Calls Ollama's OpenAI-compatible /api/chat with `tools=[...]` and reads
`message.tool_calls`.  Two deltas from the GitHub/OpenAI path:
  - Ollama returns `function.arguments` as a **dict**, not a JSON string.
  - Ollama tool_calls have no `id`, so we synthesise a stable call_id.

Tool definitions are passed through unchanged: Ollama accepts the same
`{"type": "function", "function": {...}}` schema the catalogue already uses.
Context window comes from config.get_ollama_options (num_ctx per model).
"""

from __future__ import annotations

import logging
import base64
import re
import uuid

import requests

from config import OLLAMA_HOST, get_ollama_options
from dev_harness.arg_repair import parse_tool_args
from dev_harness.base import ProviderResult
from dev_harness.history import History, ToolCall
from dev_harness.qwen_toolparse import extract_text_tool_calls
from providers.qwen_context import (
    QWEN_MODEL,
    QWEN_OUTPUT_RESERVE,
    ensure_context_headroom,
    estimate_messages_tokens,
    resolve_qwen_context,
)

logger = logging.getLogger("ollama_provider")


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, host: str | None = None, timeout: float = 300.0,
                 temperature: float = 0.2, context_profile: str | None = None,
                 task_mode: str = "chat"):
        self.model = model
        self.host = (host or OLLAMA_HOST).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.context = resolve_qwen_context(
            model, context_profile=context_profile, task_mode=task_mode
        )
        self.requested_model = model
        self.actual_model = model
        self.provider = self.name
        self.fallback = False

    @property
    def metadata(self) -> dict[str, object]:
        """Provider identity and effective Qwen context for run events."""
        return {
            "context_profile": self.context.profile,
            "effective_context_tokens": self.context.effective_tokens,
            "requested_model": self.requested_model,
            "actual_model": self.actual_model,
            "provider": self.provider,
            "fallback": self.fallback,
        }

    def _options(self) -> dict:
        options = get_ollama_options(self.model, temperature=self.temperature)
        if self.model == QWEN_MODEL:
            options["num_ctx"] = self.context.effective_tokens
        return options

    def validate_context_headroom(
        self, *, input_tokens: int, output_tokens: int, tool_tokens: int = 0
    ) -> None:
        """Validate a measured request before sending it to Ollama.

        The shared harness owns token measurement.  It can call this hook
        before dispatch; non-Qwen models intentionally retain their current
        behavior.
        """
        if self.model == QWEN_MODEL:
            ensure_context_headroom(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_tokens=tool_tokens,
                effective_tokens=self.context.effective_tokens or 0,
            )

    @staticmethod
    def _messages_for_ollama(messages: list[dict]) -> list[dict]:
        """Preserve structured image content supplied by the shared history.

        Text-only histories remain byte-for-byte compatible.  Structured user
        content is passed through with an `images` field normalized from data
        URLs, which is the native Ollama image transport.
        """
        normalized: list[dict] = []
        for message in messages:
            content = message.get("content")
            raw_images = message.get("images") or []
            if not isinstance(raw_images, list):
                raise ValueError("Ollama image payload must be a list")
            images: list[str] = [OllamaProvider._normalize_image(value) for value in raw_images]
            if not isinstance(content, list):
                if not images:
                    normalized.append(message)
                else:
                    converted = dict(message)
                    converted["images"] = images
                    normalized.append(converted)
                continue
            text_parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text"):
                    text_parts.append(str(part["text"]))
                elif part.get("type") == "image_url":
                    image_url = part.get("image_url") or {}
                    url = image_url.get("url") if isinstance(image_url, dict) else image_url
                    if isinstance(url, str):
                        images.append(OllamaProvider._normalize_image(url))
                    else:
                        raise ValueError("Ollama image_url must contain a string URL")
            converted = dict(message)
            converted["content"] = "\n".join(text_parts)
            if images:
                converted["images"] = images
            normalized.append(converted)
        return normalized

    @staticmethod
    def _normalize_image(value: str) -> str:
        """Accept strict base64 or a data:image/* base64 URL only."""
        if not isinstance(value, str) or not value:
            raise ValueError("Ollama image payload must be non-empty base64")
        match = re.fullmatch(
            r"data:image/[A-Za-z0-9.+-]+;base64,(?P<data>[A-Za-z0-9+/]*={0,2})",
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
        return encoded

    def _validate_dispatch_headroom(self, messages: list[dict], tools: list[dict]) -> None:
        if self.model != QWEN_MODEL:
            return
        input_tokens = estimate_messages_tokens(messages)
        tool_tokens = estimate_serialized_tokens(tools) if tools else 0
        self.validate_context_headroom(
            input_tokens=input_tokens,
            tool_tokens=tool_tokens,
            output_tokens=QWEN_OUTPUT_RESERVE,
        )

    def chat_with_tools(self, history: History, tools: list[dict]) -> ProviderResult:
        messages = self._messages_for_ollama(
            history.to_openai_messages(args_as_string=False)
        )
        self._validate_dispatch_headroom(messages, tools)
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            # low temp for coding; num_ctx from CONTEXT_WINDOWS via get_ollama_options
            "options": self._options(),
        }
        resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()

        message = body.get("message", {}) or {}
        text = message.get("content") or ""

        calls: list[ToolCall] = []
        malformed = False
        native = message.get("tool_calls") or []
        for tc in native:
            fn = tc.get("function", {}) or {}
            name = fn.get("name", "")
            args, ok = parse_tool_args(fn.get("arguments"))
            if not ok:
                malformed = True
                logger.warning("[ollama] malformed tool args for %s: %r", name, fn.get("arguments"))
            calls.append(
                ToolCall(
                    call_id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    name=name,
                    args=args,
                )
            )

        # Fallback: qwen3-coder sometimes emits tool calls as TEXT markup instead
        # of the native tool_calls channel.  Recover them so the loop doesn't
        # mistake a tool request for a final answer.
        if not native:
            cleaned, text_calls = extract_text_tool_calls(text)
            if text_calls:
                text = cleaned
                for name, args in text_calls:
                    calls.append(
                        ToolCall(call_id=f"call_{uuid.uuid4().hex[:8]}", name=name, args=args)
                    )
                logger.info("[ollama] recovered %d text-format tool call(s) for %s",
                            len(text_calls), self.model)

        result = ProviderResult(text=text, tool_calls=calls, malformed_args=malformed)
        # ProviderResult predates the Qwen metadata contract.  Attach the
        # optional field dynamically to preserve compatibility with all other
        # provider adapters until the shared base type is updated by the lead.
        result.provider_metadata = self.metadata
        return result
