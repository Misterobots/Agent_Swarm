"""Feature-gated HTTP adapter for the proposed learning.v1 contract.

The router is intentionally small until OA-003 identifies the durable schema
owner and OA-001 proves resource ownership. It exposes only capabilities,
dry-run admission, durable job creation, snapshots, and event replay. Control
actions and worker/resource claims remain unavailable until their safety
contracts are implemented.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from learning_contract import (
    LearningContractError,
    validate_job_spec,
)
from learning_store import LearningStore, LearningStoreError


router = APIRouter(prefix="/api/v1/learning", tags=["learning-v1"])


class JobCreateRequest(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID | None = None
    kind: str
    workspace_id: str
    project_id: str | None = None
    session_id: str | None = None
    parent_id: UUID | None = None
    recipe: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)
    dataset: dict[str, Any] = Field(default_factory=dict)
    schedule: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)
    budgets: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


def _store() -> LearningStore:
    """Resolve the store lazily so importing the router never opens a DB."""

    return LearningStore()


def _owner_id(request: Request) -> str:
    """Resolve a trusted owner identity; never accept owner_id from JSON."""

    state_owner = getattr(request.state, "owner_id", None)
    header_owner = request.headers.get("X-authentik-username") or request.headers.get("X-authentik-uid")
    owner = str(state_owner or header_owner or "").strip()
    if not owner:
        raise HTTPException(status_code=401, detail="authenticated owner is required")
    return owner


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    return model.dict(exclude_none=True)


def _learning_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LearningContractError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, LearningStoreError):
        return HTTPException(status_code=503, detail="learning store is unavailable")
    return HTTPException(status_code=500, detail="learning request failed")


@router.get("/capabilities")
async def capabilities():
    return {
        "schema": "learning.v1",
        "server_enabled": os.getenv("LEARNING_V1_ENABLED", "0").lower() in {"1", "true", "yes"},
        "operations": {
            "dry_run": True,
            "create_job": False,
            "get_job": True,
            "events": True,
            "controls": False,
            "schedules": False,
            "resource_admission": False,
            "promotion": False,
        },
        "limits": {"event_page_max": 2000},
        "compatibility": {"legacy_training_routes": "not_adapted"},
    }


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    body: JobCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    owner_id = _owner_id(request)
    body_data = _model_dump(body)
    body_data["owner_id"] = owner_id
    body_data["workspace_id"] = str(body.workspace_id).strip()

    # Admission is intentionally fail-closed until OA-001 is implemented.
    # A dry run is non-mutating: it does not open the store or acquire a lease.
    try:
        normalized = validate_job_spec(body_data)
    except Exception as exc:
        raise _learning_error(exc) from exc

    if body.dry_run:
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "schema": "learning.dry_run.v1",
            "ok": False,
            "job": normalized,
            "resource": {
                "eligibility": "blocked",
                "reason": "resource_admission_unimplemented",
            },
            "mutations": {
                "job": False,
                "lease": False,
                "eviction": False,
                "worker": False,
                "outbox": False,
            },
        })

    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    # Client-supplied eligibility is not an admission decision. Keep all job
    # creation blocked until trusted server-side admission is wired.
    raise HTTPException(status_code=409, detail="resource admission is not available")


@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, request: Request):
    owner_id = _owner_id(request)
    try:
        job = _store().get_job(str(job_id), owner_id)
    except Exception as exc:
        raise _learning_error(exc) from exc
    if not job:
        raise HTTPException(status_code=404, detail="learning job not found")
    return {"schema": "learning.job_response.v1", "job": job}


@router.get("/jobs/{job_id}/events")
async def get_events(
    job_id: UUID,
    request: Request,
    after_seq: int = Query(default=-1, ge=-1),
    limit: int = Query(default=500, ge=1, le=2000),
):
    owner_id = _owner_id(request)
    try:
        events = _store().list_events(str(job_id), owner_id, after_seq=after_seq, limit=limit)
    except Exception as exc:
        raise _learning_error(exc) from exc
    next_after_seq = events[-1]["event_seq"] if events else after_seq
    return {
        "schema": "learning.event_page.v1",
        "events": events,
        "after_seq": after_seq,
        "next_after_seq": next_after_seq,
        "has_more": len(events) == limit,
    }
