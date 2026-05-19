"""Server-side conversation persistence for the Hive UI.

Stores full conversation objects (messages, thought traces, tool calls, etc.)
in the agno_memory PostgreSQL database on Hopper, keyed by (id, owner_id).

This enables cross-device session sync — any device signed in to the same
Authentik account sees the same conversation history.
"""

import json
import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.conversation_store")

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_table() -> None:
    """Create hive_conversations table if it doesn't exist. Safe to call on startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hive_conversations (
                        id          TEXT NOT NULL,
                        owner_id    TEXT NOT NULL,
                        data        JSONB NOT NULL,
                        created_at  BIGINT NOT NULL DEFAULT 0,
                        updated_at  BIGINT NOT NULL DEFAULT 0,
                        PRIMARY KEY (id, owner_id)
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_hive_conv_owner "
                    "ON hive_conversations (owner_id, updated_at DESC)"
                )
        logger.info("[ConvStore] Table hive_conversations ready.")
    except Exception as e:
        logger.warning(f"[ConvStore] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_conversation(owner_id: str, conversation: dict) -> None:
    """Upsert a full conversation object for a given owner."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hive_conversations (id, owner_id, data, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id, owner_id) DO UPDATE
                        SET data       = EXCLUDED.data,
                            updated_at = EXCLUDED.updated_at
                    """,
                    (
                        conversation["id"],
                        owner_id,
                        json.dumps(conversation),
                        conversation.get("createdAt", 0),
                        conversation.get("updatedAt", 0),
                    ),
                )
    except Exception as e:
        logger.error(f"[ConvStore] save_conversation failed: {e}")
        raise


def list_conversations(owner_id: str) -> list[dict]:
    """Return all conversations for a given owner, newest first."""
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT data FROM hive_conversations
                    WHERE owner_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (owner_id,),
                )
                rows = cur.fetchall()
                return [row["data"] for row in rows]
    except Exception as e:
        logger.error(f"[ConvStore] list_conversations failed: {e}")
        return []


def delete_conversation(owner_id: str, conv_id: str) -> None:
    """Delete a single conversation. No-op if it doesn't exist."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM hive_conversations WHERE id = %s AND owner_id = %s",
                    (conv_id, owner_id),
                )
    except Exception as e:
        logger.error(f"[ConvStore] delete_conversation failed: {e}")
        raise
