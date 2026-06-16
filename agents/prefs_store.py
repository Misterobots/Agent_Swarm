"""Server-side per-user preference blobs for cross-device sync.

Generic key/value JSONB store keyed by (owner_id, namespace) in the agno_memory
PostgreSQL database on Hopper. The first consumer is onboarding
(namespace='onboarding'), which tracks which feature callouts a user has
dismissed so the same set follows them across devices.

Mirrors conversation_store.py. Kept generic (namespace column) so future
cross-device prefs (theme, layout, ...) can reuse this table instead of
spawning a table per feature.
"""

import json
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.prefs_store")

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
    """Create hive_user_prefs if it doesn't exist. Safe to call on startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hive_user_prefs (
                        owner_id    TEXT  NOT NULL,
                        namespace   TEXT  NOT NULL,
                        data        JSONB NOT NULL DEFAULT '{}',
                        updated_at  BIGINT NOT NULL DEFAULT 0,
                        PRIMARY KEY (owner_id, namespace)
                    )
                """)
        logger.info("[PrefsStore] Table hive_user_prefs ready.")
    except Exception as e:
        logger.warning(f"[PrefsStore] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def get_prefs(owner_id: str, namespace: str) -> dict:
    """Return the stored blob for (owner_id, namespace), or {} if absent."""
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT data FROM hive_user_prefs WHERE owner_id=%s AND namespace=%s",
                    (owner_id, namespace),
                )
                row = cur.fetchone()
                return row["data"] if row else {}
    except Exception as e:
        logger.error(f"[PrefsStore] get failed for {owner_id}/{namespace}: {e}")
        return {}


def save_prefs(owner_id: str, namespace: str, data: dict, updated_at: int = 0) -> None:
    """Upsert the blob for (owner_id, namespace)."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hive_user_prefs (owner_id, namespace, data, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (owner_id, namespace) DO UPDATE
                        SET data       = EXCLUDED.data,
                            updated_at = EXCLUDED.updated_at
                    """,
                    (owner_id, namespace, json.dumps(data), updated_at),
                )
    except Exception as e:
        logger.error(f"[PrefsStore] save failed for {owner_id}/{namespace}: {e}")
        raise
