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
import uuid

import requests

from config import OLLAMA_HOST, get_ollama_options
from dev_harness.arg_repair import parse_tool_args
from dev_harness.base import ProviderResult
from dev_harness.history import History, ToolCall
from dev_harness.qwen_toolparse import extract_text_tool_calls

logger = logging.getLogger("ollama_provider")


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, host: str | None = None, timeout: float = 300.0,
                 temperature: float = 0.2):
        self.model = model
        self.host = (host or OLLAMA_HOST).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def chat_with_tools(self, history: History, tools: list[dict]) -> ProviderResult:
        payload = {
            "model": self.model,
            "messages": history.to_openai_messages(args_as_string=False),
            "tools": tools,
            "stream": False,
            # low temp for coding; num_ctx from CONTEXT_WINDOWS via get_ollama_options
            "options": get_ollama_options(self.model, temperature=self.temperature),
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

        return ProviderResult(text=text, tool_calls=calls, malformed_args=malformed)
