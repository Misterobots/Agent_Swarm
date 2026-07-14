"""Local, same-day, network-independent memory cache for bmo_brain.

The remote vault's new /v1/extract/queue endpoint queues conversation text instantly
with no LLM call, and a nightly batch job later promotes queued items into the vault's
durable curated memory store. That queue is still a network round-trip away, though —
this module is the local tier that keeps bmo_brain resilient (same-day recall of what
was JUST said) even when the remote vault is slow or completely unreachable.

This is a cache, not a store of record: rows are pruned after 2 days, and the remote
vault remains the durable copy. Every function here must fail soft (log + return
None/[] ) — a SQLite hiccup must never be the reason a request fails.
"""
import datetime
import logging
import os
import re
import sqlite3

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("LOCAL_PENDING_DB", "/app/data/pending.db")

_PRUNE_AFTER_DAYS = 2

# A whole natural-language question almost never appears verbatim in stored
# conversation text, so matching the full query as one substring effectively
# never hits. Match on individual keywords (OR'd together) instead.
_STOPWORDS = {
    "what", "was", "were", "the", "and", "that", "this", "with", "have",
    "from", "your", "about", "again", "does", "did", "for", "are", "you",
    "tell", "know", "there", "when", "where", "which",
}


def _keywords(text: str, limit: int = 8) -> list:
    words = re.findall(r"[a-zA-Z0-9]{4,}", text.lower())
    out = []
    for w in words:
        if w in _STOPWORDS or w in out:
            continue
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation TEXT NOT NULL,
            owner_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def queue_local(conversation: str, owner_id: str) -> None:
    """Insert a same-day pending row and prune anything older than 2 days.

    Best-effort: any sqlite error is logged and swallowed, never raised.
    """
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=_PRUNE_AFTER_DAYS)).isoformat()
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO pending (conversation, owner_id, created_at) VALUES (?, ?, ?)",
                (conversation, owner_id, now),
            )
            conn.execute("DELETE FROM pending WHERE created_at < ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("local_pending.queue_local failed (non-fatal): %s", e)


def search_local(query: str, owner_id: str, limit: int = 5) -> list:
    """Return recent local pending conversation strings for owner_id.

    Matches on individual keywords extracted from the query (OR'd together), not the
    query as one literal substring — a whole spoken question essentially never appears
    verbatim in stored conversation text. Falls back to the most recent rows for that
    owner if no usable keywords are found.

    Best-effort: any sqlite error is logged and an empty list is returned, never raised.
    """
    try:
        conn = _connect()
        try:
            keywords = _keywords(query) if query else []
            if keywords:
                conditions = " OR ".join(["conversation LIKE ?"] * len(keywords))
                params = [owner_id] + [f"%{kw}%" for kw in keywords] + [limit]
                rows = conn.execute(
                    "SELECT conversation FROM pending "
                    f"WHERE owner_id = ? AND ({conditions}) "
                    "ORDER BY created_at DESC LIMIT ?",
                    params,
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT conversation FROM pending "
                    "WHERE owner_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit),
                ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("local_pending.search_local failed (non-fatal): %s", e)
        return []
