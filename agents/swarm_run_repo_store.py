"""Repo/branch metadata for swarm runs created via the "New Task" composer.

Companion table to swarm_run_store.py's swarm_runs, keyed by coordination_id.
Kept as its own table (not new columns on swarm_runs) for the same reason
swarm_run_store documents: CREATE-only (never ALTER), so it can run against
the live agno_memory DB without touching existing schema.

local_branch/bundle_data/bundle_size are written later, at run completion, by
the gated-push flow (a separate phase) — included in the schema up front so
that flow never needs an ALTER either.

Owner scoping: this table has no owner_id column by design. Callers MUST
verify ownership of the run first via swarm_run_store.get_run(coordination_id,
owner_id) (or list_runs) before calling into this module — get()/get_many()
here are trusted to be called only for coordination_ids the caller already
knows the requester owns.
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.swarm_run_repo_store")


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
    """Create swarm_run_repo if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as swarm_run_store.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm_run_repo (
                        coordination_id  TEXT PRIMARY KEY REFERENCES swarm_runs(coordination_id),
                        dev_project_id   TEXT,
                        git_url          TEXT NOT NULL,
                        branch           TEXT NOT NULL,
                        base_branch      TEXT NOT NULL DEFAULT 'main',
                        local_branch     TEXT,
                        bundle_data      BYTEA,
                        bundle_size      INT,
                        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
        logger.info("[SwarmRunRepoStore] Table swarm_run_repo ready.")
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Writes — fire-and-forget (never raise into the coordination loop)
# ---------------------------------------------------------------------------

def create(coordination_id: str, dev_project_id: str | None, git_url: str,
           branch: str, base_branch: str = "main") -> None:
    """Record the repo/branch context for a run. Idempotent on coordination_id."""
    if not coordination_id or not git_url or not branch:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO swarm_run_repo
                        (coordination_id, dev_project_id, git_url, branch, base_branch)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (coordination_id) DO NOTHING
                    """,
                    (coordination_id, dev_project_id, git_url, branch, base_branch),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] create failed (non-fatal): {e}")


def set_local_branch(coordination_id: str, local_branch: str, bundle_data: bytes | None = None) -> None:
    """Record the finalized local branch (+ its git-bundle export) at run
    completion — see orchestrator.py's call to workspace_ops.finalize_task_branch."""
    if not coordination_id or not local_branch:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE swarm_run_repo SET local_branch=%s, bundle_data=%s, bundle_size=%s "
                    "WHERE coordination_id=%s",
                    (local_branch, psycopg2.Binary(bundle_data) if bundle_data else None,
                     len(bundle_data) if bundle_data else None, coordination_id),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] set_local_branch failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get(coordination_id: str) -> dict | None:
    """Fetch repo context for one run (excludes bundle_data — see get_bundle)."""
    if not coordination_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT coordination_id, dev_project_id, git_url, branch, base_branch, "
                    "local_branch, bundle_size FROM swarm_run_repo WHERE coordination_id=%s",
                    (coordination_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] get failed: {e}")
        return None


def get_bundle(coordination_id: str) -> bytes | None:
    """Fetch the raw bundle bytes for one run. Separate from get() since this
    is a large binary payload that most callers (list/detail views) never
    need — only the push flow (agents/tools/github_push_ops.py) calls this."""
    if not coordination_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT bundle_data FROM swarm_run_repo WHERE coordination_id=%s",
                    (coordination_id,),
                )
                row = cur.fetchone()
                return bytes(row[0]) if row and row[0] is not None else None
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] get_bundle failed: {e}")
        return None


def get_many(coordination_ids: list[str]) -> dict[str, dict]:
    """Batch fetch for list views. Returns {coordination_id: {git_url, branch, ...}}."""
    if not coordination_ids:
        return {}
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT coordination_id, dev_project_id, git_url, branch FROM swarm_run_repo "
                    "WHERE coordination_id = ANY(%s)",
                    (coordination_ids,),
                )
                return {r["coordination_id"]: dict(r) for r in cur.fetchall()}
    except Exception as e:
        logger.warning(f"[SwarmRunRepoStore] get_many failed: {e}")
        return {}
