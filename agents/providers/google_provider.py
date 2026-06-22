"""
Google Gemini provider — OpenAI-compatible inference
Calls https://generativelanguage.googleapis.com/v1beta/openai/ using stored API keys.
Supports streaming and non-streaming modes.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Generator, Optional

logger = logging.getLogger("google_provider")

# Google's OpenAI-compatible endpoint
INFERENCE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


# ---------------------------------------------------------------------------
# Normalised streaming chunk — same shape as other providers
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

class GoogleProvider:
    """
    Wraps the Google Gemini inference API (OpenAI-compatible endpoint).
    API key is fetched from provider_keys on every call.
    """

    def __init__(self, user_id: str, model: str = "gemini-2.0-flash"):
        self.user_id = user_id
        self.model = model

    def _get_api_key(self) -> str:
        from provider_keys import get_key
        record = get_key(self.user_id, "google")
        if not record:
            raise RuntimeError(
                f"No Google API key found for user_id={self.user_id}. "
                "Add your key in Settings → Provider API Keys."
            )
        return record.get_api_key()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 8192,
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
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            logger.error(f"google generate HTTP {e.code}: {detail}", exc_info=True)
            return StreamChunk(type="error", content=f"Google API error {e.code}: {detail}")
        except Exception as e:
            logger.error(f"google generate error: {e}", exc_info=True)
            return StreamChunk(type="error", content=f"Google API error: {e}")

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 8192,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        """SSE streaming completion — yields StreamChunk objects."""
        import urllib.error
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
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            logger.error(f"google stream HTTP {e.code}: {detail}", exc_info=True)
            yield StreamChunk(type="error", content=f"Google API error {e.code}: {detail}")
        except Exception as e:
            logger.error(f"google stream error: {e}", exc_info=True)
            yield StreamChunk(type="error", content=f"Google API error: {e}")
