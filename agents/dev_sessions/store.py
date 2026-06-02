"""
Dev sessions store — thin DB layer over the dev_sessions table.
Uses the same psycopg2 / context-manager pattern as goals/store.py.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.dev_sessions.store")


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
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_tables() -> None:
    """Create dev_sessions table if it doesn't exist. Safe to call on every startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dev_sessions (
                        id            TEXT PRIMARY KEY,
                        uid           TEXT NOT NULL,
                        project_id    TEXT,
                        active_file   TEXT,
                        view_mode     TEXT NOT NULL DEFAULT 'code',
                        selected_node TEXT NOT NULL DEFAULT 'workspace',
                        open_goal_ids JSONB NOT NULL DEFAULT '[]',
                        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        archived_at   TIMESTAMPTZ
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS dev_sessions_uid_idx
                        ON dev_sessions(uid)
                """)
        logger.info("Dev sessions table ready.")
    except Exception as exc:
        logger.warning(f"Dev sessions table init failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_sessions(uid: str) -> list[dict]:
    """Return all non-archived sessions for a given uid, newest first."""
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM dev_sessions
                WHERE uid = %s AND archived_at IS NULL
                ORDER BY updated_at DESC
                """,
                (uid,),
            )
            rows = cur.fetchall()
            return [_row_to_dict(r) for r in rows]


def get_session(id: str, uid: str) -> Optional[dict]:
    """Return session by id. Returns None if not found or uid mismatch."""
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM dev_sessions WHERE id = %s AND uid = %s",
                (id, uid),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def create_session(id: str, uid: str, **fields) -> dict:
    """Insert a new session row and return it."""
    project_id    = fields.get("project_id")
    active_file   = fields.get("active_file")
    view_mode     = fields.get("view_mode", "code")
    selected_node = fields.get("selected_node", "workspace")
    open_goal_ids = fields.get("open_goal_ids", [])

    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO dev_sessions
                    (id, uid, project_id, active_file, view_mode,
                     selected_node, open_goal_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    id,
                    uid,
                    project_id,
                    active_file,
                    view_mode,
                    selected_node,
                    json.dumps(open_goal_ids),
                ),
            )
            row = cur.fetchone()
            return _row_to_dict(row)


def update_session(id: str, uid: str, **fields) -> Optional[dict]:
    """
    Update mutable fields on a session. Only provided keys are changed.
    Returns the updated row, or None if not found / uid mismatch.
    """
    # Build a partial UPDATE — only set columns that were explicitly passed
    allowed = {
        "project_id", "active_file", "view_mode",
        "selected_node", "open_goal_ids",
    }
    set_clauses = []
    params: list = []

    for col in allowed:
        if col in fields:
            val = fields[col]
            if col == "open_goal_ids":
                val = json.dumps(val)
            set_clauses.append(f"{col} = %s")
            params.append(val)

    if not set_clauses:
        # Nothing to change — just return the current row
        return get_session(id, uid)

    # Always bump updated_at
    set_clauses.append("updated_at = NOW()")
    params.extend([id, uid])

    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE dev_sessions
                SET {', '.join(set_clauses)}
                WHERE id = %s AND uid = %s AND archived_at IS NULL
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def archive_session(id: str, uid: str) -> bool:
    """Soft-delete: set archived_at. Returns True if a row was updated."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dev_sessions
                SET archived_at = NOW(), updated_at = NOW()
                WHERE id = %s AND uid = %s AND archived_at IS NULL
                """,
                (id, uid),
            )
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    """Convert a RealDictRow to a plain dict, serialising timestamps."""
    d = dict(row)
    # Convert datetime objects to ISO strings so they're JSON-serialisable
    for key in ("created_at", "updated_at", "archived_at"):
        if key in d and d[key] is not None:
            d[key] = d[key].isoformat()
    # open_goal_ids comes back as a Python list from psycopg2 JSONB — keep it
    return d
