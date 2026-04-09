"""
Lightweight token estimation for context window management.
Uses chars/4 heuristic — no tokenizer dependency required.
"""

from config import CONTEXT_WINDOWS


def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def count_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        content = (
            msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        )
        total += count_tokens(str(content)) + 4  # 4-token per-message overhead
    return total


def context_usage(messages: list, model: str) -> dict:
    """Return {'used': int, 'total': int, 'pct': float} for the given model + messages."""
    used = count_messages_tokens(messages)
    total = CONTEXT_WINDOWS.get(model, CONTEXT_WINDOWS["default"])
    return {"used": used, "total": total, "pct": round(used / total, 4)}
