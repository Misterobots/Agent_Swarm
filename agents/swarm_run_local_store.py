"""Project metadata for swarm runs against a "local" (blank, no git_url) dev project.

Sibling to swarm_run_repo_store.py, kept as its own table for the identical
reason that module documents for itself: CREATE-only (never ALTER), so this
never needs to touch swarm_run_repo's schema — in particular its
`git_url TEXT NOT NULL` constraint, which a local/blank-project run has no
value for. See coordination/orchestrator.py's Phase 0 for where each store
gets written (branches on whether repo_context carries a git_url or a
local_path) and coordination/workspace_ops.checkout_local_project for the
actual sandbox seeding this table's rows correspond to.

Owner scoping: same posture as swarm_run_repo_store.py — no owner_id column
by design. Callers MUST verify ownership of the run first via
swarm_run_store.get_run(coordination_id, owner_id) before calling into this
module.
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.swarm_run_local_store")


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
    """Create swarm_run_local_project if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as swarm_run_repo_store.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm_run_local_project (
                        coordination_id  TEXT PRIMARY KEY REFERENCES swarm_runs(coordination_id),
                        dev_project_id   TEXT NOT NULL,
                        source_path      TEXT NOT NULL,
                        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
        logger.info("[SwarmRunLocalStore] Table swarm_run_local_project ready.")
    except Exception as e:
        logger.warning(f"[SwarmRunLocalStore] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Writes — fire-and-forget (never raise into the coordination loop)
# ---------------------------------------------------------------------------

def create(coordination_id: str, dev_project_id: str, source_path: str) -> None:
    """Record which local project a run's workspace was seeded from. Idempotent
    on coordination_id."""
    if not coordination_id or not dev_project_id or not source_path:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO swarm_run_local_project
                        (coordination_id, dev_project_id, source_path)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (coordination_id) DO NOTHING
                    """,
                    (coordination_id, dev_project_id, source_path),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunLocalStore] create failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get(coordination_id: str) -> dict | None:
    """Fetch local-project context for one run."""
    if not coordination_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT coordination_id, dev_project_id, source_path FROM swarm_run_local_project "
                    "WHERE coordination_id=%s",
                    (coordination_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[SwarmRunLocalStore] get failed: {e}")
        return None


def get_many(coordination_ids: list[str]) -> dict[str, dict]:
    """Batch fetch for list views. Returns {coordination_id: {dev_project_id, source_path}}."""
    if not coordination_ids:
        return {}
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT coordination_id, dev_project_id, source_path FROM swarm_run_local_project "
                    "WHERE coordination_id = ANY(%s)",
                    (coordination_ids,),
                )
                return {r["coordination_id"]: dict(r) for r in cur.fetchall()}
    except Exception as e:
        logger.warning(f"[SwarmRunLocalStore] get_many failed: {e}")
        return {}
