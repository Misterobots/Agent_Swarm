"""Small, dependency-free helpers for the gated publish lifecycle."""
from __future__ import annotations


def consume_push_confirm(client, key: str, expected: str) -> bool:
    """Atomically consume a preview token when the Redis client supports it.

    The Lua path avoids a GET/DELETE race between duplicate confirm requests;
    GETDEL is the compatibility fallback for Redis-compatible clients that do
    not expose EVAL.
    """
    script = (
        "local value = redis.call('GET', KEYS[1]); "
        "if value == ARGV[1] then redis.call('DEL', KEYS[1]); return 1 end; "
        "return 0"
    )
    try:
        return bool(client.eval(script, 1, key, expected))
    except (AttributeError, NotImplementedError):
        actual = client.get(key)
        if isinstance(actual, bytes):
            actual = actual.decode("utf-8", errors="replace")
        if actual != expected:
            return False
        getdel = getattr(client, "getdel", None)
        if getdel:
            consumed = getdel(key)
            if isinstance(consumed, bytes):
                consumed = consumed.decode("utf-8", errors="replace")
            return consumed == expected
        client.delete(key)
        return True
