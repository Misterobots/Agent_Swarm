"""Governed dispatch helpers for human-requested Mission Control actions.

Interactive actions and alert-driven repairs share the
``maintenance:system_alert`` transport, but they enter it through different
policy boundaries.  Alert actions are classified by ``maintenance_router``;
manual actions are authenticated by the gateway and explicitly allow-listed
here before the host-privileged auto-repair daemon sees them.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from fastapi import HTTPException


SYSTEM_ALERT_QUEUE = "maintenance:system_alert"
ALLOWED_NODES = frozenset({"turing", "hopper", "lovelace"})
JANITOR_NODES = frozenset({"turing", "lovelace"})
_CONTAINER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _normalize_target(node: str, container: str) -> tuple[str, str]:
    node_key = (node or "").strip().lower()
    container_name = (container or "").strip()
    if node_key not in ALLOWED_NODES:
        raise HTTPException(status_code=400, detail=f"Unknown node '{node}'")
    if not _CONTAINER_NAME_RE.fullmatch(container_name):
        raise HTTPException(status_code=400, detail="Invalid container name")
    return node_key, container_name


def dispatch_restart(node: str, container: str, *, requested_by: str) -> dict[str, Any]:
    """Validate and enqueue a manual container restart.

    This call is intentionally asynchronous.  The returned request ID is also
    placed in the queue payload so the daemon's durable action audit can attach
    completion state without changing this API contract later.
    """

    node_key, container_name = _normalize_target(node, container)
    request_id = str(uuid.uuid4())
    actor = requested_by.strip() or "unknown"
    payload = {
        "type": "system_alert",
        "source": "mission_control",
        "payload": {
            "request_id": request_id,
            "requested_by": actor,
            "alertname": "manual_restart",
            "labels": {
                "origin": "mission_control",
                "container": container_name,
                "node": node_key,
                "requested_by": actor,
            },
            "annotations": {
                "summary": f"Manual restart of {container_name} on {node_key} via Mission Control"
            },
            "action": "restart_container",
            "action_args": {"node": node_key, "container": container_name},
        },
    }

    try:
        import redis

        client = redis.Redis(
            host=os.getenv("MAINTENANCE_QUEUE_REDIS_HOST", "redis-turing"),
            port=int(os.getenv("MAINTENANCE_QUEUE_REDIS_PORT", "6379")),
            socket_connect_timeout=3,
        )
        client.rpush(SYSTEM_ALERT_QUEUE, json.dumps(payload))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not dispatch restart to the repair queue: {exc}",
        ) from exc

    return {
        "status": "dispatched",
        "request_id": request_id,
        "node": node_key,
        "container": container_name,
        "detail": "Restart queued to auto_repair_daemon; it executes within a few seconds.",
    }


def dispatch_janitor(
    node: str,
    *,
    requested_by: str,
    mode: str = "dry_run",
    include_stopped: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Queue a governed Docker cleanup on a supported execution node.

    Dry-run is the default.  Destructive execution is intentionally explicit
    and is still limited by the daemon to the allow-listed cleanup classes.
    Named volumes and active containers are never touched by this action.
    """

    node_key = (node or "").strip().lower()
    if node_key not in JANITOR_NODES:
        raise HTTPException(status_code=400, detail=f"Janitor is not available on '{node}'")
    mode_key = (mode or "dry_run").strip().lower()
    if mode_key not in {"dry_run", "execute"}:
        raise HTTPException(status_code=400, detail="mode must be 'dry_run' or 'execute'")
    if mode_key == "execute" and not confirm:
        raise HTTPException(status_code=400, detail="execute mode requires confirm=true")
    if mode_key == "execute" and not include_stopped:
        # The first execution pass only removes build cache.  Removing stopped
        # containers requires a separate explicit opt-in from the UI.
        include_stopped = False

    request_id = str(uuid.uuid4())
    actor = requested_by.strip() or "unknown"
    payload = {
        "type": "system_alert",
        "source": "mission_control",
        "payload": {
            "request_id": request_id,
            "requested_by": actor,
            "alertname": "manual_janitor",
            "labels": {"origin": "mission_control", "node": node_key, "requested_by": actor},
            "annotations": {"summary": f"Janitor {mode_key} on {node_key} via Mission Control"},
            "action": "janitor_cleanup",
            "action_args": {
                "node": node_key,
                "mode": mode_key,
                "include_stopped": str(bool(include_stopped)).lower(),
            },
        },
    }

    try:
        import redis

        client = redis.Redis(
            host=os.getenv("MAINTENANCE_QUEUE_REDIS_HOST", "redis-turing"),
            port=int(os.getenv("MAINTENANCE_QUEUE_REDIS_PORT", "6379")),
            socket_connect_timeout=3,
        )
        client.rpush(SYSTEM_ALERT_QUEUE, json.dumps(payload))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not dispatch janitor: {exc}") from exc

    return {
        "status": "dispatched",
        "request_id": request_id,
        "node": node_key,
        "mode": mode_key,
        "include_stopped": bool(include_stopped),
        "detail": "Janitor queued; dry-run reports reclaimable data, execute prunes only the selected safe classes.",
    }
