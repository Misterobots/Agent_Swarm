"""Ollama-backed embedding generation and LLM memory extraction."""

from __future__ import annotations

import asyncio
import os
import re
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger("mempalace.embeddings")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "qwen2.5-coder:14b-instruct-q4_k_m")
HTTPX_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))
EMBED_RETRIES = int(os.getenv("OLLAMA_EMBED_RETRIES", "2"))

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=HTTPX_TIMEOUT)
    return _client


async def _embed_post(payload: dict) -> list[list[float]]:
    """POST to Ollama /api/embed with bounded retries on transient failures.

    Retries on connection errors, timeouts, and 5xx responses. Does NOT retry
    on 4xx (caller error), and surfaces the original exception after the
    final attempt so the FastAPI handler can return a meaningful 5xx.
    """
    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(EMBED_RETRIES + 1):
        try:
            resp = await client.post(f"{OLLAMA_HOST}/api/embed", json=payload)
            if 500 <= resp.status_code < 600:
                resp.raise_for_status()  # raises HTTPStatusError → retry
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            # Don't retry 4xx
            if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                raise
            last_exc = exc
            if attempt < EMBED_RETRIES:
                backoff = 0.5 * (2 ** attempt)
                logger.warning(
                    "Ollama embed attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1, EMBED_RETRIES + 1, exc, backoff,
                )
                await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
async def embed_text(text: str) -> list[float]:
    """Generate a 768-dim embedding via Ollama nomic-embed-text."""
    embeddings = await _embed_post({"model": EMBED_MODEL, "input": text})
    return embeddings[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts."""
    return await _embed_post({"model": EMBED_MODEL, "input": texts})


# ---------------------------------------------------------------------------
# Memory extraction via LLM
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """\
Analyze the following conversation and extract key facts, preferences, \
learnings, or rules that should be remembered for future interactions.

Return ONLY a JSON array. Each element must have:
- "content": the fact or learning (one clear sentence)
- "type": one of "semantic" (factual knowledge), "episodic" (event/experience), "procedural" (rule/how-to)
- "domain": category such as "visual", "coding", "general", "architecture", "preferences"

Rules:
- Only extract genuinely useful, durable information.
- Skip trivial, temporary, or context-specific details.
- If nothing is worth remembering, return an empty array [].
- Do NOT include any text outside the JSON array.

Conversation:
{conversation}

JSON array:"""


async def extract_memories(conversation_text: str) -> list[dict]:
    """Use an LLM to extract memorable facts from a conversation turn."""
    client = _get_client()

    for attempt, max_chars in enumerate([4000, 2000], 1):
        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text[:max_chars])

        try:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": EXTRACT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()

            memories = _parse_llm_json(raw)
            if memories is not None and isinstance(memories, list) and len(memories) > 0:
                # Validate structure
                valid = []
                for m in memories:
                    if isinstance(m, dict) and "content" in m and "type" in m:
                        valid.append({
                            "content": str(m["content"])[:500],
                            "type": m.get("type", "semantic"),
                            "domain": m.get("domain", "general"),
                        })
                if valid:
                    return valid
                logger.warning("Attempt %d: extracted %d items but none valid", attempt, len(memories))
            else:
                logger.warning("Attempt %d: extraction returned empty/null", attempt)

        except (json.JSONDecodeError, httpx.HTTPError) as exc:
            logger.warning("Attempt %d extraction failed: %s", attempt, exc)

    return []


def _parse_llm_json(raw: str):
    """Best-effort JSON array extraction from potentially messy LLM output."""
    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:  # odd-indexed parts are inside fences
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    pass

    raw = raw.strip()

    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract the first [...] block via bracket matching
    start = raw.find("[")
    if start == -1:
        logger.warning("No JSON array found in LLM output (len=%d)", len(raw))
        return None
    depth = 0
    end = start
    for i, ch in enumerate(raw[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if depth != 0:
        logger.warning("Unbalanced brackets in LLM JSON output — attempting repair")
        # Try to close the array at the last complete object '}'
        last_brace = raw.rfind("}")
        if last_brace > start:
            fragment = raw[start:last_brace + 1] + "]"
        else:
            return None
    else:
        fragment = raw[start:end]

    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        pass

    # Fix common LLM JSON errors: trailing commas, missing commas between objects
    cleaned = re.sub(r",\s*([}\]])", r"\1", fragment)  # trailing commas
    cleaned = re.sub(r"(\})\s*(\{)", r"\1, \2", cleaned)  # missing commas between objects
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: regex-extract individual {...} objects
    objects = re.findall(r'\{[^{}]*\}', fragment)
    if objects:
        results = []
        for obj_str in objects:
            try:
                results.append(json.loads(obj_str))
            except json.JSONDecodeError:
                continue
        if results:
            logger.info("Recovered %d memories via regex fallback", len(results))
            return results

    logger.warning("JSON repair failed for fragment (len=%d)", len(fragment))
    return None


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
