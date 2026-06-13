"""
GitHub Models provider — Phase 1C
Calls https://models.github.ai/inference using the user's stored OAuth token.
Presents the same generate / generate_stream interface as AnthropicProvider.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator, Optional

logger = logging.getLogger("github_models_provider")

# ---------------------------------------------------------------------------
# Model catalogue (static initial list; fetched dynamically on connect)
# ---------------------------------------------------------------------------

GITHUB_MODELS: list[dict[str, Any]] = [
    {"id": "openai/gpt-4o",                  "label": "GPT-4o",                "context": 128_000},
    {"id": "openai/gpt-4o-mini",             "label": "GPT-4o Mini",           "context": 128_000},
    {"id": "openai/gpt-4.1",                 "label": "GPT-4.1",               "context": 1_047_576},
    {"id": "openai/o1",                      "label": "o1",                    "context": 200_000},
    {"id": "openai/o1-mini",                 "label": "o1-mini",               "context": 128_000},
    {"id": "openai/o3",                      "label": "o3",                    "context": 200_000},
    {"id": "openai/o3-mini",                 "label": "o3-mini",               "context": 200_000},
    {"id": "meta/llama-3.3-70b-instruct",    "label": "Llama 3.3 70B",         "context": 131_072},
    {"id": "microsoft/phi-4-mini-instruct",  "label": "Phi-4 Mini",            "context": 131_072},
]

INFERENCE_BASE = "https://models.github.ai/inference"


# Catalog ids are stored verbatim in the form GitHub Models accepts
# (publisher-prefixed, e.g. `openai/gpt-4o`). No stripping needed.


# ---------------------------------------------------------------------------
# Normalised streaming chunk — same shape as AnthropicProvider.StreamChunk
# ---------------------------------------------------------------------------

@dataclass
class StreamChunk:
    type: str = "content"
    content: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_call_id: Optional[str] = None

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
# Provider
# ---------------------------------------------------------------------------

class GitHubModelsProvider:
    """
    Wraps the GitHub Models inference API (OpenAI-compatible).
    Token is fetched from github_oauth on every call so rotation is seamless.
    """

    def __init__(self, user_id: str, model: str = "github/gpt-4o"):
        self.user_id = user_id
        self.model = model

    def _get_token(self) -> str:
        from github_oauth import get_token
        record = get_token(self.user_id)
        if not record:
            raise RuntimeError(
                f"No GitHub token found for user_id={self.user_id}. "
                "Connect a GitHub account in Settings → Connected Accounts."
            )
        return record.get_plaintext_token()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> StreamChunk:
        """Non-streaming completion — returns a single StreamChunk."""
        import urllib.request

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{INFERENCE_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read())
            content = body["choices"][0]["message"]["content"]
            return StreamChunk(type="content", content=content)
        except Exception as e:
            logger.error(f"github_models generate error: {e}", exc_info=True)
            return StreamChunk(type="error", content=f"GitHub Models error: {e}")

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        """SSE streaming completion — yields StreamChunk objects."""
        import urllib.request

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        req = urllib.request.Request(
            f"{INFERENCE_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={**self._headers(), "Accept": "text/event-stream"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content") or ""
                        if text:
                            yield StreamChunk(type="content", content=text)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as e:
            logger.error(f"github_models stream error: {e}", exc_info=True)
            yield StreamChunk(type="error", content=f"GitHub Models error: {e}")

    # -----------------------------------------------------------------------
    # Phase 2 — Agentic loop with tool calling
    # -----------------------------------------------------------------------

    async def generate_stream_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_executor,          # async (name: str, args: dict) -> str
        max_iterations: int = 10,
    ):
        """
        Async generator — implements the model → tool call → result → model loop.

        Yields StreamChunk objects (same shape used throughout the pipeline).
        The caller serialises them to SSE.

        tool_executor signature:
            async def execute(name: str, arguments: dict) -> str
        """
        import urllib.request
        import uuid as _uuid

        iteration = 0
        current_messages = list(messages)

        while iteration < max_iterations:
            iteration += 1

            payload: dict = {
                "model": self.model,
                "messages": current_messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": 4096,
                "temperature": 0.2,      # lower temp for coding tasks
                "stream": False,          # non-streaming so we can inspect tool_calls
            }

            req = urllib.request.Request(
                f"{INFERENCE_BASE}/chat/completions",
                data=json.dumps(payload).encode(),
                headers=self._headers(),
                method="POST",
            )
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                # Run blocking HTTP in executor to avoid blocking the event loop
                def _http_call():
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        return json.loads(resp.read())

                body = await loop.run_in_executor(None, _http_call)
            except Exception as e:
                logger.error(f"github_models tool-call HTTP error (iter {iteration}): {e}", exc_info=True)
                yield StreamChunk(type="error", content=f"GitHub Models error: {e}")
                return

            choice = body["choices"][0]
            finish_reason = choice.get("finish_reason", "stop")
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls") or []
            content_text = message.get("content") or ""

            # Add assistant message (with or without tool_calls) to history
            current_messages.append(message)

            if not tool_calls:
                # No more tool calls — stream the final assistant text and exit
                if content_text:
                    # Yield in smallish chunks so the UI streams smoothly
                    CHUNK_SIZE = 80
                    for i in range(0, len(content_text), CHUNK_SIZE):
                        yield StreamChunk(type="content", content=content_text[i:i + CHUNK_SIZE])
                return

            # ---- Execute each tool call ----
            for tc in tool_calls:
                call_id = tc.get("id") or str(_uuid.uuid4())
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                yield StreamChunk(
                    type="tool_start",
                    content=f"Using tool: {tool_name}",
                    tool_name=tool_name,
                    tool_input=tool_args,
                    tool_call_id=call_id,
                )

                # Execute (may wait for user approval inside tool_executor)
                tool_result = await tool_executor(call_id, tool_name, tool_args)

                yield StreamChunk(
                    type="tool_result",
                    content=tool_result,
                    tool_name=tool_name,
                    tool_call_id=call_id,
                )

                # Append tool result back to the conversation
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_result,
                })

            if finish_reason == "stop":
                # Model said stop even though there were tool calls — shouldn't happen,
                # but treat it as done.
                return

        # Max iterations guard
        yield StreamChunk(
            type="error",
            content=f"Agentic loop exceeded {max_iterations} iterations — stopping.",
        )


# ---------------------------------------------------------------------------
# Dev-harness adapter — single-turn tool call over the neutral history.
# Used as a selectable provider and as the first escalation target (gpt-4o is a
# reliable tool-caller, so validating the harness against it isolates harness
# bugs from local-model weakness).  Reuses GitHubModelsProvider for token/headers.
# ---------------------------------------------------------------------------

class GitHubProvider:
    """Provider-protocol adapter: one non-streaming tools call, neutral in/out."""

    name = "github"

    def __init__(self, user_id: str, model: str):
        self._inner = GitHubModelsProvider(user_id=user_id, model=model)
        self.model = model

    def chat_with_tools(self, history, tools: list[dict]):
        import urllib.request
        import uuid as _uuid
        from dev_harness.base import ProviderResult
        from dev_harness.history import ToolCall
        from dev_harness.arg_repair import parse_tool_args

        payload: dict = {
            "model": self.model,
            "messages": history.to_openai_messages(args_as_string=True),
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 4096,
            "temperature": 0.2,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{INFERENCE_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._inner._headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read())

        message = body["choices"][0].get("message", {})
        text = message.get("content") or ""
        calls: list = []
        malformed = False
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {}) or {}
            args, ok = parse_tool_args(fn.get("arguments"))  # GitHub sends a JSON string
            if not ok:
                malformed = True
            calls.append(
                ToolCall(
                    call_id=tc.get("id") or f"call_{_uuid.uuid4().hex[:8]}",
                    name=fn.get("name", ""),
                    args=args,
                )
            )
        return ProviderResult(text=text, tool_calls=calls, malformed_args=malformed)
