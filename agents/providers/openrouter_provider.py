"""
OpenRouter provider — OpenAI-compatible inference.
Calls https://openrouter.ai/api/v1/chat/completions using the user's stored key.

Deliberately the same shape as `nvidia_provider.py`, which is also an
OpenAI-compatible client: two near-identical providers are cheaper than one
abstraction nobody asked for, and the difference between them (attribution headers,
how a failure is reported) is where a shared base would have hidden it.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Generator, Optional

logger = logging.getLogger("openrouter_provider")

INFERENCE_BASE = "https://openrouter.ai/api/v1"

# OpenRouter uses these two headers for app attribution on its rankings page; they
# are not authorisation and carry no secret. Absent is fine, a wrong referer is not
# fatal, so they are sent from env with a harmless default.
_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "")
_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Memex")


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


class OpenRouterProvider:
    """Wraps OpenRouter's chat API. The key is fetched from provider_keys per call."""

    def __init__(self, user_id: str, model: str = ""):
        self.user_id = user_id
        self.model = model

    def _get_api_key(self) -> str:
        from provider_keys import get_key
        record = get_key(self.user_id, "openrouter")
        if not record:
            raise RuntimeError(
                f"No OpenRouter API key found for user_id={self.user_id}. "
                "Add your key in Settings → Model providers."
            )
        return record.get_api_key()

    def _headers(self, stream: bool) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        if _REFERER:
            headers["HTTP-Referer"] = _REFERER
        if _TITLE:
            headers["X-Title"] = _TITLE
        return headers

    def _payload(self, messages: list[dict[str, str]], max_tokens: int, temperature: float, stream: bool, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        # Optional per-request routing controls, passed straight through so a caller
        # can pin a provider route without this class learning OpenRouter's grammar.
        for key in ("provider", "models", "route", "top_p", "stop"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return payload

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> StreamChunk:
        import urllib.request
        payload = self._payload(messages, max_tokens, temperature, False, **kwargs)
        req = urllib.request.Request(
            f"{INFERENCE_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(stream=False),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read())
            message = body["choices"][0]["message"]
            content = message.get("content") or ""
            # Some OpenRouter routes answer with reasoning plus a null content;
            # reporting that as an empty success would look like a broken model.
            if not content:
                reasoning = message.get("reasoning") or ""
                content = reasoning
            return StreamChunk(type="content", content=content)
        except Exception as e:
            logger.error(f"openrouter generate error: {e}", exc_info=True)
            return StreamChunk(type="error", content=f"OpenRouter API error: {e}")

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        import urllib.request
        payload = self._payload(messages, max_tokens, temperature, True, **kwargs)
        req = urllib.request.Request(
            f"{INFERENCE_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(stream=True),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    # An SSE error frame carries {"error": {...}} and no choices.
                    if isinstance(chunk, dict) and chunk.get("error"):
                        yield StreamChunk(type="error", content=f"OpenRouter API error: {chunk['error']}")
                        return
                    try:
                        choice = (chunk.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                    except (AttributeError, IndexError, TypeError):
                        continue
                    text = delta.get("content")
                    if text:
                        yield StreamChunk(type="content", content=text)
                    reasoning = delta.get("reasoning")
                    if reasoning and not text:
                        yield StreamChunk(type="content", content=reasoning)
        except Exception as e:
            logger.error(f"openrouter stream error: {e}", exc_info=True)
            yield StreamChunk(type="error", content=f"OpenRouter API error: {e}")
