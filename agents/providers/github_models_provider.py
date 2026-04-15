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
    {"id": "github/gpt-4o",              "label": "GPT-4o",           "context": 128_000},
    {"id": "github/gpt-4o-mini",         "label": "GPT-4o Mini",      "context": 128_000},
    {"id": "github/o1",                  "label": "o1",                "context": 200_000},
    {"id": "github/o1-mini",             "label": "o1-mini",           "context": 128_000},
    {"id": "github/o3-mini",             "label": "o3-mini",           "context": 200_000},
    {"id": "github/claude-sonnet-4-20250514",  "label": "Claude Sonnet 4",   "context": 200_000},
    {"id": "github/claude-haiku-3-5-20241022", "label": "Claude Haiku 3.5",  "context": 200_000},
    {"id": "github/gemini-2.0-flash",    "label": "Gemini 2.0 Flash",  "context": 1_048_576},
    {"id": "github/Llama-4-Scout-17B-16E-Instruct", "label": "Llama 4 Scout", "context": 131_072},
    {"id": "github/Phi-4-mini-instruct", "label": "Phi-4 Mini",        "context": 131_072},
]

INFERENCE_BASE = "https://models.github.ai/inference"


def _model_name(model_id: str) -> str:
    """Strip 'github/' prefix for the API call."""
    return model_id.removeprefix("github/")


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
            "model": _model_name(self.model),
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
            "model": _model_name(self.model),
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
