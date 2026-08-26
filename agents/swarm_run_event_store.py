"""Owner-scoped durable event history for coordinated task runs."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL
from event_contract import stable_event

logger = logging.getLogger("agents.swarm_run_event_store")


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
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS swarm_run_events (
                        coordination_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        seq INTEGER NOT NULL,
                        type TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        created_at BIGINT NOT NULL,
                        PRIMARY KEY (coordination_id, seq)
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_swarm_run_events_owner "
                    "ON swarm_run_events (owner_id, coordination_id, seq)"
                )
    except Exception as exc:
        logger.warning("[SwarmRunEventStore] init failed (non-fatal): %s", exc)


def append_event(coordination_id: str, owner_id: str, seq: int,
                 event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not coordination_id or not owner_id or int(seq) < 0:
        return None
    event = stable_event(coordination_id, int(seq), event_type, payload)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO swarm_run_events
                       (coordination_id, owner_id, seq, type, payload, created_at)
                       VALUES (%s, %s, %s, %s, %s, EXTRACT(EPOCH FROM NOW())::BIGINT)
                       ON CONFLICT (coordination_id, seq) DO NOTHING""",
                    (coordination_id, owner_id, int(seq), event["type"],
                     psycopg2.extras.Json(event["payload"])),
                )
        return event
    except Exception as exc:
        logger.warning("[SwarmRunEventStore] append failed (non-fatal): %s", exc)
        return None


def list_events(coordination_id: str, owner_id: str, *, after_seq: int = -1,
                limit: int = 500) -> list[dict[str, Any]]:
    if not coordination_id or not owner_id:
        return []
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT type, seq, payload, created_at
                       FROM swarm_run_events
                       WHERE coordination_id=%s AND owner_id=%s AND seq>%s
                       ORDER BY seq ASC LIMIT %s""",
                    (coordination_id, owner_id, int(after_seq), min(max(int(limit), 1), 2000)),
                )
                rows = cur.fetchall()
        return [stable_event(coordination_id, int(row["seq"]), row["type"], row["payload"])
                for row in rows]
    except Exception as exc:
        logger.warning("[SwarmRunEventStore] list failed (non-fatal): %s", exc)
        return []
