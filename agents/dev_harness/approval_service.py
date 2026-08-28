"""Durable, owner-scoped approval decisions for DevHarness tool calls."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.dev_harness.approval")

VALID_SCOPES = frozenset({"once", "session", "workspace"})
VALID_DECISIONS = frozenset({"approved", "denied", "expired", "failed"})
VALID_MODES = frozenset({"default", "plan", "acceptEdits", "bypass"})


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


def arguments_hash(arguments: Any) -> str:
    """Hash canonical arguments; raw secrets never enter the audit table."""
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def init_table() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dev_approval_requests (
                    call_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    session_id TEXT,
                    task_id TEXT,
                    tool_name TEXT NOT NULL,
                    arguments_hash TEXT NOT NULL,
                    permission_mode TEXT NOT NULL,
                    requested_at BIGINT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    decision TEXT,
                    decision_scope TEXT,
                    decided_at BIGINT,
                    decided_by TEXT,
                    audit JSONB NOT NULL DEFAULT '[]'::jsonb
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dev_approval_owner ON dev_approval_requests(owner_id, requested_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dev_approval_scope ON dev_approval_requests(owner_id, session_id, task_id, tool_name)")


def request_approval(*, owner_id: str, call_id: str, tool_name: str,
                     arguments: Any, permission_mode: str = "default",
                     session_id: str | None = None, task_id: str | None = None,
                     ttl_seconds: int = 120) -> dict[str, Any] | None:
    if not owner_id or not call_id or not tool_name or permission_mode not in VALID_MODES:
        return None
    now = int(time.time())
    row = {
        "owner_id": owner_id, "session_id": session_id, "task_id": task_id,
        "call_id": call_id, "tool_name": tool_name,
        "arguments_hash": arguments_hash(arguments), "permission_mode": permission_mode,
        "requested_at": now, "expires_at": now + max(1, int(ttl_seconds)),
    }
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO dev_approval_requests
                    (call_id, owner_id, session_id, task_id, tool_name, arguments_hash,
                     permission_mode, requested_at, expires_at)
                    VALUES (%(call_id)s, %(owner_id)s, %(session_id)s, %(task_id)s,
                            %(tool_name)s, %(arguments_hash)s, %(permission_mode)s,
                            %(requested_at)s, %(expires_at)s)
                    ON CONFLICT (call_id) DO NOTHING RETURNING *
                """, row)
                result = cur.fetchone()
                if result:
                    return dict(result)
                cur.execute("SELECT * FROM dev_approval_requests WHERE call_id=%s", (call_id,))
                existing = cur.fetchone()
                return dict(existing) if existing else None
    except Exception:
        logger.exception("approval request persistence failed")
        return None


def get_request(owner_id: str, call_id: str) -> dict[str, Any] | None:
    """Return an approval only when both owner and call id match."""
    if not owner_id or not call_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM dev_approval_requests WHERE owner_id=%s AND call_id=%s",
                    (owner_id, call_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        logger.exception("approval lookup failed")
        return None


def get_request_any_owner(call_id: str) -> dict[str, Any] | None:
    """Lookup minimal metadata to distinguish 404 from cross-owner 403."""
    if not call_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT call_id, owner_id, decision, expires_at FROM dev_approval_requests WHERE call_id=%s",
                    (call_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        return None


def decide(*, owner_id: str, call_id: str, decision: str, decided_by: str,
           scope: str = "once", now: int | None = None) -> dict[str, Any] | None:
    """Atomically resolve an approval; retries return the original decision."""
    if decision not in VALID_DECISIONS or scope not in VALID_SCOPES or not owner_id or not decided_by:
        return None
    now = int(time.time()) if now is None else int(now)
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM dev_approval_requests WHERE owner_id=%s AND call_id=%s FOR UPDATE", (owner_id, call_id))
                row = cur.fetchone()
                if not row:
                    return None
                if row["decision"]:
                    return dict(row)
                if int(row["expires_at"]) <= now:
                    decision, scope = "expired", "once"
                audit = list(row.get("audit") or [])
                audit.append({"event": decision, "at": now, "by": decided_by, "scope": scope})
                cur.execute("""
                    UPDATE dev_approval_requests
                    SET decision=%s, decision_scope=%s, decided_at=%s, decided_by=%s, audit=%s
                    WHERE call_id=%s AND owner_id=%s AND decision IS NULL RETURNING *
                """, (decision, scope, now, decided_by, psycopg2.extras.Json(audit), call_id, owner_id))
                updated = cur.fetchone()
                return dict(updated) if updated else dict(row)
    except Exception:
        logger.exception("approval decision persistence failed")
        return None


def audit_outcome(*, owner_id: str, call_id: str, event: str, by: str = "system") -> bool:
    """Append a non-decision outcome such as failed execution or expiration."""
    if event not in VALID_DECISIONS or not owner_id or not call_id:
        return False
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE dev_approval_requests SET audit = audit || %s::jsonb WHERE call_id=%s AND owner_id=%s",
                    (json.dumps([{"event": event, "at": int(time.time()), "by": by}]), call_id, owner_id),
                )
        return True
    except Exception:
        logger.exception("approval outcome persistence failed")
        return False
