"""
Z.ai GLM provider — OpenAI-compatible inference
Calls https://api.z.ai/api/paas/v4/chat/completions using stored API keys.
Supports streaming and non-streaming modes.

GLM (Zhipu / Z.ai) exposes an OpenAI-compatible surface, so this adapter is a
near-exact twin of google_provider / nvidia_provider — only the base URL and
the provider_keys lookup id differ.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Generator, Optional

logger = logging.getLogger("glm_provider")

# Z.ai International OpenAI-compatible endpoint.
# Mainland-China accounts use https://open.bigmodel.cn/api/paas/v4 instead;
# override via GLM_INFERENCE_BASE if needed.
INFERENCE_BASE = os.getenv("GLM_INFERENCE_BASE", "https://api.z.ai/api/paas/v4")


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

class GLMProvider:
    """
    Wraps the Z.ai GLM inference API (OpenAI-compatible endpoint).
    API key is fetched from provider_keys on every call.
    """

    def __init__(self, user_id: str, model: str = "glm-5.2"):
        self.user_id = user_id
        self.model = model

    def _get_api_key(self) -> str:
        from provider_keys import get_key
        record = get_key(self.user_id, "glm")
        if not record:
            raise RuntimeError(
                f"No GLM API key found for user_id={self.user_id}. "
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
        import urllib.error
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
            logger.error(f"glm generate HTTP {e.code}: {detail}", exc_info=True)
            return StreamChunk(type="error", content=f"GLM API error {e.code}: {detail}")
        except Exception as e:
            logger.error(f"glm generate error: {e}", exc_info=True)
            return StreamChunk(type="error", content=f"GLM API error: {e}")

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 8192,
        temperature: float = 0.7,
        grounding_web: bool = False,
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        """SSE streaming completion — yields StreamChunk objects.

        When grounding_web=True, GLM's native web_search tool is enabled so the
        model decides when to search and integrates results itself, rather than
        doing RAG pre-injection on our side.
        """
        import urllib.error
        import urllib.request

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if grounding_web:
            payload["tools"] = [{"type": "web_search", "web_search": {"enable": True}}]

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
                        # GLM-5.2 is a reasoning model: it streams a long burst of
                        # `reasoning_content` (the chain-of-thought) BEFORE any
                        # `content`. Forward it as "thought" chunks so (a) bytes keep
                        # flowing through proxies during the think phase — otherwise
                        # the idle SSE connection gets killed before the answer starts
                        # — and (b) the UI renders it live in the thinking panel.
                        reasoning = delta.get("reasoning_content")
                        if reasoning:
                            yield StreamChunk(type="thought", content=reasoning)
                        text = delta.get("content") or ""
                        if text:
                            yield StreamChunk(type="content", content=text)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            logger.error(f"glm stream HTTP {e.code}: {detail}", exc_info=True)
            yield StreamChunk(type="error", content=f"GLM API error {e.code}: {detail}")
        except Exception as e:
            logger.error(f"glm stream error: {e}", exc_info=True)
            yield StreamChunk(type="error", content=f"GLM API error: {e}")
