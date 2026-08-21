"""Durable, owner-scoped checkpoints for the provider-neutral DevHarness.

The checkpoint is a recovery record, not an instruction to replay side effects.
An interrupted tool remains visible as ``recovery_required`` until a future
resume flow can obtain explicit approval for that tool again.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.dev_harness.checkpoints")

_STATUSES = frozenset({
    "running",
    "awaiting_tools",
    "recovery_required",
    "ready_to_resume",
    "completed",
    "failed",
})


@contextmanager
def _db():
    conn = psycopg2.connect(AGNO_DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_table() -> None:
    """Create the checkpoint table if absent; safe to call at startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dev_harness_checkpoints (
                        session_id TEXT NOT NULL,
                        owner_id   TEXT NOT NULL,
                        status     TEXT NOT NULL,
                        turn       INTEGER NOT NULL DEFAULT 0,
                        data       JSONB NOT NULL,
                        updated_at BIGINT NOT NULL DEFAULT 0,
                        PRIMARY KEY (session_id, owner_id)
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dev_checkpoint_owner "
                    "ON dev_harness_checkpoints (owner_id, updated_at DESC)"
                )
    except Exception as exc:
        logger.warning("[DevCheckpoint] init failed (non-fatal): %s", exc)


def save_checkpoint(
    owner_id: str,
    session_id: str,
    *,
    status: str,
    turn: int,
    data: dict[str, Any],
) -> bool:
    """Persist one complete checkpoint and report whether it was durable."""
    if not owner_id or not session_id or status not in _STATUSES or not isinstance(data, dict):
        return False
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dev_harness_checkpoints
                        (session_id, owner_id, status, turn, data, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id, owner_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        turn = EXCLUDED.turn,
                        data = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        session_id,
                        owner_id,
                        status,
                        int(turn),
                        psycopg2.extras.Json(data),
                        int(time.time()),
                    ),
                )
        return True
    except Exception as exc:
        logger.error(
            "[DevCheckpoint] save failed owner=%s session=%s status=%s: %s",
            owner_id, session_id, status, exc,
        )
        return False


def get_checkpoint(owner_id: str, session_id: str) -> dict[str, Any] | None:
    """Return a checkpoint only for the exact owner/session pair."""
    if not owner_id or not session_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT session_id, owner_id, status, turn, data, updated_at
                    FROM dev_harness_checkpoints
                    WHERE owner_id = %s AND session_id = %s
                    """,
                    (owner_id, session_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.warning("[DevCheckpoint] read failed owner=%s session=%s: %s", owner_id, session_id, exc)
        return None


def list_recovery_required(owner_id: str) -> list[dict[str, Any]]:
    """List incomplete checkpoints for the owner without exposing other users."""
    if not owner_id:
        return []
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT session_id, status, turn, data, updated_at
                    FROM dev_harness_checkpoints
                    WHERE owner_id = %s AND status IN ('running', 'awaiting_tools', 'recovery_required')
                    ORDER BY updated_at DESC
                    """,
                    (owner_id,),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("[DevCheckpoint] recovery list failed owner=%s: %s", owner_id, exc)
        return []
