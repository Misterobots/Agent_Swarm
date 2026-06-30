"""Durable swarm-run history for the mobile Codex loop (task board).

Records every swarm/coordinate run + its per-worker (pioneer) status in the
agno_memory PostgreSQL database on Hopper, keyed by coordination_id and scoped
by owner_id. This is what GET /v1/tasks reads — a durable board surviving
agent_runtime restarts and synced across the phone and desktop.

Mirrors conversation_store.py exactly (psycopg2 + _db() context manager,
idempotent init_table on startup, owner-scoped index). All WRITE functions are
fire-and-forget: they swallow errors and log a warning so a DB hiccup can never
break swarm coordination. READ functions return safe defaults on error.

Owner scoping: owner_id is the value from _resolve_owner_id() in main.py
(prefers X-authentik-username). The READ endpoints MUST resolve owner_id the
same way or queries will miss rows.
"""

import logging
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.swarm_run_store")

# Hard cap on persisted diff text — protects the column and the phone payload.
MAX_DIFF_BYTES = 256 * 1024


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


def _now() -> int:
    return int(time.time())


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_table() -> None:
    """Create swarm_runs + swarm_workers if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as conversation_store, so it can
    run against the live agno_memory DB without touching existing schema.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm_runs (
                        coordination_id   TEXT PRIMARY KEY,
                        session_id        TEXT NOT NULL,
                        owner_id          TEXT NOT NULL,
                        title             TEXT,
                        status            TEXT NOT NULL DEFAULT 'running',
                        phase             SMALLINT NOT NULL DEFAULT 0,
                        phase_name        TEXT,
                        workers_total     INT NOT NULL DEFAULT 0,
                        workers_completed INT NOT NULL DEFAULT 0,
                        workers_failed    INT NOT NULL DEFAULT 0,
                        scope             TEXT,
                        preview_url       TEXT,
                        diff_text         TEXT,
                        approval_state    TEXT NOT NULL DEFAULT 'none',
                        summary           TEXT,
                        error             TEXT,
                        started_at        BIGINT NOT NULL DEFAULT 0,
                        updated_at        BIGINT NOT NULL DEFAULT 0,
                        ended_at          BIGINT
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_swarm_runs_owner "
                    "ON swarm_runs (owner_id, started_at DESC)"
                )
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm_workers (
                        worker_id        TEXT PRIMARY KEY,
                        coordination_id  TEXT NOT NULL,
                        role             TEXT,
                        task             TEXT,
                        phase            TEXT,
                        pioneer_name     TEXT,
                        status           TEXT NOT NULL DEFAULT 'pending',
                        output           TEXT,
                        started_at       BIGINT,
                        completed_at     BIGINT
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_swarm_workers_coord "
                    "ON swarm_workers (coordination_id)"
                )
        logger.info("[SwarmRunStore] Tables swarm_runs + swarm_workers ready.")
    except Exception as e:
        logger.warning(f"[SwarmRunStore] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Writes — all fire-and-forget (never raise into the coordination loop)
# ---------------------------------------------------------------------------

def create_run(coordination_id: str, session_id: str, owner_id: str,
               title: str | None, scope: str | None, started_at: int) -> None:
    """Record a run at dispatch. Idempotent on coordination_id."""
    if not coordination_id or not owner_id:
        return
    try:
        now = _now()
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO swarm_runs
                        (coordination_id, session_id, owner_id, title, scope,
                         status, started_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'running', %s, %s)
                    ON CONFLICT (coordination_id) DO NOTHING
                    """,
                    (coordination_id, session_id, owner_id,
                     (title or "")[:200], scope, int(started_at or now), now),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunStore] create_run failed (non-fatal): {e}")


def update_run_phase(coordination_id: str, phase: int, phase_name: str | None) -> None:
    if not coordination_id:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE swarm_runs SET phase=%s, phase_name=%s, updated_at=%s "
                    "WHERE coordination_id=%s",
                    (int(phase or 0), phase_name, _now(), coordination_id),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunStore] update_run_phase failed (non-fatal): {e}")


