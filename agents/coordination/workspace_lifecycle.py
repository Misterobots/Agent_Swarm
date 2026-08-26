"""Owner-scoped lifecycle registry for disposable task workspaces."""
from __future__ import annotations

import re
import secrets
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_STATES = frozenset({"created", "entered", "finalized", "exited", "cleaned", "abandoned"})
_TERMINAL = frozenset({"cleaned", "abandoned"})
_NEXT = {
    "created": frozenset({"entered", "exited", "abandoned"}),
    "entered": frozenset({"finalized", "exited", "abandoned"}),
    "finalized": frozenset({"exited", "cleaned", "abandoned"}),
    "exited": frozenset({"cleaned", "abandoned"}),
    "cleaned": frozenset(),
    "abandoned": frozenset(),
}


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


def _check(value: str, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value) or ".." in value:
        raise ValueError(f"invalid {label}")


def init_table() -> None:
    with _db() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS isolated_workspaces (
                worktree_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                task_id TEXT,
                repository_ref TEXT,
                branch TEXT,
                base_branch TEXT,
                lifecycle_status TEXT NOT NULL,
                cleanup_status TEXT NOT NULL DEFAULT 'active',
                diff_ref TEXT,
                lease_until BIGINT NOT NULL,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                UNIQUE(owner_id, session_id, task_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_isolated_workspace_lease ON isolated_workspaces(lease_until, lifecycle_status)")


def create(*, owner_id: str, session_id: str, task_id: str | None = None,
           repository_ref: str | None = None, branch: str | None = None,
           base_branch: str | None = None, lease_seconds: int = 1800) -> dict[str, Any] | None:
    _check(owner_id, _SAFE_ID, "owner_id")
    _check(session_id, _SAFE_ID, "session_id")
    if task_id:
        _check(task_id, _SAFE_ID, "task_id")
    if repository_ref and not repository_ref.startswith(("https://", "http://")):
        raise ValueError("repository_ref must use http(s)")
    if branch:
        _check(branch, _SAFE_REF, "branch")
    if base_branch:
        _check(base_branch, _SAFE_REF, "base_branch")
    now = int(time.time())
    row = {"worktree_id": "wt_" + secrets.token_urlsafe(18), "owner_id": owner_id,
           "session_id": session_id, "task_id": task_id, "repository_ref": repository_ref,
           "branch": branch, "base_branch": base_branch, "lifecycle_status": "created",
           "lease_until": now + max(60, int(lease_seconds)), "created_at": now, "updated_at": now}
    with _db() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO isolated_workspaces
            (worktree_id,owner_id,session_id,task_id,repository_ref,branch,base_branch,
             lifecycle_status,lease_until,created_at,updated_at)
            VALUES (%(worktree_id)s,%(owner_id)s,%(session_id)s,%(task_id)s,%(repository_ref)s,
                    %(branch)s,%(base_branch)s,%(lifecycle_status)s,%(lease_until)s,
                    %(created_at)s,%(updated_at)s) RETURNING *""", row)
        result = cur.fetchone()
        return dict(result) if result else None


def transition(*, worktree_id: str, owner_id: str, status: str,
               diff_ref: str | None = None, lease_seconds: int = 1800) -> dict[str, Any] | None:
    _check(worktree_id, _SAFE_ID, "worktree_id")
    _check(owner_id, _SAFE_ID, "owner_id")
    if status not in _STATES:
        raise ValueError("invalid lifecycle status")
    now = int(time.time())
    with _db() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT lifecycle_status FROM isolated_workspaces WHERE worktree_id=%s AND owner_id=%s FOR UPDATE", (worktree_id, owner_id))
        current = cur.fetchone()
        if not current or status not in _NEXT[current["lifecycle_status"]]:
            return None
        cur.execute("""UPDATE isolated_workspaces SET lifecycle_status=%s,
            diff_ref=COALESCE(%s,diff_ref), cleanup_status=CASE WHEN %s IN ('exited','cleaned','abandoned') THEN %s ELSE cleanup_status END,
            lease_until=%s,updated_at=%s WHERE worktree_id=%s AND owner_id=%s RETURNING *""",
            (status, diff_ref, status, status, now + max(60, int(lease_seconds)), now, worktree_id, owner_id))
        result = cur.fetchone()
        return dict(result) if result else None


def get(*, worktree_id: str, owner_id: str) -> dict[str, Any] | None:
    _check(worktree_id, _SAFE_ID, "worktree_id")
    _check(owner_id, _SAFE_ID, "owner_id")
    with _db() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM isolated_workspaces WHERE worktree_id=%s AND owner_id=%s", (worktree_id, owner_id))
        row = cur.fetchone()
        return dict(row) if row else None


def reap_abandoned(*, now: int | None = None) -> list[str]:
    now = int(time.time()) if now is None else int(now)
    with _db() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE isolated_workspaces SET lifecycle_status='abandoned', cleanup_status='abandoned', updated_at=%s
            WHERE lease_until < %s AND lifecycle_status NOT IN ('cleaned','exited','abandoned') RETURNING worktree_id""", (now, now))
        return [row[0] for row in cur.fetchall()]
