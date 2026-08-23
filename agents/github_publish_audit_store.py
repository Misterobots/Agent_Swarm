"""Audit trail for the "Publish to GitHub" flow (blank dev project -> new
GitHub repo).

Sibling to github_push_audit_store.py, not an extension — that table is
structurally run-scoped (coordination_id TEXT NOT NULL, indexed on it), and a
publish action has no run/coordination_id at all, only a dev_project_id. Same
CREATE-only convention, same DB (AGNO_DB_URL — audit rows correlate with
dev_projects data, not the credential store in github_push_tokens.py's
TEMPLATE_DB_URL).
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.github_publish_audit_store")

# publish_requested | publish_succeeded | publish_failed
_VALID_STAGES = frozenset(["publish_requested", "publish_succeeded", "publish_failed"])


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
    """Create github_publish_audit if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as github_push_audit_store.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS github_publish_audit (
                        id              BIGSERIAL PRIMARY KEY,
                        dev_project_id  TEXT NOT NULL,
                        owner_id        TEXT NOT NULL,
                        stage           TEXT NOT NULL,
                        target_repo     TEXT,
                        error           TEXT,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_publish_audit_project "
                    "ON github_publish_audit (dev_project_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_publish_audit_owner "
                    "ON github_publish_audit (owner_id, created_at DESC)"
                )
        logger.info("[GithubPublishAudit] Table github_publish_audit ready.")
    except Exception as e:
        logger.warning(f"[GithubPublishAudit] init_table failed (non-fatal): {e}")


def record(dev_project_id: str, owner_id: str, stage: str, *,
           target_repo: str | None = None, error: str | None = None) -> None:
    """Append one audit row. Fire-and-forget — never raises into the route handler."""
    if not dev_project_id or not owner_id or stage not in _VALID_STAGES:
        logger.warning(f"[GithubPublishAudit] record: invalid args (stage={stage!r}) — dropped")
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO github_publish_audit
                        (dev_project_id, owner_id, stage, target_repo, error)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (dev_project_id, owner_id, stage, target_repo, (error[:2000] if error else None)),
                )
    except Exception as e:
        logger.warning(f"[GithubPublishAudit] record failed (non-fatal): {e}")


def latest(dev_project_id: str, owner_id: str) -> dict | None:
    """Owner-scoped: most recent audit row for a project."""
    if not dev_project_id or not owner_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT stage, target_repo, error, created_at FROM github_publish_audit "
                    "WHERE dev_project_id=%s AND owner_id=%s "
                    "ORDER BY created_at DESC, id DESC LIMIT 1",
                    (dev_project_id, owner_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[GithubPublishAudit] latest failed: {e}")
        return None
