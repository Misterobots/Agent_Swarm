"""Postgres-backed audit log + human pickup queue.

Two tables, both auto-created on startup so the router has no migration-tool
dependency. Reuses the existing Postgres on Hopper (control_plane).

  maintenance_dispatch  — every classification decision (audit trail)
  maintenance_queue     — items awaiting human pickup in Mission Control
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg2.extensions

from .models import (
    AlertmanagerAlert,
    AuditRow,
    Decision,
    QueueItem,
    QueueStatus,
)

logger = logging.getLogger(__name__)


SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS maintenance_dispatch (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_name      TEXT NOT NULL,
    alert_labels    JSONB NOT NULL,
    alert_payload   JSONB NOT NULL,
    route           TEXT NOT NULL,
    action          TEXT,
    action_args     JSONB,
    rule_index      INTEGER,
    queue_item_id   BIGINT
);
CREATE INDEX IF NOT EXISTS idx_maintenance_dispatch_ts
    ON maintenance_dispatch (ts DESC);

CREATE TABLE IF NOT EXISTS maintenance_queue (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_name      TEXT NOT NULL,
    alert_labels    JSONB NOT NULL,
    alert_payload   JSONB NOT NULL,
    severity        TEXT,
    summary         TEXT,
    description     TEXT,
    blast_radius    TEXT NOT NULL DEFAULT 'medium',
    runbook         TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    acked_at        TIMESTAMPTZ,
    acked_by        TEXT,
    note            TEXT
);
CREATE INDEX IF NOT EXISTS idx_maintenance_queue_status
    ON maintenance_queue (status, created_at DESC);
"""


def make_dsn() -> str:
    dsn = os.getenv("MAINTENANCE_DB_DSN")
    if dsn:
        return dsn
    # Fall back to component env vars; defaults match the Hopper Postgres
    # exposed by control_plane.
    return (
        f"host={os.getenv('MAINTENANCE_DB_HOST', '192.168.2.102')} "
        f"port={os.getenv('MAINTENANCE_DB_PORT', '5432')} "
        f"dbname={os.getenv('MAINTENANCE_DB_NAME', 'maintenance')} "
        f"user={os.getenv('MAINTENANCE_DB_USER', 'maintenance')} "
        f"password={os.getenv('MAINTENANCE_DB_PASSWORD', '')}"
    )


class Storage:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or make_dsn()
        self._ensure_schema()

    @contextmanager
    def _cursor(self) -> Iterator["psycopg2.extensions.cursor"]:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(self.dsn)
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    yield cur
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._cursor() as cur:
            cur.execute(SCHEMA_DDL)
        logger.info("maintenance schema ensured")

    # ── audit ──────────────────────────────────────────────────────────
    def write_audit(
        self,
        alert: AlertmanagerAlert,
        decision: Decision,
        queue_item_id: int | None = None,
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO maintenance_dispatch
                    (alert_name, alert_labels, alert_payload, route,
                     action, action_args, rule_index, queue_item_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    alert.labels.get("alertname", "unknown"),
                    json.dumps(alert.labels),
                    json.dumps(alert.model_dump()),
                    decision.route,
                    decision.action,
                    json.dumps(decision.action_args) if decision.action_args else None,
                    decision.rule_index,
                    queue_item_id,
                ),
            )
            return cur.fetchone()["id"]

    def recent_audit(self, limit: int = 100) -> list[AuditRow]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, alert_name, route, action, rule_index, queue_item_id
                FROM maintenance_dispatch
                ORDER BY ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [AuditRow(**row) for row in cur.fetchall()]

    # ── human queue ────────────────────────────────────────────────────
    def enqueue_human(
        self, alert: AlertmanagerAlert, decision: Decision
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO maintenance_queue
                    (alert_name, alert_labels, alert_payload, severity,
                     summary, description, blast_radius, runbook)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    alert.labels.get("alertname", "unknown"),
                    json.dumps(alert.labels),
                    json.dumps(alert.model_dump()),
                    alert.labels.get("severity"),
                    alert.annotations.get("summary"),
                    alert.annotations.get("description"),
                    decision.blast_radius,
                    decision.runbook,
                ),
            )
            return cur.fetchone()["id"]

    def list_queue(
        self, status: QueueStatus | None = "pending", limit: int = 200
    ) -> list[QueueItem]:
        with self._cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT * FROM maintenance_queue
                    WHERE status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM maintenance_queue ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            return [_row_to_queue_item(row) for row in cur.fetchall()]

    def ack(
        self, item_id: int, by: str, status: QueueStatus, note: str | None
    ) -> QueueItem | None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE maintenance_queue
                SET status = %s, acked_at = NOW(), acked_by = %s, note = %s
                WHERE id = %s AND status = 'pending'
                RETURNING *
                """,
                (status, by, note, item_id),
            )
            row = cur.fetchone()
            return _row_to_queue_item(row) if row else None


def _row_to_queue_item(row: dict) -> QueueItem:
    return QueueItem(
        id=row["id"],
        created_at=row["created_at"],
        alert_name=row["alert_name"],
        alert_labels=row["alert_labels"] if isinstance(row["alert_labels"], dict)
            else json.loads(row["alert_labels"]),
        severity=row.get("severity"),
        summary=row.get("summary"),
        description=row.get("description"),
        blast_radius=row.get("blast_radius") or "medium",
        runbook=row.get("runbook"),
        status=row["status"],
        acked_at=row.get("acked_at"),
        acked_by=row.get("acked_by"),
        note=row.get("note"),
    )
