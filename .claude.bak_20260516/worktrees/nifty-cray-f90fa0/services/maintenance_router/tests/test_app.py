"""End-to-end webhook tests.

Mocks Storage and Redis so we can run without external infrastructure but
still exercise the full app routing logic.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import maintenance_router.app as app_module
from tests.conftest import (
    FakeRedis,
    InMemoryCooldowns,
    InMemoryStorage,
    make_alert,
)
from maintenance_router.classifier import Classifier
from maintenance_router.redis_bus import SYSTEM_ALERT_QUEUE


def _wire(app_module_, manifest_path):
    cooldowns = InMemoryCooldowns()
    app_module_._classifier = Classifier(manifest_path, cooldowns)
    app_module_._storage = InMemoryStorage()
    app_module_._redis = FakeRedis()
    return app_module_._storage, app_module_._redis, cooldowns


def _webhook_payload(*alerts) -> dict:
    return {
        "version": "4",
        "status": "firing",
        "alerts": [
            {
                "status": a.status,
                "labels": a.labels,
                "annotations": a.annotations,
            }
            for a in alerts
        ],
    }


def test_healthz(manifest_path):
    _wire(app_module, manifest_path)
    client = TestClient(app_module.app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_agent_safe_alert_dispatches_to_redis(manifest_path):
    storage, fake_redis, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    alert = make_alert("ServiceDown", job="postgres", severity="critical")
    resp = client.post("/webhook/alertmanager", json=_webhook_payload(alert))
    assert resp.status_code == 202
    assert resp.json() == {
        "agent": 1, "human": 0, "suppressed_cooldown": 0, "unmatched": 0
    }
    assert SYSTEM_ALERT_QUEUE in fake_redis.lists
    assert len(fake_redis.lists[SYSTEM_ALERT_QUEUE]) == 1
    assert len(storage.audit_rows) == 1
    assert storage.audit_rows[0]["route"] == "agent"
    assert storage.queue == []  # nothing in human queue


def test_human_alert_creates_queue_item(manifest_path):
    storage, fake_redis, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    alert = make_alert(
        "ContainerHighMemory", name="agent_runtime", severity="warning"
    )
    resp = client.post("/webhook/alertmanager", json=_webhook_payload(alert))
    assert resp.status_code == 202
    assert resp.json()["human"] == 1
    assert len(storage.queue) == 1
    assert storage.queue[0]["status"] == "pending"
    assert storage.queue[0]["runbook"] == "runbooks/high-memory.md"
    # Audit row should reference the queue item id.
    assert storage.audit_rows[-1]["queue_item_id"] == storage.queue[0]["id"]


def test_cooldown_route_does_not_redispatch(manifest_path):
    storage, fake_redis, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    alert = make_alert("ServiceDown", job="postgres")
    payload = _webhook_payload(alert)

    client.post("/webhook/alertmanager", json=payload)
    second = client.post("/webhook/alertmanager", json=payload)
    assert second.json()["suppressed_cooldown"] == 1
    # Only one Redis dispatch even though we POSTed twice.
    assert len(fake_redis.lists[SYSTEM_ALERT_QUEUE]) == 1


def test_resolved_alert_does_not_dispatch(manifest_path):
    storage, fake_redis, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    payload = {
        "version": "4",
        "status": "resolved",
        "alerts": [{
            "status": "resolved",
            "labels": {"alertname": "ServiceDown", "job": "postgres"},
            "annotations": {},
        }],
    }
    resp = client.post("/webhook/alertmanager", json=payload)
    assert resp.status_code == 202
    assert SYSTEM_ALERT_QUEUE not in fake_redis.lists or not fake_redis.lists[SYSTEM_ALERT_QUEUE]
    assert storage.queue == []


def test_queue_endpoint_returns_pending_items(manifest_path):
    storage, _, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    client.post(
        "/webhook/alertmanager",
        json=_webhook_payload(
            make_alert("ContainerHighMemory", name="x", severity="warning")
        ),
    )
    resp = client.get("/api/maintenance/queue")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["alert_name"] == "ContainerHighMemory"
    assert items[0]["status"] == "pending"


def test_ack_endpoint_marks_item(manifest_path):
    storage, _, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    client.post(
        "/webhook/alertmanager",
        json=_webhook_payload(
            make_alert("ContainerHighMemory", name="x", severity="warning")
        ),
    )
    item_id = storage.queue[0]["id"]

    resp = client.post(
        f"/api/maintenance/queue/{item_id}/ack",
        json={"by": "justin", "status": "acked", "note": "investigating"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acked"
    assert resp.json()["acked_by"] == "justin"

    # Second ack on same item should 404 (already acked).
    second = client.post(
        f"/api/maintenance/queue/{item_id}/ack",
        json={"by": "justin", "status": "acked"},
    )
    assert second.status_code == 404


def test_unmatched_alert_lands_in_human_queue(manifest_path):
    storage, _, _ = _wire(app_module, manifest_path)
    client = TestClient(app_module.app)

    resp = client.post(
        "/webhook/alertmanager",
        json=_webhook_payload(make_alert("CompletelyUnknownAlert")),
    )
    assert resp.status_code == 202
    assert resp.json()["unmatched"] == 1
    assert len(storage.queue) == 1
    assert storage.queue[0]["alert_name"] == "CompletelyUnknownAlert"
