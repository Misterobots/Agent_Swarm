"""Audit trail for the gated GitHub push/PR flow (Phase D of the Codex-task-
composer plan).

Lives in the same database as swarm_runs/swarm_run_repo (AGNO_DB_URL) — NOT
alongside github_push_tokens.py's table (a different database, TEMPLATE_DB_URL
— see that module's docstring). Audit rows correlate with task/run data far
more than with the credential store, and this way listing a run's push
history never needs a cross-database query.

The existing agents/security/audit_logger.py is a JSON-file structured
logger, not a DB table — not queryable, not owner-scoped, and not currently
tied to git actions at all. This is a real, queryable, owner-scoped trail,
matching swarm_run_store.py's style (psycopg2 + _db() context manager,
idempotent init_table(), fire-and-forget writes that swallow+log).
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.github_push_audit_store")

# preview_shown | confirm_attempted | push_succeeded | push_failed
_VALID_STAGES = frozenset(["preview_shown", "confirm_attempted", "push_succeeded", "push_failed"])


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
    """Create github_push_audit if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as swarm_run_store.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS github_push_audit (
                        id              BIGSERIAL PRIMARY KEY,
                        coordination_id TEXT NOT NULL,
                        owner_id        TEXT NOT NULL,
                        stage           TEXT NOT NULL,
                        target_repo     TEXT,
                        target_branch   TEXT,
                        base_branch     TEXT,
                        pr_number       INT,
                        pr_url          TEXT,
                        error           TEXT,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_push_audit_coord "
                    "ON github_push_audit (coordination_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_push_audit_owner "
                    "ON github_push_audit (owner_id, created_at DESC)"
                )
        logger.info("[GithubPushAudit] Table github_push_audit ready.")
    except Exception as e:
        logger.warning(f"[GithubPushAudit] init_table failed (non-fatal): {e}")


def record(coordination_id: str, owner_id: str, stage: str, *,
           target_repo: str | None = None, target_branch: str | None = None,
           base_branch: str | None = None, pr_number: int | None = None,
           pr_url: str | None = None, error: str | None = None) -> None:
    """Append one audit row. Fire-and-forget — never raises into the route handler."""
    if not coordination_id or not owner_id or stage not in _VALID_STAGES:
        logger.warning(f"[GithubPushAudit] record: invalid args (stage={stage!r}) — dropped")
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO github_push_audit
                        (coordination_id, owner_id, stage, target_repo, target_branch,
                         base_branch, pr_number, pr_url, error)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (coordination_id, owner_id, stage, target_repo, target_branch,
                     base_branch, pr_number, pr_url, (error[:2000] if error else None)),
                )
    except Exception as e:
        logger.warning(f"[GithubPushAudit] record failed (non-fatal): {e}")


def latest(coordination_id: str, owner_id: str) -> dict | None:
    """Owner-scoped: most recent audit row for a run (for push/status polling)."""
    if not coordination_id or not owner_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT stage, target_repo, target_branch, base_branch, pr_number, "
                    "pr_url, error, created_at FROM github_push_audit "
                    "WHERE coordination_id=%s AND owner_id=%s "
                    "ORDER BY created_at DESC, id DESC LIMIT 1",
                    (coordination_id, owner_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[GithubPushAudit] latest failed: {e}")
        return None
