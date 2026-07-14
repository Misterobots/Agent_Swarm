"""Learned area/entity phrase->target_id mappings for Friday's Home Assistant resolver.

Pure storage layer — normalization and matching live in hass_resolver.py, which always
passes an already-normalized phrase_norm in. Kept as its own SQLite file (not a table in
local_pending.py's pending.db) because the two have different lifecycles: pending.db rows
are pruned after 2 days as disposable cache, while a learned phrase->area mapping ("second
floor" -> the Upstairs area) does not go stale on a fixed schedule and must survive
indefinitely until corrected.

Same fail-soft contract as local_pending.py: every public function wraps its body in
try/except sqlite3.Error, logs, and returns None/[]/False rather than raising — a SQLite
hiccup must never be the reason a voice command fails.
"""
import datetime
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("HASS_SYNONYMS_DB", "/app/data/hass_synonyms.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hass_synonyms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            phrase_norm TEXT NOT NULL,
            phrase_raw TEXT NOT NULL,
            target_id TEXT NOT NULL,
            method TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            hit_count INTEGER NOT NULL DEFAULT 1,
            owner_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(kind, phrase_norm, owner_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hass_synonyms_lookup "
        "ON hass_synonyms(kind, phrase_norm, owner_id)"
    )
    return conn


def lookup(kind: str, phrase_norm: str, owner_id: str) -> str | None:
    """Return the stored target_id for this normalized phrase, or None on a miss/error."""
    if not phrase_norm:
        return None
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT target_id FROM hass_synonyms WHERE kind = ? AND phrase_norm = ? AND owner_id = ?",
                (kind, phrase_norm, owner_id or ""),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("hass_synonyms.lookup failed (non-fatal): %s", e)
        return None


def learn(kind: str, phrase_raw: str, phrase_norm: str, target_id: str, method: str,
          confidence: float, owner_id: str) -> None:
    """Upsert a phrase->target_id mapping. A later call for the same (kind, phrase_norm,
    owner_id) always overwrites the earlier one — this is deliberate, since a real
    correction should always win over an earlier guess."""
    if not (kind and phrase_norm and target_id):
        return
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO hass_synonyms
                    (kind, phrase_norm, phrase_raw, target_id, method, confidence,
                     hit_count, owner_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(kind, phrase_norm, owner_id) DO UPDATE SET
                    phrase_raw = excluded.phrase_raw,
                    target_id = excluded.target_id,
                    method = excluded.method,
                    confidence = excluded.confidence,
                    hit_count = hit_count + 1,
                    updated_at = excluded.updated_at
                """,
                (kind, phrase_norm, phrase_raw, target_id, method, confidence,
                 owner_id or "", now, now),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("hass_synonyms.learn failed (non-fatal): %s", e)


def all_synonyms(owner_id: str) -> list:
    """Every learned mapping for owner_id, most-recently-updated first. Debugging/
    inspection only — never on a hot path."""
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT kind, phrase_norm, phrase_raw, target_id, method, confidence, "
                "hit_count, updated_at FROM hass_synonyms WHERE owner_id = ? "
                "ORDER BY updated_at DESC",
                (owner_id or "",),
            ).fetchall()
            cols = ("kind", "phrase_norm", "phrase_raw", "target_id", "method",
                    "confidence", "hit_count", "updated_at")
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("hass_synonyms.all_synonyms failed (non-fatal): %s", e)
        return []
