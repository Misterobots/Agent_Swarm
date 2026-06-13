"""
arg_repair.py — tolerant tool-argument parser for small local models.

qwen3-coder and friends frequently emit *almost*-valid JSON for tool arguments:
markdown fences, trailing commas, single quotes, or an unclosed brace at the
end of a truncated generation.  `parse_tool_args` accepts either an already
-decoded dict (Ollama / Anthropic) or a raw string (GitHub/OpenAI) and tries a
ladder of conservative repairs.

Returns (args: dict, ok: bool).  `ok=False` is the signal the router counts
toward escalation — it means we fell back to an empty/partial parse.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def parse_tool_args(raw: Any) -> tuple[dict[str, Any], bool]:
    """Best-effort decode of a tool-call argument payload.

    dict in  → returned as-is (ok=True).
    str in   → json.loads, then a repair ladder if that fails.
    other    → ({}, False).
    """
    if isinstance(raw, dict):
        return raw, True
    if raw is None:
        return {}, True  # no-arg tool call is legitimately empty
    if not isinstance(raw, str):
        return {}, False

    text = raw.strip()
    if not text:
        return {}, True

    # 1. Direct parse — the common case.
    parsed = _try_load(text)
    if parsed is not None:
        return parsed, True

    # 2. Unwrap a markdown code fence, if the model wrapped the JSON.
    fence = _FENCE_RE.search(text)
    if fence:
        parsed = _try_load(fence.group(1).strip())
        if parsed is not None:
            return parsed, True
        text = fence.group(1).strip()

    # 3. Isolate the first balanced {...} region (drop leading/trailing prose).
    region = _first_brace_region(text)
    if region:
        for candidate in _repair_candidates(region):
            parsed = _try_load(candidate)
            if parsed is not None:
                return parsed, True

    # 4. Repair ladder on the whole string as a last resort.
    for candidate in _repair_candidates(text):
        parsed = _try_load(candidate)
        if parsed is not None:
            return parsed, True

    return {}, False


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        val = json.loads(text)
        return val if isinstance(val, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _first_brace_region(text: str) -> str | None:
    """Return the substring from the first '{' to its matching '}' (brace-balanced,
    string-aware).  If the closing brace is missing, return through end-of-string
    so the balance-repair step can append the missing braces."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # Unterminated — hand back the remainder for balance repair.
    return text[start:]


def _repair_candidates(text: str):
    """Yield progressively more aggressive repairs of `text`."""
    # a) remove trailing commas before } or ]
    no_trailing = _TRAILING_COMMA_RE.sub(r"\1", text)
    yield no_trailing

    # b) balance unclosed braces/brackets (string-aware count)
    balanced = _balance(no_trailing)
    if balanced != no_trailing:
        yield balanced

    # c) swap single quotes for double quotes, then re-balance.
    #    Only when there are single but no real double-quoted strings, to avoid
    #    corrupting apostrophes inside valid JSON strings.
    if "'" in no_trailing and '"' not in no_trailing:
        swapped = no_trailing.replace("'", '"')
        yield swapped
        yield _balance(_TRAILING_COMMA_RE.sub(r"\1", swapped))


def _balance(text: str) -> str:
    """Append the braces/brackets needed to close an unterminated object/array."""
    depth_curly = 0
    depth_square = 0
    in_str = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth_curly += 1
        elif ch == "}":
            depth_curly = max(0, depth_curly - 1)
        elif ch == "[":
            depth_square += 1
        elif ch == "]":
            depth_square = max(0, depth_square - 1)
    suffix = ""
    if in_str:
        suffix += '"'
    suffix += "]" * depth_square
    suffix += "}" * depth_curly
    return text + suffix
