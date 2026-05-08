"""Pytest fixtures and helpers shared across router tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from maintenance_router.audit import Storage  # noqa: E402
from maintenance_router.classifier import Classifier
from maintenance_router.models import (
    AlertmanagerAlert,
    AuditRow,
    Decision,
    QueueItem,
    QueueStatus,
)


class InMemoryCooldowns:
    """Drop-in for RedisCooldownStore."""

    def __init__(self) -> None:
        self._now: float = 0.0
        self._expiry: dict[str, float] = {}

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def remaining(self, key: str) -> int:
        exp = self._expiry.get(key)
        if exp is None:
            return 0
        rem = exp - self._now
        return int(rem) if rem > 0 else 0

    def set(self, key: str, ttl_seconds: int) -> None:
        self._expiry[key] = self._now + ttl_seconds


class InMemoryStorage:
    """Drop-in for Storage; matches the interface used by app.py."""

    def __init__(self) -> None:
        self.audit_rows: list[dict[str, Any]] = []
        self.queue: list[dict[str, Any]] = []
        self._next_audit_id = 1
        self._next_queue_id = 1

    # ── audit ──
    def write_audit(
        self,
        alert: AlertmanagerAlert,
        decision: Decision,
        queue_item_id: int | None = None,
    ) -> int:
        row = {
            "id": self._next_audit_id,
            "ts": "now",
            "alert_name": alert.labels.get("alertname", "unknown"),
            "route": decision.route,
            "action": decision.action,
            "rule_index": decision.rule_index,
            "queue_item_id": queue_item_id,
        }
        self.audit_rows.append(row)
        self._next_audit_id += 1
        return row["id"]

    def recent_audit(self, limit: int = 100) -> list[AuditRow]:
        return [
            AuditRow(
                id=r["id"],
                ts=__import__("datetime").datetime.utcnow(),
                alert_name=r["alert_name"],
                route=r["route"],
                action=r["action"],
                rule_index=r["rule_index"],
                queue_item_id=r["queue_item_id"],
            )
            for r in list(reversed(self.audit_rows))[:limit]
        ]

    # ── queue ──
    def enqueue_human(
        self, alert: AlertmanagerAlert, decision: Decision
    ) -> int:
        item = {
            "id": self._next_queue_id,
            "created_at": __import__("datetime").datetime.utcnow(),
            "alert_name": alert.labels.get("alertname", "unknown"),
            "alert_labels": alert.labels,
            "severity": alert.labels.get("severity"),
            "summary": alert.annotations.get("summary"),
            "description": alert.annotations.get("description"),
            "blast_radius": decision.blast_radius,
            "runbook": decision.runbook,
            "status": "pending",
            "acked_at": None,
            "acked_by": None,
            "note": None,
        }
        self.queue.append(item)
        self._next_queue_id += 1
        return item["id"]

    def list_queue(
        self, status: QueueStatus | None = "pending", limit: int = 200
    ) -> list[QueueItem]:
        items = [i for i in self.queue if status is None or i["status"] == status]
        items = list(reversed(items))[:limit]
        return [QueueItem(**i) for i in items]

    def ack(
        self, item_id: int, by: str, status: QueueStatus, note: str | None
    ) -> QueueItem | None:
        for item in self.queue:
            if item["id"] == item_id and item["status"] == "pending":
                item["status"] = status
                item["acked_by"] = by
                item["note"] = note
                item["acked_at"] = __import__("datetime").datetime.utcnow()
                return QueueItem(**item)
        return None


class FakeRedis:
    """Minimal RPUSH-only fake for the system_alert queue."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])


@pytest.fixture
def manifest_path(tmp_path):
    """Repo manifest copied into tmp so tests can mutate it without leaking."""
    repo_manifest = (
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "config" / "maintenance" / "manifest.yaml"
    )
    target = tmp_path / "manifest.yaml"
    target.write_bytes(repo_manifest.read_bytes())
    return target


@pytest.fixture
def cooldowns():
    return InMemoryCooldowns()


@pytest.fixture
def classifier(manifest_path, cooldowns):
    return Classifier(manifest_path, cooldowns)


@pytest.fixture
def storage():
    return InMemoryStorage()


@pytest.fixture
def fake_redis():
    return FakeRedis()


def make_alert(alertname: str, **labels: str) -> AlertmanagerAlert:
    labels = {"alertname": alertname, **labels}
    return AlertmanagerAlert(status="firing", labels=labels, annotations={})