def upsert_worker(coordination_id: str, worker_id: str, role: str | None,
                  task: str | None, phase: str | None, pioneer_name: str | None,
                  status: str, output: str | None = None,
                  started_at: float | None = None,
                  completed_at: float | None = None) -> None:
    if not coordination_id or not worker_id:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO swarm_workers
                        (worker_id, coordination_id, role, task, phase,
                         pioneer_name, status, output, started_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (worker_id) DO UPDATE SET
                        status       = EXCLUDED.status,
                        output       = COALESCE(EXCLUDED.output, swarm_workers.output),
                        completed_at = COALESCE(EXCLUDED.completed_at, swarm_workers.completed_at)
                    """,
                    (worker_id, coordination_id, role, (task or "")[:500], phase,
                     pioneer_name, status, (output[:2000] if output else None),
                     int(started_at) if started_at else None,
                     int(completed_at) if completed_at else None),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunStore] upsert_worker failed (non-fatal): {e}")


def finish_run(coordination_id: str, status: str, workers_total: int = 0,
               workers_completed: int = 0, workers_failed: int = 0,
               summary: str | None = None, preview_url: str | None = None,
               ended_at: int | None = None, error: str | None = None) -> None:
    if not coordination_id:
        return
    try:
        now = _now()
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE swarm_runs SET
                        status=%s, workers_total=%s, workers_completed=%s,
                        workers_failed=%s, summary=%s, preview_url=%s,
                        error=%s, ended_at=%s, updated_at=%s
                    WHERE coordination_id=%s
                    """,
                    (status, int(workers_total), int(workers_completed),
                     int(workers_failed), (summary[:8000] if summary else None),
                     preview_url, (error[:2000] if error else None),
                     int(ended_at or now), now, coordination_id),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunStore] finish_run failed (non-fatal): {e}")


def set_diff(coordination_id: str, diff_text: str | None) -> None:
    if not coordination_id or not diff_text:
        return
    try:
        encoded = diff_text.encode("utf-8")
        truncated = len(encoded) > MAX_DIFF_BYTES
        if truncated:
            diff_text = encoded[:MAX_DIFF_BYTES].decode("utf-8", "ignore") + "\n[...diff truncated...]"
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE swarm_runs SET diff_text=%s, updated_at=%s WHERE coordination_id=%s",
                    (diff_text, _now(), coordination_id),
                )
    except Exception as e:
        logger.warning(f"[SwarmRunStore] set_diff failed (non-fatal): {e}")


def set_approval(coordination_id: str, owner_id: str, approval_state: str) -> bool:
    """Owner-scoped approval update. Returns True if a row was changed."""
    if not coordination_id or not owner_id:
        return False
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE swarm_runs SET approval_state=%s, updated_at=%s "
                    "WHERE coordination_id=%s AND owner_id=%s",
                    (approval_state, _now(), coordination_id, owner_id),
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.warning(f"[SwarmRunStore] set_approval failed (non-fatal): {e}")
        return False


# ---------------------------------------------------------------------------
# Reads — owner-scoped; return safe defaults on error
# ---------------------------------------------------------------------------

_RUN_LIST_COLS = (
    "coordination_id, session_id, title, status, phase, phase_name, "
    "workers_total, workers_completed, workers_failed, scope, approval_state, "
    "preview_url, started_at, updated_at, ended_at, "
    "(diff_text IS NOT NULL) AS has_diff"
)


def list_runs(owner_id: str, limit: int = 50, running_only: bool = False) -> list[dict]:
    if not owner_id:
        return []
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql = f"SELECT {_RUN_LIST_COLS} FROM swarm_runs WHERE owner_id=%s"
                params: list = [owner_id]
                if running_only:
                    sql += " AND status='running'"
                sql += " ORDER BY started_at DESC LIMIT %s"
                params.append(int(limit))
                cur.execute(sql, tuple(params))
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"[SwarmRunStore] list_runs failed: {e}")
        return []


def get_run(coordination_id: str, owner_id: str) -> dict | None:
    if not coordination_id or not owner_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT {_RUN_LIST_COLS}, summary, error "
                    "FROM swarm_runs WHERE coordination_id=%s AND owner_id=%s",
                    (coordination_id, owner_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[SwarmRunStore] get_run failed: {e}")
        return None


def get_diff(coordination_id: str, owner_id: str) -> str | None:
    """Owner-scoped diff fetch. Returns None if no diff or not owned."""
    if not coordination_id or not owner_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT diff_text FROM swarm_runs WHERE coordination_id=%s AND owner_id=%s",
                    (coordination_id, owner_id),
                )
                row = cur.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.warning(f"[SwarmRunStore] get_diff failed: {e}")
        return None


def get_workers(coordination_id: str, owner_id: str) -> list[dict]:
    """Per-worker rows for a run, owner-verified via join on swarm_runs."""
    if not coordination_id or not owner_id:
        return []
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT w.worker_id, w.role, w.task, w.phase, w.pioneer_name,
                           w.status, w.output, w.started_at, w.completed_at
                    FROM swarm_workers w
                    JOIN swarm_runs r ON r.coordination_id = w.coordination_id
                    WHERE w.coordination_id=%s AND r.owner_id=%s
                    ORDER BY w.started_at ASC NULLS LAST
                    """,
                    (coordination_id, owner_id),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"[SwarmRunStore] get_workers failed: {e}")
        return []
