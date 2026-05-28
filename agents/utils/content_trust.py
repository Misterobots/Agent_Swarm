"""
Content Trust & Provenance-Aware Security Scanning
====================================================
Fires llama-guard3:8b only at trust boundaries — retrieved/external content —
not on every authenticated user turn.

Trust levels
------------
INTERNAL   Authenticated user message, agent-to-agent comms, system output.
           → fast regex pre-check only (no GPU)

RETRIEVED  Web search results, fetched page text, tool/function call returns,
           third-party API responses injected into the prompt.
           → fast regex + llama-guard3:8b on Turing

INGESTED   User-uploaded documents / knowledge-base additions.
           → same as RETRIEVED; result is cached by content hash so
             the same chunk is never re-scanned on subsequent retrievals.

EXTERNAL   Third-party plugin / component imports, manifest descriptions.
           → same as RETRIEVED

Attack surfaces this covers
---------------------------
• Indirect prompt injection via RAG / web retrieval
• Web-page or document poisoning
• Tool-output hijacking (browser, terminal, skill runner)
• Third-party component import poisoning

What it intentionally does NOT cover
--------------------------------------
• Direct user jailbreak attempts — the existing regex SecurityAgent in
  security_agent.py already handles that on user input. Adding llama-guard
  there too would double the latency for every turn.
  Exception: the FIRST turn of any external/anonymous session should still
  call llama-guard; authenticated internal sessions can skip it.

Usage
-----
    from utils.content_trust import sanitize_external_content, TrustLevel

    clean_text, is_clean = sanitize_external_content(
        content   = page_text,
        trust     = TrustLevel.RETRIEVED,
        source    = url,          # for log attribution
    )
    if not is_clean:
        # content was redacted; use clean_text which contains the placeholder
        ...
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from enum import Enum
from functools import lru_cache
from typing import Dict, Tuple

import requests

logger = logging.getLogger("ContentTrust")

# ---------------------------------------------------------------------------
# Trust levels
# ---------------------------------------------------------------------------

class TrustLevel(str, Enum):
    INTERNAL  = "internal"    # authenticated user / agent output
    RETRIEVED = "retrieved"   # web result / tool output / API response
    INGESTED  = "ingested"    # user-uploaded document (scan once, cache)
    EXTERNAL  = "external"    # third-party plugin / component import


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDACTED = "[CONTENT REDACTED — security scan flagged this content as unsafe]"

# llama-guard3 lives on Turing's local Ollama (SECONDARY_OLLAMA_HOST).
# Imported lazily to avoid circular dependency at module load.
_GUARD_MODEL    = os.getenv("GUARD_MODEL", "llama-guard3:8b")
_GUARD_TIMEOUT  = int(os.getenv("GUARD_TIMEOUT_SECS", "30"))

# Simple in-process cache: content_hash → (is_clean: bool, timestamp: float)
# Avoids rescanning the same document chunk on every retrieval.
_SCAN_CACHE: Dict[str, Tuple[bool, float]] = {}
_CACHE_TTL   = 3600  # 1 hour — re-scan if content is seen again after an hour
_CACHE_MAX   = 4096  # evict oldest entries above this threshold

# ---------------------------------------------------------------------------
# Fast regex injection scanner  (no GPU, ~microseconds)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = re.compile(
    # Classic "ignore instructions" variants
    r"ignore\s+(previous|prior|all)\s+(instructions?|prompts?|context|system)"
    # Role-swap / persona injection
    r"|you\s+are\s+now\s+(a|an|the)\s+\w"
    r"|act\s+as\s+(if\s+you\s+are\s+)?(a|an|the)\s+\w"
    # System-prompt boundary injection
    r"|<\s*/?system\s*>"
    r"|system\s*:\s*you\s+(are|must|should|will)"
    # Common LLM instruction template injections
    r"|\[\s*INST\s*\]"
    r"|<\|im_(start|end)\|>"
    r"|###\s*(Human|Assistant|System)\s*:"
    r"|<\s*/?(human|assistant|bot)\s*>"
    # Direct commands to override behaviour
    r"|IGNORE\s+AND\s+(PRINT|EXECUTE|OUTPUT|REPEAT|SAY)"
    r"|disregard\s+(your|all|any|previous)\s+(instructions?|training|guidelines?)"
    r"|your\s+(new|true|real|actual)\s+(instructions?|purpose|goal|task)\s+(is|are)"
    # Exfiltration patterns
    r"|print\s+(your|the)\s+(system\s+)?prompt"
    r"|reveal\s+(your|the)\s+(system\s+)?prompt"
    r"|what\s+(is|are)\s+your\s+(system\s+)?instructions?"
    # Self-referential override
    r"|prompt\s+injection"
    r"|jailbreak",
    re.IGNORECASE | re.DOTALL,
)


def fast_injection_scan(content: str) -> bool:
    """
    Returns True if injection-like patterns are detected.
    No GPU required — pure regex, completes in microseconds.
    Intended as a cheap first pass before invoking llama-guard.
    """
    return bool(_INJECTION_PATTERNS.search(content))


# ---------------------------------------------------------------------------
# llama-guard3 scanner  (GPU-backed, Turing local Ollama)
# ---------------------------------------------------------------------------

def _guard_host() -> str:
    """Return the Ollama host that runs llama-guard (Turing local)."""
    # Import here to avoid circular import at module load time.
    try:
        from utils.gpu_queue import SECONDARY_OLLAMA_HOST
        return SECONDARY_OLLAMA_HOST
    except ImportError:
        return os.getenv("SECONDARY_OLLAMA_HOST", "http://ollama:11434")


def llama_guard_scan(content: str, source: str = "") -> Tuple[str, bool]:
    """
    Send content to llama-guard3:8b on Turing's local Ollama.
    Returns (content_or_redaction, is_clean).

    Fail-open: if the guard is unreachable, pass through and log a warning
    so that a down Turing node doesn't block all requests.
    """
    host  = _guard_host()
    model = _GUARD_MODEL

    # llama-guard3 uses /v1/chat/completions with a safety-check role message.
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content[:8000]}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 50},
    }

    try:
        resp = requests.post(
            f"{host}/v1/chat/completions",
            json=payload,
            timeout=_GUARD_TIMEOUT,
        )
        if resp.status_code == 200:
            verdict = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .lower()
            )
            is_safe = verdict.startswith("safe")
            if not is_safe:
                logger.warning(
                    f"[ContentTrust] llama-guard UNSAFE from {source!r}: {verdict[:120]}"
                )
                return REDACTED, False
            logger.debug(f"[ContentTrust] llama-guard SAFE for source={source!r}")
            return content, True
        else:
            logger.warning(
                f"[ContentTrust] llama-guard HTTP {resp.status_code} — fail-open for {source!r}"
            )
    except requests.exceptions.ConnectionError:
        logger.warning(
            f"[ContentTrust] llama-guard unreachable at {host} — fail-open for {source!r}"
        )
    except requests.exceptions.Timeout:
        logger.warning(
            f"[ContentTrust] llama-guard timeout ({_GUARD_TIMEOUT}s) — fail-open for {source!r}"
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"[ContentTrust] llama-guard error ({e}) — fail-open for {source!r}")

    # Fail-open: if the guard is unavailable, let content through.
    # Fast regex already ran before this function was called.
    return content, True


# ---------------------------------------------------------------------------
# Scan-result cache helpers
# ---------------------------------------------------------------------------

def _cache_key(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _cache_get(key: str) -> bool | None:
    """Return cached is_clean result, or None if expired / not cached."""
    entry = _SCAN_CACHE.get(key)
    if entry is None:
        return None
    is_clean, ts = entry
    if time.time() - ts > _CACHE_TTL:
        del _SCAN_CACHE[key]
        return None
    return is_clean


def _cache_put(key: str, is_clean: bool) -> None:
    if len(_SCAN_CACHE) >= _CACHE_MAX:
        # Evict the oldest quarter of entries
        sorted_keys = sorted(_SCAN_CACHE, key=lambda k: _SCAN_CACHE[k][1])
        for k in sorted_keys[: _CACHE_MAX // 4]:
            del _SCAN_CACHE[k]
    _SCAN_CACHE[key] = (is_clean, time.time())


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def sanitize_external_content(
    content: str,
    trust: TrustLevel,
    source: str = "",
    use_cache: bool = True,
) -> Tuple[str, bool]:
    """
    Scan *content* according to its trust level.

    Parameters
    ----------
    content    The text to scan (web page, tool result, doc chunk, …).
    trust      TrustLevel enum value describing the content's origin.
    source     Human-readable source label used in log messages (URL, tool name, …).
    use_cache  Whether to check/update the in-process scan cache.
               Disable for content that changes frequently.

    Returns
    -------
    (sanitized_content, is_clean)
        If is_clean is False, sanitized_content is the REDACTED placeholder.
    """
    # Internal content (authenticated user, agent output) → trust immediately.
    if trust == TrustLevel.INTERNAL:
        return content, True

    if not content or not content.strip():
        return content, True

    # Check cache for INGESTED content (documents scanned at ingest time).
    if use_cache and trust == TrustLevel.INGESTED:
        key = _cache_key(content)
        cached = _cache_get(key)
        if cached is not None:
            if not cached:
                logger.debug(f"[ContentTrust] Cache hit: previously flagged content from {source!r}")
                return REDACTED, False
            return content, True

    # ── Fast regex pre-filter (no GPU) ──────────────────────────────────────
    if fast_injection_scan(content):
        logger.warning(
            f"[ContentTrust] Injection pattern (regex) detected from {source!r} "
            f"(trust={trust.value}) — redacting"
        )
        if use_cache and trust == TrustLevel.INGESTED:
            _cache_put(_cache_key(content), False)
        return REDACTED, False

    # ── GPU-backed llama-guard scan ──────────────────────────────────────────
    clean_content, is_safe = llama_guard_scan(content, source)

    if use_cache and trust == TrustLevel.INGESTED:
        _cache_put(_cache_key(content), is_safe)

    return clean_content, is_safe


def sanitize_chunks(
    chunks: list[str],
    trust: TrustLevel,
    source: str = "",
) -> list[str]:
    """
    Convenience wrapper to sanitize a list of text chunks (e.g. RAG results).
    Redacted chunks are replaced with the REDACTED placeholder in-place.
    """
    return [sanitize_external_content(c, trust, source)[0] for c in chunks]
