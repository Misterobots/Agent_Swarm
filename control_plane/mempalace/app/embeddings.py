"""Ollama-backed embedding generation and LLM memory extraction."""

import os
import re
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger("mempalace.embeddings")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.2.101:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "nemotron-mini")
HTTPX_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=HTTPX_TIMEOUT)
    return _client


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
async def embed_text(text: str) -> list[float]:
    """Generate a 768-dim embedding via Ollama nomic-embed-text."""
    client = _get_client()
    resp = await client.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": EMBED_MODEL, "input": text},
    )
    resp.raise_for_status()
    data = resp.json()
    # Ollama /api/embed returns {"embeddings": [[...], ...]}
    return data["embeddings"][0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts."""
    client = _get_client()
    resp = await client.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


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
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text[:4000])

    try:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": EXTRACT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024},
            },
            timeout=90.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()

        memories = _parse_llm_json(raw)
        if memories is None:
            return []

        if not isinstance(memories, list):
            logger.warning("Extraction returned non-list: %s", type(memories))
            return []

        # Validate structure
        valid = []
        for m in memories:
            if isinstance(m, dict) and "content" in m and "type" in m:
                valid.append({
                    "content": str(m["content"])[:500],
                    "type": m.get("type", "semantic"),
                    "domain": m.get("domain", "general"),
                })
        return valid

    except (json.JSONDecodeError, httpx.HTTPError) as exc:
        logger.warning("Memory extraction failed: %s", exc)
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
        logger.warning("Unbalanced brackets in LLM JSON output")
        return None

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
    except json.JSONDecodeError as exc:
        logger.warning("JSON repair failed: %s", exc)
        return None


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
