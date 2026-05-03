"""
NVIDIA NIM provider — OpenAI-compatible inference
Calls https://integrate.api.nvidia.com/v1/chat/completions using stored API keys.
Supports streaming and non-streaming modes.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Generator, Optional

logger = logging.getLogger("nvidia_provider")

INFERENCE_BASE = "https://integrate.api.nvidia.com/v1"


def _model_name(model_id: str) -> str:
    """Strip 'nvidia/' prefix for the API call."""
    return model_id.removeprefix("nvidia/")


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

class NvidiaProvider:
    """
    Wraps the NVIDIA NIM inference API (OpenAI-compatible).
    API key is fetched from provider_keys on every call.
    """

    def __init__(self, user_id: str, model: str = "nvidia/llama-3.1-nemotron-70b-instruct"):
        self.user_id = user_id
        self.model = model

    def _get_api_key(self) -> str:
        from provider_keys import get_key
        record = get_key(self.user_id, "nvidia")
        if not record:
            raise RuntimeError(
                f"No NVIDIA API key found for user_id={self.user_id}. "
                "Add your key in Settings → Provider API Keys."
            )
        return record.get_api_key()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
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
        
        # Add Kimi-specific thinking parameter if applicable
        if "kimi" in self.model.lower():
            payload["chat_template_kwargs"] = {"thinking": True}

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
            logger.error(f"nvidia generate error: {e}", exc_info=True)
            return StreamChunk(type="error", content=f"NVIDIA API error: {e}")

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
        
        # Add Kimi-specific thinking parameter if applicable
        if "kimi" in self.model.lower():
            payload["chat_template_kwargs"] = {"thinking": True}

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
            logger.error(f"nvidia stream error: {e}", exc_info=True)
            yield StreamChunk(type="error", content=f"NVIDIA API error: {e}")
