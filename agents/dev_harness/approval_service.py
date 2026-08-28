"""Durable, owner-scoped approval and mutation audit service.

The database is the source of truth.  In-process waiters are deliberately not
persisted; after a restart callers recover the durable pending request.
"""
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
VALID_DECISIONS = frozenset({"pending", "approved", "denied", "expired", "failed"})


class ApprovalUnavailable(RuntimeError):
    pass


def arguments_hash(arguments: Any) -> str:
    """Hash canonical arguments; never persist raw sensitive arguments."""
    encoded = json.dumps(arguments if arguments is not None else {}, sort_keys=True,
                         separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dev_approvals (
                    call_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, session_id TEXT,
                    task_id TEXT, tool_name TEXT NOT NULL, arguments_hash TEXT NOT NULL,
                    permission_mode TEXT NOT NULL, requested_at BIGINT NOT NULL,
                    expires_at BIGINT NOT NULL, decision TEXT NOT NULL,
                    decision_scope TEXT NOT NULL, decided_at BIGINT, decided_by TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dev_approval_audit (
                    id BIGSERIAL PRIMARY KEY, call_id TEXT NOT NULL, owner_id TEXT,
                    session_id TEXT, task_id TEXT, tool_name TEXT NOT NULL,
                    arguments_hash TEXT NOT NULL, permission_mode TEXT NOT NULL,
                    outcome TEXT NOT NULL, actor_id TEXT, occurred_at BIGINT NOT NULL,
                    error TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dev_approvals_owner ON dev_approvals(owner_id, decision)")


def request(*, owner_id: str, session_id: str, task_id: str | None, call_id: str,
            tool_name: str, arguments: Any, permission_mode: str,
            expires_at: int | None = None) -> dict[str, Any]:
    if not owner_id or not session_id or not call_id or not tool_name:
        raise ApprovalUnavailable("malformed approval request")
    now = int(time.time())
    expiry = expires_at or now + 120
    row = {
        "call_id": call_id, "owner_id": owner_id, "session_id": session_id,
        "task_id": task_id, "tool_name": tool_name,
        "arguments_hash": arguments_hash(arguments), "permission_mode": permission_mode,
        "requested_at": now, "expires_at": expiry, "decision": "pending",
        "decision_scope": "once", "decided_at": None, "decided_by": None,
    }
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO dev_approvals
                    (call_id, owner_id, session_id, task_id, tool_name, arguments_hash,
                     permission_mode, requested_at, expires_at, decision, decision_scope)
                    VALUES (%(call_id)s,%(owner_id)s,%(session_id)s,%(task_id)s,%(tool_name)s,
                            %(arguments_hash)s,%(permission_mode)s,%(requested_at)s,%(expires_at)s,
                            'pending','once')
                    ON CONFLICT (call_id) DO UPDATE SET call_id=EXCLUDED.call_id
                    RETURNING *
                """, row)
                found = cur.fetchone()
                if not found:
                    raise ApprovalUnavailable("approval request unavailable")
                return dict(found)
    except ApprovalUnavailable:
        raise
    except Exception as exc:
        logger.error("approval request persistence failed: %s", exc)
        raise ApprovalUnavailable("approval storage unavailable") from exc


def decide(*, call_id: str, owner_id: str, approved: bool, decided_by: str,
           scope: str = "once", is_admin: bool = False) -> dict[str, Any]:
    if scope not in VALID_SCOPES or not call_id or not owner_id or not decided_by:
        raise ApprovalUnavailable("malformed approval decision")
    now = int(time.time())
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM dev_approvals WHERE call_id=%s FOR UPDATE", (call_id,))
                row = cur.fetchone()
                if not row:
                    raise ApprovalUnavailable("approval request not found")
                if row["owner_id"] != owner_id:
                    raise PermissionError("approval request belongs to another owner")
                if row["permission_mode"] == "bypass" and not is_admin:
                    raise PermissionError("administrator authorization required")
                if row["expires_at"] < now and row["decision"] == "pending":
                    cur.execute("UPDATE dev_approvals SET decision='expired', decided_at=%s, decided_by=%s WHERE call_id=%s", (now, decided_by, call_id))
                    outcome = "expired"
                elif row["decision"] != "pending":
                    outcome = row["decision"]
                else:
                    outcome = "approved" if approved else "denied"
                    cur.execute("UPDATE dev_approvals SET decision=%s, decision_scope=%s, decided_at=%s, decided_by=%s WHERE call_id=%s", (outcome, scope, now, decided_by, call_id))
                cur.execute("""INSERT INTO dev_approval_audit
                    (call_id,owner_id,session_id,task_id,tool_name,arguments_hash,permission_mode,outcome,actor_id,occurred_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (call_id,row["owner_id"],row["session_id"],row["task_id"],row["tool_name"],row["arguments_hash"],row["permission_mode"],outcome,decided_by,now))
                return {"decision": outcome, "owner_id": row["owner_id"], "tool_name": row["tool_name"]}
    except (ApprovalUnavailable, PermissionError):
        raise
    except Exception as exc:
        logger.error("approval decision persistence failed: %s", exc)
        raise ApprovalUnavailable("approval storage unavailable") from exc


def get(call_id: str, owner_id: str) -> dict[str, Any] | None:
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM dev_approvals WHERE call_id=%s AND owner_id=%s", (call_id, owner_id))
                row = cur.fetchone()
                if row and row["decision"] == "pending" and row["expires_at"] < int(time.time()):
                    cur.execute("UPDATE dev_approvals SET decision='expired', decided_at=%s WHERE call_id=%s", (int(time.time()), call_id))
                    row["decision"] = "expired"
                return dict(row) if row else None
    except Exception as exc:
        logger.error("approval lookup failed: %s", exc)
        raise ApprovalUnavailable("approval storage unavailable") from exc
