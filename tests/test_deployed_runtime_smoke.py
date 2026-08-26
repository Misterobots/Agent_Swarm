"""Opt-in smoke checks for a deployed Agent_Swarm runtime.

Run with ``MEMEX_RUNTIME_URL=https://... pytest -m integration``.  For an
Authentik-protected deployment, pass the already-authenticated session as
``MEMEX_RUNTIME_COOKIE``.  The checks are read-only unless an existing task id
is supplied through ``MEMEX_SMOKE_TASK_ID``.
"""
from __future__ import annotations

import os

import httpx
import pytest


RUNTIME_URL = os.getenv("MEMEX_RUNTIME_URL", "").rstrip("/")
OWNER_ID = os.getenv("MEMEX_OWNER_ID", "").strip()
TASK_ID = os.getenv("MEMEX_SMOKE_TASK_ID", "").strip()
RUNTIME_COOKIE = os.getenv("MEMEX_RUNTIME_COOKIE", "").strip()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not RUNTIME_URL, reason="MEMEX_RUNTIME_URL is not configured"),
]


def _client() -> httpx.Client:
    headers = {"X-authentik-username": OWNER_ID} if OWNER_ID else {}
    if RUNTIME_COOKIE:
        headers["Cookie"] = RUNTIME_COOKIE
    return httpx.Client(base_url=RUNTIME_URL, headers=headers, timeout=15.0)


def test_deployed_mcp_health_and_client_config():
    with _client() as client:
        health = client.get("/api/v1/mcp/health")
        assert health.status_code == 200, health.text[:500]
        health_body = health.json()
        assert health_body.get("status") == "running"
        assert health_body.get("tools_registered") is not None
        assert {"http", "sse", "websocket", "stdio"}.issubset(
            set(health_body.get("transports", []))
        )

        config = client.get("/api/v1/mcp/client-config")
        assert config.status_code == 200, config.text[:500]
        config_body = config.json()
        descriptors = config_body.get("mcpServers") or config_body.get("servers")
        assert isinstance(descriptors, dict) and descriptors


def test_deployed_mcp_sse_discovery():
    with _client() as client:
        with client.stream("GET", "/api/v1/mcp/sse") as response:
            assert response.status_code == 200
            lines = iter(response.iter_lines())
            assert next(lines) == "event: endpoint"


def test_deployed_task_event_polling_is_ordered_and_owner_scoped():
    if not TASK_ID:
        pytest.skip("MEMEX_SMOKE_TASK_ID is not configured")
    if not OWNER_ID:
        pytest.skip("MEMEX_OWNER_ID is required for task-event polling")
    with _client() as client:
        response = client.get(f"/v1/tasks/{TASK_ID}/events", params={"after_seq": -1})
        assert response.status_code == 200, response.text[:500]
        events = response.json().get("events", [])
        assert all(event.get("run_id") == TASK_ID for event in events)
        assert [event.get("seq") for event in events] == sorted(event.get("seq") for event in events)
