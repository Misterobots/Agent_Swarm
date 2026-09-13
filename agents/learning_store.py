"""Durable PostgreSQL store for the proposed overnight learning contract.

This module is deliberately not imported by application startup yet.  The
existing ``swarm.*`` schema owner and additive migration boundary must be
resolved first (OA-003).  When wired, writes must fail closed: there is no
in-memory production fallback for jobs, leases, idempotency, or events.

The store follows the existing Core PostgreSQL store conventions but improves
the safety properties needed for learning:

* owner/workspace scoping is mandatory;
* job creation and its initial event are one transaction;
* idempotency keys are fingerprinted and replay the original response;
* event sequence allocation locks the durable job row;
* state updates use an expected state version;
* database errors are raised to the API boundary instead of becoming fake
  success or an empty healthy state.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping
from uuid import uuid4

import psycopg2
import psycopg2.extras

from config import AGNO_DB_URL
from learning_contract import (
    IdempotencyConflict,
    LearningContractError,
    make_event,
    require_scope,
    require_uuid,
    validate_budgets,
    validate_job_spec,
    validate_transition,
)

logger = logging.getLogger("agents.learning_store")


class LearningStoreError(RuntimeError):
    """The durable learning store could not complete an operation."""


class LearningStore:
    """Postgres-backed store; construction has no network side effects."""

    MUTABLE_SNAPSHOT_FIELDS = frozenset({
        "worker_id", "resource", "budgets", "progress", "checkpoint", "retry",
        "freshness", "blocking_reason", "provenance", "evaluation", "candidate",
    })

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or AGNO_DB_URL

    @contextmanager
    def _db(self) -> Iterator[Any]:
        try:
            conn = psycopg2.connect(self.dsn)
        except Exception as exc:
            raise LearningStoreError("learning store is unavailable") from exc
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_tables(self) -> None:
        """Create only the new learning tables; never alter legacy tables.

        This method is explicit by design.  It is not called from FastAPI
        startup until OA-003 identifies the authorized schema/migration owner.
        """

        with self._db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_jobs (
                        job_id TEXT PRIMARY KEY,
                        experiment_id TEXT,
                        owner_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        project_id TEXT,
                        session_id TEXT,
                        parent_id TEXT,
                        worker_id TEXT,
                        kind TEXT NOT NULL,
                        status TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        state_version BIGINT NOT NULL DEFAULT 0,
                        event_cursor BIGINT NOT NULL DEFAULT -1,
                        recipe JSONB NOT NULL DEFAULT '{}'::jsonb,
                        model JSONB NOT NULL DEFAULT '{}'::jsonb,
                        dataset JSONB NOT NULL DEFAULT '{}'::jsonb,
                        budgets JSONB NOT NULL DEFAULT '{}'::jsonb,
                        schedule JSONB NOT NULL DEFAULT '{}'::jsonb,
                        resource JSONB NOT NULL DEFAULT '{}'::jsonb,
                        progress JSONB NOT NULL DEFAULT '{}'::jsonb,
                        checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
                        retry JSONB NOT NULL DEFAULT '{}'::jsonb,
                        freshness JSONB NOT NULL DEFAULT '{}'::jsonb,
                        blocking_reason TEXT,
                        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
                        evaluation JSONB NOT NULL DEFAULT '{}'::jsonb,
                        candidate JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_attempts (
                        attempt_id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES learning_jobs(job_id),
                        owner_id TEXT NOT NULL,
                        attempt_number INT NOT NULL,
                        status TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        worker_id TEXT,
                        lease_generation BIGINT,
                        heartbeat_at TIMESTAMPTZ,
                        checkpoint_id TEXT,
                        error JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (job_id, attempt_number)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_events (
                        job_id TEXT NOT NULL REFERENCES learning_jobs(job_id),
                        owner_id TEXT NOT NULL,
                        event_seq BIGINT NOT NULL,
                        event_id TEXT NOT NULL UNIQUE,
                        experiment_id TEXT,
                        attempt_id TEXT,
                        kind TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (job_id, event_seq)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_idempotency (
                        owner_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        job_id TEXT,
                        response JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (owner_id, idempotency_key)
                    )
                """)
                # These are additive changes to the new learning tables only;
                # legacy swarm tables remain outside this explicit initializer.
                cur.execute("""
                    ALTER TABLE learning_jobs
                    ADD COLUMN IF NOT EXISTS event_cursor BIGINT NOT NULL DEFAULT -1
                """)
                cur.execute("""
                    ALTER TABLE learning_jobs
                    ADD COLUMN IF NOT EXISTS budgets JSONB NOT NULL DEFAULT '{}'::jsonb
                """)
                cur.execute("""
                    ALTER TABLE learning_events
                    ADD COLUMN IF NOT EXISTS experiment_id TEXT
                """)
                cur.execute("""
                    UPDATE learning_jobs AS jobs
                    SET event_cursor = COALESCE(
                        (SELECT MAX(events.event_seq)
                         FROM learning_events AS events
                         WHERE events.job_id = jobs.job_id
                           AND events.owner_id = jobs.owner_id), -1)
                    WHERE jobs.event_cursor = -1
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_learning_jobs_owner_updated
                    ON learning_jobs (owner_id, updated_at DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_learning_events_owner_job_seq
                    ON learning_events (owner_id, job_id, event_seq)
                """)

    def create_job(
        self,
        spec: Mapping[str, Any],
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[dict[str, Any], bool]:
        """Create one queued job or replay an identical idempotent request.

        Returns ``(snapshot, replayed)``.  A key collision with a different
        fingerprint raises ``IdempotencyConflict``.
        """

        normalized = validate_job_spec(spec)
        owner_id = normalized["owner_id"]
        key = str(idempotency_key or "").strip()
        fingerprint = str(request_fingerprint or "").strip()
        if not key or not fingerprint:
            raise LearningContractError("idempotency_key and request_fingerprint are required")

        normalized.setdefault("status", "queued")
        normalized.setdefault("phase", "queued")
        normalized.setdefault("state_version", 0)

        with self._db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO learning_idempotency
                           (owner_id, idempotency_key, request_fingerprint, response)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (owner_id, idempotency_key) DO NOTHING
                       RETURNING owner_id""",
                    (owner_id, key, fingerprint, psycopg2.extras.Json({"_pending": True})),
                )
                reserved = cur.fetchone() is not None
                if not reserved:
                    cur.execute(
                        """SELECT request_fingerprint, response
                           FROM learning_idempotency
                           WHERE owner_id=%s AND idempotency_key=%s
                           FOR UPDATE""",
                        (owner_id, key),
                    )
                    prior = cur.fetchone()
                    if not prior:
                        raise LearningStoreError("idempotency reservation disappeared")
                    if prior["request_fingerprint"] != fingerprint:
                        raise IdempotencyConflict("idempotency key reused with a different request")
                    response = dict(prior["response"])
                    if response.get("_pending"):
                        raise LearningStoreError("idempotency reservation is incomplete")
                    return response, True

                snapshot = self._snapshot_defaults(normalized)
                snapshot["event_cursor"] = 0
                cur.execute(
                    """INSERT INTO learning_jobs (
                           job_id, experiment_id, owner_id, workspace_id,
                           project_id, session_id, parent_id, worker_id, kind,
                           status, phase, state_version, event_cursor, recipe,
                           model, dataset, budgets, schedule, resource, progress,
                           checkpoint, retry,
                           freshness, blocking_reason, provenance, evaluation,
                           candidate)
                       VALUES (%(job_id)s, %(experiment_id)s, %(owner_id)s,
                           %(workspace_id)s, %(project_id)s, %(session_id)s,
                           %(parent_id)s, %(worker_id)s, %(kind)s, %(status)s,
                           %(phase)s, %(state_version)s, %(event_cursor)s,
                           %(recipe)s, %(model)s, %(dataset)s, %(budgets)s,
                           %(schedule)s, %(resource)s,
                           %(progress)s, %(checkpoint)s, %(retry)s,
                           %(freshness)s, %(blocking_reason)s, %(provenance)s,
                           %(evaluation)s, %(candidate)s)""",
                    self._job_params(snapshot),
                )
                event = self._event_for_snapshot(snapshot, 0, "job_created", "queued", {})
                self._insert_event(cur, snapshot, event)
                response = {"job": snapshot, "event": event}
                cur.execute(
                    """UPDATE learning_idempotency
                       SET job_id=%s, response=%s
                       WHERE owner_id=%s AND idempotency_key=%s""",
                    (snapshot["job_id"], psycopg2.extras.Json(response), owner_id, key),
                )
                return response, False

    def get_job(self, job_id: str, owner_id: str) -> dict[str, Any] | None:
        job_id = require_uuid(job_id, "job_id")
        owner_id = require_scope(owner_id, "owner_id")
        with self._db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM learning_jobs WHERE job_id=%s AND owner_id=%s",
                    (job_id, owner_id),
                )
                row = cur.fetchone()
                return self._row_to_snapshot(dict(row)) if row else None

    def list_events(
        self,
        job_id: str,
        owner_id: str,
        *,
        after_seq: int = -1,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        job_id = require_uuid(job_id, "job_id")
        owner_id = require_scope(owner_id, "owner_id")
        bounded_limit = min(max(int(limit), 1), 2000)
        with self._db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT event_id, job_id, owner_id, event_seq, experiment_id,
                              attempt_id, kind, phase, payload, occurred_at
                       FROM learning_events
                       WHERE job_id=%s AND owner_id=%s AND event_seq>%s
                       ORDER BY event_seq ASC LIMIT %s""",
                    (job_id, owner_id, int(after_seq), bounded_limit),
                )
                return [self._row_to_event(dict(row)) for row in cur.fetchall()]

    def transition_job(
        self,
        job_id: str,
        owner_id: str,
        *,
        expected_version: int,
        status: str,
        phase: str,
        patch: Mapping[str, Any] | None = None,
        event_kind: str = "state_changed",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Atomically update state and append its event under a row lock."""

        job_id = require_uuid(job_id, "job_id")
        owner_id = require_scope(owner_id, "owner_id")
        if not isinstance(expected_version, int) or expected_version < 0:
            raise LearningContractError("expected_version must be a non-negative integer")
        if status not in {"queued", "running", "paused", "retry_wait", "blocked", "failed", "cancelled", "completed"}:
            raise LearningContractError(f"unsupported learning status: {status}")
        if phase not in {"queued", "preflight", "preparing", "training", "checkpointing", "evaluating", "exporting", "awaiting_review", "restoring", "done"}:
            raise LearningContractError(f"unsupported learning phase: {phase}")

        patch = dict(patch or {})
        unknown_patch = set(patch) - self.MUTABLE_SNAPSHOT_FIELDS
        if unknown_patch:
            raise LearningContractError(
                "unsupported learning snapshot fields: " + ", ".join(sorted(unknown_patch))
            )
        if "budgets" in patch:
            patch["budgets"] = validate_budgets(patch["budgets"])
        with self._db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM learning_jobs WHERE job_id=%s AND owner_id=%s FOR UPDATE",
                    (job_id, owner_id),
                )
                row = cur.fetchone()
                if not row:
                    raise LearningStoreError("learning job not found")
                current = dict(row)
                if int(current["state_version"]) != expected_version:
                    raise LearningStoreError("learning job state version conflict")
                validate_transition(current["status"], status)

                new_version = expected_version + 1
                snapshot = self._row_to_snapshot(current)
                snapshot.update(patch)
                snapshot.update({
                    "job_id": job_id,
                    "owner_id": owner_id,
                    "status": status,
                    "phase": phase,
                    "state_version": new_version,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                next_seq = self._next_event_seq(cur, job_id, owner_id)
                snapshot["event_cursor"] = next_seq
                params = self._job_params(snapshot)
                cur.execute(
                    """UPDATE learning_jobs SET status=%(status)s, phase=%(phase)s,
                           state_version=%(state_version)s, event_cursor=%(event_cursor)s,
                           worker_id=%(worker_id)s, resource=%(resource)s,
                           budgets=%(budgets)s,
                           progress=%(progress)s, checkpoint=%(checkpoint)s,
                           retry=%(retry)s, freshness=%(freshness)s,
                           blocking_reason=%(blocking_reason)s,
                           provenance=%(provenance)s, evaluation=%(evaluation)s,
                           candidate=%(candidate)s, updated_at=NOW()
                       WHERE job_id=%(job_id)s AND owner_id=%(owner_id)s""",
                    params,
                )
                event = self._event_for_snapshot(
                    snapshot, next_seq,
                    event_kind, phase, {"status": status, "state_version": new_version},
                )
                self._insert_event(cur, snapshot, event)
                return snapshot, event

    @staticmethod
    def _snapshot_defaults(spec: Mapping[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        snapshot = dict(spec)
        snapshot.setdefault("experiment_id", None)
        snapshot.setdefault("project_id", None)
        snapshot.setdefault("session_id", None)
        snapshot.setdefault("parent_id", None)
        snapshot.setdefault("worker_id", None)
        snapshot.setdefault("event_cursor", -1)
        snapshot.setdefault("recipe", {})
        snapshot.setdefault("model", {})
        snapshot.setdefault("dataset", {})
        snapshot["budgets"] = validate_budgets(snapshot.get("budgets", {}))
        snapshot.setdefault("schedule", {})
        snapshot.setdefault("resource", {"eligibility": "pending", "lease_generation": 0})
        snapshot.setdefault("progress", {"unit": "step", "current": 0, "total": None})
        snapshot.setdefault("checkpoint", {"latest_id": None, "age_sec": None, "recovery_point": None})
        snapshot.setdefault("retry", {"used": 0, "max": 0, "next_at": None, "reason": None})
        snapshot.setdefault("freshness", {"observed_at": now, "heartbeat_at": None})
        snapshot.setdefault("blocking_reason", None)
        snapshot.setdefault("provenance", {"source_run_ids": [], "memory_ids": [], "pioneer_ids": []})
        snapshot.setdefault("evaluation", {"report_id": None, "decision": "pending"})
        snapshot.setdefault("candidate", {"candidate_id": None, "state": "none"})
        snapshot.setdefault("created_at", now)
        snapshot.setdefault("updated_at", now)
        return snapshot

    @staticmethod
    def _job_params(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        params = dict(snapshot)
        for field in ("recipe", "model", "dataset", "budgets", "schedule", "resource", "progress", "checkpoint", "retry", "freshness", "provenance", "evaluation", "candidate"):
            params[field] = psycopg2.extras.Json(snapshot.get(field) or {})
        return params

    @staticmethod
    def _row_to_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for field in ("recipe", "model", "dataset", "budgets", "schedule", "resource", "progress", "checkpoint", "retry", "freshness", "provenance", "evaluation", "candidate"):
            value = result.get(field)
            if isinstance(value, str):
                try:
                    result[field] = json.loads(value)
                except json.JSONDecodeError:
                    result[field] = {}
            elif value is None:
                result[field] = {}
        for field in ("created_at", "updated_at"):
            if hasattr(result.get(field), "isoformat"):
                result[field] = result[field].isoformat()
        return result

    @staticmethod
    def _event_for_snapshot(snapshot: Mapping[str, Any], seq: int, kind: str, phase: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = make_event(
            job_id=snapshot["job_id"],
            event_seq=seq,
            kind=kind,
            phase=phase,
            payload=payload,
            experiment_id=snapshot.get("experiment_id"),
        )
        return event

    @staticmethod
    def _insert_event(cur: Any, snapshot: Mapping[str, Any], event: Mapping[str, Any]) -> None:
        cur.execute(
            """INSERT INTO learning_events
               (job_id, owner_id, event_seq, event_id, experiment_id, attempt_id,
                kind, phase, payload, occurred_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                snapshot["job_id"], snapshot["owner_id"], event["event_seq"],
                event["event_id"], event.get("experiment_id"),
                event.get("attempt_id"), event["kind"], event["phase"],
                psycopg2.extras.Json(event["payload"]), event["occurred_at"],
            ),
        )

    @staticmethod
    def _next_event_seq(cur: Any, job_id: str, owner_id: str) -> int:
        cur.execute(
            "SELECT COALESCE(MAX(event_seq), -1) + 1 AS next_seq FROM learning_events WHERE job_id=%s AND owner_id=%s",
            (job_id, owner_id),
        )
        return int(cur.fetchone()["next_seq"])

    @staticmethod
    def _row_to_event(row: Mapping[str, Any]) -> dict[str, Any]:
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        occurred_at = row.get("occurred_at")
        if hasattr(occurred_at, "isoformat"):
            occurred_at = occurred_at.isoformat()
        return {
            "schema": "learning.event.v1",
            "event_id": row["event_id"],
            "job_id": row["job_id"],
            "experiment_id": row.get("experiment_id"),
            "attempt_id": row.get("attempt_id"),
            "event_seq": int(row["event_seq"]),
            "kind": row["kind"],
            "phase": row["phase"],
            "occurred_at": occurred_at,
            "payload": payload,
        }
