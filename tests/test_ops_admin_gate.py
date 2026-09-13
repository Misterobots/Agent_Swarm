"""Host-affecting Mission Control routes require administrator authority."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import ops.routes as routes


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_restart_requires_admin_group(monkeypatch):
    monkeypatch.setattr(
        routes,
        "dispatch_restart",
        lambda *args, **kwargs: {"status": "dispatched"},
    )

    response = _client().post("/api/v1/ops/fleet/turing/agent_runtime/restart")

    assert response.status_code == 403


def test_janitor_accepts_explicit_admin_group(monkeypatch):
    monkeypatch.setattr(
        routes,
        "dispatch_janitor",
        lambda *args, **kwargs: {"status": "dispatched"},
    )

    response = _client().post(
        "/api/v1/ops/janitor",
        json={"node": "lovelace", "mode": "dry_run"},
        headers={"x-authentik-groups": "users,memex-admin"},
    )

    assert response.status_code == 200
