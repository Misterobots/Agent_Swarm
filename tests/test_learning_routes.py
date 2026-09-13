"""Feature-gated learning.v1 route tests; no database or live service use."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import learning.routes as routes  # noqa: E402


@pytest.fixture()
def client():
    app = FastAPI()

    @app.middleware("http")
    async def trusted_test_auth(request, call_next):
        # Test-only stand-in for AuthorizationMiddleware's validated state.
        owner = request.headers.get("X-test-owner")
        if owner:
            request.state.owner_id = owner
        return await call_next(request)

    app.include_router(routes.router)
    return TestClient(app)


def _body(**overrides):
    value = {
        "kind": "sft",
        "workspace_id": "memex-core",
        "recipe": {"revision": "sha256:recipe"},
        "model": {"base_revision": "sha256:model"},
        "dataset": {"manifest_id": str(uuid4())},
    }
    value.update(overrides)
    return value


def test_capabilities_advertise_fail_closed_resource_state(client):
    response = client.get("/api/v1/learning/capabilities")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.memex.learning+json")
    body = response.json()
    assert body["schema"] == "learning.v1"
    assert body["operations"]["resource_admission"] is False
    assert body["operations"]["create_job"] is False
    assert body["operations"]["controls"] is False


def test_create_requires_trusted_owner(client):
    response = client.post(
        "/api/v1/learning/jobs",
        json={**_body(), "dry_run": True},
    )
    assert response.status_code == 401


def test_dry_run_is_non_mutating_and_blocks_unknown_resource_admission(client):
    response = client.post(
        "/api/v1/learning/jobs",
        json={**_body(), "dry_run": True},
        headers={"X-test-owner": "alice"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.memex.learning+json")
    body = response.json()
    assert body["ok"] is False
    assert body["resource"]["eligibility"] == "blocked"
    assert body["mutations"] == {
        "job": False,
        "lease": False,
        "eviction": False,
        "worker": False,
        "outbox": False,
    }


def test_create_rejects_without_idempotency_and_resource_admission(client):
    response = client.post(
        "/api/v1/learning/jobs",
        json=_body(),
        headers={"X-test-owner": "alice"},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/learning/jobs",
        json=_body(),
        headers={"X-test-owner": "alice", "Idempotency-Key": "k1"},
    )
    assert response.status_code == 409


def test_client_cannot_self_authorize_resource_admission(client, monkeypatch):
    def forbidden_store():
        pytest.fail("blocked admission must not open the store")

    monkeypatch.setattr(routes, "_store", forbidden_store)
    response = client.post(
        "/api/v1/learning/jobs",
        json=_body(resource={"eligibility": "eligible"}),
        headers={"X-test-owner": "alice", "Idempotency-Key": "k1"},
    )
    assert response.status_code == 409


@pytest.mark.parametrize("suffix", ["", "/events"])
def test_unauthenticated_reads_return_401_without_store_access(client, monkeypatch, suffix):
    def forbidden_store():
        pytest.fail("unauthenticated request must not open the store")

    monkeypatch.setattr(routes, "_store", forbidden_store)
    response = client.get(f"/api/v1/learning/jobs/{uuid4()}{suffix}")
    assert response.status_code == 401


def test_enabled_learning_requires_trusted_scope(client, monkeypatch):
    monkeypatch.setenv("LEARNING_V1_ENABLED", "1")
    response = client.post(
        "/api/v1/learning/jobs",
        json={**_body(), "dry_run": True},
        headers={"X-test-owner": "alice"},
    )
    assert response.status_code == 503


def test_enabled_learning_rejects_cross_scope_request(client, monkeypatch):
    monkeypatch.setenv("LEARNING_V1_ENABLED", "1")
    monkeypatch.setattr(routes, "_scope_values", lambda _request: {"workspace_id": "other-workspace"})
    response = client.post(
        "/api/v1/learning/jobs",
        json={**_body(), "dry_run": True},
        headers={"X-test-owner": "alice"},
    )
    assert response.status_code == 404
