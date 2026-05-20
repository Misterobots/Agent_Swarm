"""
Goals store — thin DB layer over the swarm.goals tables.
Uses the same psycopg2 / context-manager pattern as conversation_store.py.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL

logger = logging.getLogger("agents.goals.store")


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
    """Create goals tables if they don't exist. Safe to call on every startup."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm.goals (
                        id               TEXT PRIMARY KEY,
                        thread_id        TEXT NOT NULL,
                        owner_id         TEXT NOT NULL DEFAULT '',
                        objective        TEXT NOT NULL,
                        status           TEXT NOT NULL CHECK (status IN ('active','complete','paused')),
                        created_at       TEXT NOT NULL,
                        updated_at       TEXT NOT NULL,
                        completed_at     TEXT,
                        tokens_used      INTEGER DEFAULT 0,
                        time_used_seconds INTEGER DEFAULT 0
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_goals_thread_status
                        ON swarm.goals (thread_id, status)
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm.goal_plan_steps (
                        id       TEXT PRIMARY KEY,
                        goal_id  TEXT NOT NULL REFERENCES swarm.goals(id) ON DELETE CASCADE,
                        step     TEXT NOT NULL,
                        status   TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
                        ord      INTEGER NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm.goal_evidence (
                        id             TEXT PRIMARY KEY,
                        goal_id        TEXT NOT NULL REFERENCES swarm.goals(id) ON DELETE CASCADE,
                        requirement    TEXT NOT NULL,
                        evidence_type  TEXT NOT NULL
                            CHECK (evidence_type IN ('command_output','file_ref','test_result','note')),
                        evidence_ref   TEXT NOT NULL,
                        created_at     TEXT NOT NULL
                    )
                """)
        logger.info("Goals tables ready.")
    except Exception as exc:
        logger.warning(f"Goals table init failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# Goals CRUD
# ---------------------------------------------------------------------------

def create_goal(goal: dict) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swarm.goals
                    (id, thread_id, owner_id, objective, status,
                     created_at, updated_at, tokens_used, time_used_seconds)
                VALUES (%(id)s, %(thread_id)s, %(owner_id)s, %(objective)s, %(status)s,
                        %(created_at)s, %(updated_at)s, %(tokens_used)s, %(time_used_seconds)s)
                """,
                goal,
            )


def get_active_by_thread(thread_id: str, owner_id: str = "") -> Optional[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM swarm.goals
                WHERE thread_id = %s AND status = 'active'
                  AND (owner_id = %s OR owner_id = '')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id, owner_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_goal(goal_id: str) -> Optional[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM swarm.goals WHERE id = %s", (goal_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def list_goals(owner_id: str = "", limit: int = 50) -> list[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM swarm.goals
                WHERE (owner_id = %s OR owner_id = '')
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (owner_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def set_status(goal_id: str, status: str, now: str, completed_at: Optional[str] = None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE swarm.goals
                SET status = %s, updated_at = %s, completed_at = %s
                WHERE id = %s
                """,
                (status, now, completed_at, goal_id),
            )


def update_usage(goal_id: str, delta_tokens: int, delta_seconds: int, now: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE swarm.goals
                SET tokens_used = tokens_used + %s,
                    time_used_seconds = time_used_seconds + %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (delta_tokens, delta_seconds, now, goal_id),
            )


# ---------------------------------------------------------------------------
# Plan steps CRUD
# ---------------------------------------------------------------------------

def upsert_plan_steps(goal_id: str, steps: list[dict]) -> None:
    """Replace all plan steps for a goal."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM swarm.goal_plan_steps WHERE goal_id = %s", (goal_id,))
            for step in steps:
                cur.execute(
                    """
                    INSERT INTO swarm.goal_plan_steps (id, goal_id, step, status, ord)
                    VALUES (%(id)s, %(goal_id)s, %(step)s, %(status)s, %(ord)s)
                    """,
                    step,
                )


def update_step_status(step_id: str, status: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE swarm.goal_plan_steps SET status = %s WHERE id = %s",
                (status, step_id),
            )


def get_plan_steps(goal_id: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM swarm.goal_plan_steps WHERE goal_id = %s ORDER BY ord",
                (goal_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Evidence CRUD
# ---------------------------------------------------------------------------

def add_evidence(ev: dict) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swarm.goal_evidence
                    (id, goal_id, requirement, evidence_type, evidence_ref, created_at)
                VALUES (%(id)s, %(goal_id)s, %(requirement)s,
                        %(evidence_type)s, %(evidence_ref)s, %(created_at)s)
                """,
                ev,
            )


def get_evidence(goal_id: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM swarm.goal_evidence WHERE goal_id = %s ORDER BY created_at",
                (goal_id,),
            )
            return [dict(r) for r in cur.fetchall()]
