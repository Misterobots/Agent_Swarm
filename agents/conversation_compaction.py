"""Provider-neutral conversation compaction helpers."""
from __future__ import annotations

from typing import Any


def compact_messages(messages: list[dict[str, Any]], summary: str, *,
                     keep_messages: int = 3) -> list[dict[str, Any]]:
    """Replace older context with a summary while retaining the tail.

    The helper is intentionally independent of the model call that produces
    ``summary``.  This makes the boundary safe to test and keeps compaction
    behavior identical after a resumed or provider-switched session.
    """
    if len(messages) <= 6:
        return list(messages)
    keep = max(int(keep_messages), 1)
    return [
        {"role": "system", "content": f"[Conversation Summary]: {summary}"},
        *messages[-keep:],
    ]
