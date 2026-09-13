"""Frozen learning.v1 response-shape checks."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import learning.routes as routes  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client() -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def trusted_test_auth(request, call_next):
        request.state.owner_id = "fixture-owner"
        return await call_next(request)

    app.include_router(routes.router)
    return TestClient(app)


def test_capabilities_match_frozen_fixture():
    body = _client().get("/api/v1/learning/capabilities").json()
    expected = _load("learning_v1_capabilities.json")
    assert {key: body[key] for key in expected} == expected


def test_dry_run_matches_frozen_fixture():
    response = _client().post(
        "/api/v1/learning/jobs",
        json={
            "kind": "sft",
            "workspace_id": "memex-core",
            "dry_run": True,
            "recipe": {"revision": "sha256:recipe"},
            "model": {"base_revision": "sha256:model"},
            "dataset": {"manifest_id": str(uuid4())},
        },
    )
    assert response.status_code == 200
    body = response.json()
    expected = _load("learning_v1_dry_run.json")
    assert {key: body[key] for key in expected} == expected
