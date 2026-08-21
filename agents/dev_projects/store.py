"""
dev_projects/store.py — DB layer for the dev_projects table.

Uses the same psycopg2 context-manager pattern as goals/store.py.
Table lives in the public schema (no schema prefix needed).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.dev_projects.store")


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
    """Create dev_projects table and indexes if they don't exist. Safe to call on every startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dev_projects (
                        id          TEXT PRIMARY KEY,
                        uid         TEXT NOT NULL,
                        name        TEXT NOT NULL,
                        source      TEXT NOT NULL,
                        git_url     TEXT,
                        git_ref     TEXT NOT NULL DEFAULT 'main',
                        path        TEXT NOT NULL,
                        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS dev_projects_uid_name_idx
                        ON dev_projects (uid, name)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS dev_projects_uid_idx
                        ON dev_projects (uid)
                """)
        logger.info("Dev projects table ready.")
    except Exception as exc:
        logger.warning(f"Dev projects table init failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_projects(uid: str) -> list[dict]:
    """Return all projects for a given uid, newest first."""
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM dev_projects
                WHERE uid = %s
                ORDER BY created_at DESC
                """,
                (uid,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_project(id: str, uid: str) -> Optional[dict]:
    """
    Return the project with the given id that belongs to uid.
    Returns None if not found OR if the uid doesn't match (cross-uid guard).
    """
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM dev_projects WHERE id = %s AND uid = %s",
                (id, uid),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_project(
    id: str,
    uid: str,
    name: str,
    source: str,
    git_url: Optional[str],
    git_ref: str,
    path: str,
) -> dict:
    """
    Insert a new project row and return the created record.

    Raises psycopg2.errors.UniqueViolation if (uid, name) is already taken.
    The caller (routes.py) translates that into HTTP 409.
    """
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO dev_projects (id, uid, name, source, git_url, git_ref, path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (id, uid, name, source, git_url, git_ref, path),
            )
            row = cur.fetchone()
            return dict(row)


def set_git_url(id: str, uid: str, git_url: str, git_ref: str) -> Optional[dict]:
    """
    Attach a git remote to a project that didn't have one — the "Publish to
    GitHub" flow, for a "blank" project that's been git-inited locally and
    just got pushed to a new GitHub repo. Flips source to "git_url" too, so
    future tasks against this project route through the normal ephemeral-clone
    path (dev_projects.routes/main.py's create_task) instead of the
    local-checkout path — it's a real linked repo now, not a local-only one.

    Owner-scoped like get_project. Returns None if not found / uid mismatch.
    """
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE dev_projects
                SET git_url = %s, git_ref = %s, source = 'git_url'
                WHERE id = %s AND uid = %s
                RETURNING *
                """,
                (git_url, git_ref, id, uid),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_or_create_live_repo_project(uid: str) -> dict:
    """
    Return the one distinguished "live_repo" project for `uid` — the sole,
    deliberate exception where a session container bind-mounts the actual
    live Agent_Swarm repo (see session_sandbox.py's "live_repo" mode and
    Design Decision 3 of the per-session-sandbox plan). Every other project
    (source="blank"/"git_url") always gets a mount-free ephemeral container.

    Lazy get-or-create, not a startup seed: works correctly for any uid
    without hardcoding one, and only ever creates the row the first time a
    given owner actually needs it (chat project picker, or POST /v1/tasks).

    Deterministic id (f"live-repo-{uid}") makes this idempotent under a
    race — ON CONFLICT DO NOTHING, then re-SELECT, rather than relying on
    the caller to serialize. No schema change: `source` is already a
    free-form TEXT column; only the public POST /v1/dev/projects route's
    Pydantic Literal restricts values, and that endpoint never creates this
    row, so the restriction never applies here.
    """
    live_id = f"live-repo-{uid}"
    existing = get_project(live_id, uid)
    if existing:
        return existing

    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO dev_projects (id, uid, name, source, git_url, git_ref, path)
                VALUES (%s, %s, %s, 'live_repo', NULL, 'main', '/workspace')
                ON CONFLICT (id) DO NOTHING
                RETURNING *
                """,
                (live_id, uid, "Agent_Swarm (live)"),
            )
            row = cur.fetchone()
            if row:
                logger.info(f"[dev_projects] Created live_repo project for uid={uid}")
                return dict(row)

    # ON CONFLICT DO NOTHING with no RETURNING row means another concurrent
    # call just created it first — safe to just fetch what's there now.
    return get_project(live_id, uid)  # type: ignore[return-value]


def delete_project(id: str, uid: str) -> bool:
    """
    Delete the project row.  Returns True if a row was deleted, False otherwise
    (not found or uid mismatch — either way the caller gets a 404).
    """
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dev_projects WHERE id = %s AND uid = %s",
                (id, uid),
            )
            return cur.rowcount > 0
