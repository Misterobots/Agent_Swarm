"""Redis transport: cooldown store + agent dispatch queue.

The agent dispatch queue (`maintenance:system_alert`) is consumed by the
extended auto_repair_daemon. The payload format mirrors agents/dispatcher.py
Event.to_json() so it can later be plugged into the existing event bus
without breaking the daemon.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis

from .models import AlertmanagerAlert, Decision

logger = logging.getLogger(__name__)


SYSTEM_ALERT_QUEUE = "maintenance:system_alert"


def make_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis-turing"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )


class RedisCooldownStore:
    """Cooldowns as Redis keys with TTL. `remaining` returns seconds left."""

    def __init__(self, client: redis.Redis):
        self.r = client

    def remaining(self, key: str) -> int:
        ttl = self.r.ttl(key)
        # ttl: -2 = missing, -1 = no expiry, otherwise seconds remaining.
        return max(0, ttl) if ttl and ttl > 0 else 0

    def set(self, key: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self.r.set(key, "1", ex=ttl_seconds)


def publish_system_alert(
    client: redis.Redis,
    decision: Decision,
    alert: AlertmanagerAlert,
) -> None:
    """RPUSH an Event-shaped payload onto the agent queue.

    Mirrors agents/dispatcher.py Event.to_json() so the consumer can decode
    with the existing helper if desired.
    """
    payload: dict[str, Any] = {
        "type": "system_alert",
        "source": "maintenance_router",
        "payload": {
            "alertname": alert.labels.get("alertname"),
            "labels": alert.labels,
            "annotations": alert.annotations,
            "fingerprint": alert.fingerprint,
            "action": decision.action,
            "action_args": decision.action_args,
            "rule_index": decision.rule_index,
            "blast_radius": decision.blast_radius,
        },
    }
    client.rpush(SYSTEM_ALERT_QUEUE, json.dumps(payload))
    logger.info(
        "dispatched alert=%s action=%s args=%s to %s",
        alert.labels.get("alertname"),
        decision.action,
        decision.action_args,
        SYSTEM_ALERT_QUEUE,
    )
