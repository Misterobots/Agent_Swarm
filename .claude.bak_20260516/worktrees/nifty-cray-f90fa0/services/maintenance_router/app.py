"""FastAPI app for the maintenance router.

Routes Alertmanager webhooks → Redis (agent path) or Postgres queue (human
path), writes an audit row for every classification.

  POST /webhook/alertmanager           — Alertmanager-shaped payload
  GET  /api/maintenance/queue          — pending items for Mission Control UI
  POST /api/maintenance/queue/{id}/ack — human ack/escalate/resolve
  GET  /api/maintenance/audit          — recent dispatch history
  GET  /healthz                        — liveness
  POST /admin/reload-manifest          — re-read manifest.yaml (also SIGHUP)
"""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .audit import Storage
from .classifier import Classifier
from .models import (
    AckRequest,
    AlertmanagerWebhook,
    AuditRow,
    Decision,
    QueueItem,
    QueueStatus,
)
from .redis_bus import RedisCooldownStore, make_redis, publish_system_alert

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("maintenance_router")


MANIFEST_PATH = Path(
    os.getenv("MAINTENANCE_MANIFEST", "/etc/maintenance/manifest.yaml")
)


app = FastAPI(title="Maintenance Router", version="0.1.0")


# Wired in startup so tests can override.
_redis = None
_classifier: Classifier | None = None
_storage: Storage | None = None


@app.on_event("startup")
def _startup() -> None:
    global _redis, _classifier, _storage
    _redis = make_redis()
    _classifier = Classifier(MANIFEST_PATH, RedisCooldownStore(_redis))
    _storage = Storage()
    try:
        signal.signal(signal.SIGHUP, lambda *_: _classifier.reload())  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        # SIGHUP unavailable (Windows) or not in main thread — admin endpoint
        # still works.
        logger.info("SIGHUP not available; use POST /admin/reload-manifest to reload")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/alertmanager", status_code=202)
def webhook_alertmanager(payload: AlertmanagerWebhook) -> dict[str, int]:
    if _classifier is None or _storage is None or _redis is None:
        raise HTTPException(status_code=503, detail="router not initialized")

    counts = {"agent": 0, "human": 0, "suppressed_cooldown": 0, "unmatched": 0}

    for alert in payload.alerts:
        # Resolved alerts: log only, never re-dispatch. Auto_repair_daemon
        # already handles its own resolved-state checks.
        if alert.status == "resolved":
            decision = Decision(route="unmatched", blast_radius="low")
            _storage.write_audit(alert, decision)
            counts["unmatched"] += 1
            continue

        decision = _classifier.classify(alert)

        if decision.route == "agent":
            publish_system_alert(_redis, decision, alert)
            _classifier.mark_dispatched(decision)
            _storage.write_audit(alert, decision)
        elif decision.route == "human":
            queue_id = _storage.enqueue_human(alert, decision)
            _storage.write_audit(alert, decision, queue_item_id=queue_id)
        elif decision.route == "suppressed_cooldown":
            _storage.write_audit(alert, decision)
        else:  # unmatched
            queue_id = _storage.enqueue_human(alert, decision)
            _storage.write_audit(alert, decision, queue_item_id=queue_id)

        counts[decision.route] += 1

    return counts


@app.get("/api/maintenance/queue", response_model=list[QueueItem])
def list_queue(
    status: QueueStatus | None = Query(default="pending"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[QueueItem]:
    if _storage is None:
        raise HTTPException(status_code=503, detail="router not initialized")
    return _storage.list_queue(status=status, limit=limit)


@app.post("/api/maintenance/queue/{item_id}/ack", response_model=QueueItem)
def ack_item(item_id: int, body: AckRequest) -> QueueItem:
    if _storage is None:
        raise HTTPException(status_code=503, detail="router not initialized")
    item = _storage.ack(item_id, body.by, body.status, body.note)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"queue item {item_id} not found or already acked",
        )
    return item


@app.get("/api/maintenance/audit", response_model=list[AuditRow])
def recent_audit(limit: int = Query(default=100, ge=1, le=1000)) -> list[AuditRow]:
    if _storage is None:
        raise HTTPException(status_code=503, detail="router not initialized")
    return _storage.recent_audit(limit=limit)


@app.post("/admin/reload-manifest")
def reload_manifest() -> JSONResponse:
    if _classifier is None:
        raise HTTPException(status_code=503, detail="router not initialized")
    _classifier.reload()
    return JSONResponse({"reloaded": True})
