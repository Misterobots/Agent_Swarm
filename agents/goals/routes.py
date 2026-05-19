"""
Goals FastAPI router — mounts at /v1/goals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import store as goals_store
from . import service as goals_service
from .audit import validate_plan, can_complete_goal

router = APIRouter(prefix="/v1/goals", tags=["goals"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner(request: Request) -> str:
    """Best-effort: pull owner from Authentik forward-auth header."""
    return (
        request.headers.get("x-authentik-username")
        or request.headers.get("x-authentik-uid")
        or ""
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class EnsureGoalRequest(BaseModel):
    thread_id: str
    objective: str


class PlanStep(BaseModel):
    step: str
    status: Literal["pending", "in_progress", "completed"] = "pending"
    ord: int


class SetPlanRequest(BaseModel):
    steps: list[PlanStep]


class UpdateStepRequest(BaseModel):
    status: Literal["pending", "in_progress", "completed"]


class AddEvidenceRequest(BaseModel):
    requirement: str
    evidence_type: Literal["command_output", "file_ref", "test_result", "note"]
    evidence_ref: str


class RequirementCheck(BaseModel):
    requirement: str
    required_evidence_types: list[Literal["command_output", "file_ref", "test_result", "note"]]


class AuditRequest(BaseModel):
    checks: list[RequirementCheck]


class UpdateUsageRequest(BaseModel):
    delta_tokens: int = 0
    delta_seconds: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ensure")
async def ensure_goal(body: EnsureGoalRequest, request: Request):
    """Ensure an active goal exists for a thread, creating one if needed."""
    owner = _owner(request)
    goal = goals_service.ensure_goal(body.thread_id, body.objective, owner)
    return {"goal": goal}


@router.get("")
async def list_goals(request: Request, limit: int = 50):
    """List goals (most-recent first)."""
    owner = _owner(request)
    goals = goals_store.list_goals(owner, limit)
    return {"goals": goals}


@router.get("/{goal_id}")
async def get_goal(goal_id: str):
    goal = goals_store.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    steps = goals_store.get_plan_steps(goal_id)
    evidence = goals_store.get_evidence(goal_id)
    return {"goal": goal, "steps": steps, "evidence": evidence}


@router.post("/{goal_id}/complete")
async def complete_goal(goal_id: str):
    """Mark a goal complete (no audit gate — use /audit first if desired)."""
    goal = goals_store.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goals_service.complete_goal(goal_id)
    return {"ok": True}


@router.post("/{goal_id}/pause")
async def pause_goal(goal_id: str):
    goal = goals_store.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goals_service.pause_goal(goal_id)
    return {"ok": True}


@router.post("/{goal_id}/usage")
async def update_usage(goal_id: str, body: UpdateUsageRequest):
    goals_service.update_usage(goal_id, body.delta_tokens, body.delta_seconds)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Plan steps
# ---------------------------------------------------------------------------

@router.put("/{goal_id}/plan")
async def set_plan(goal_id: str, body: SetPlanRequest):
    """Replace the plan for a goal. Validates that at most one step is in_progress."""
    steps_raw = [s.model_dump() for s in body.steps]
    try:
        validate_plan(steps_raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    steps_db = [
        {
            "id": str(uuid.uuid4()),
            "goal_id": goal_id,
            "step": s["step"],
            "status": s["status"],
            "ord": s["ord"],
        }
        for s in steps_raw
    ]
    goals_store.upsert_plan_steps(goal_id, steps_db)
    return {"ok": True, "steps": steps_db}


@router.patch("/{goal_id}/plan/{step_id}")
async def update_step(goal_id: str, step_id: str, body: UpdateStepRequest):
    """Update a single step's status. Validates in_progress constraint."""
    all_steps = goals_store.get_plan_steps(goal_id)
    # Simulate the update to validate
    simulated = [
        {**s, "status": body.status if s["id"] == step_id else s["status"]}
        for s in all_steps
    ]
    try:
        validate_plan(simulated)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    goals_store.update_step_status(step_id, body.status)
    return {"ok": True}


@router.get("/{goal_id}/plan")
async def get_plan(goal_id: str):
    steps = goals_store.get_plan_steps(goal_id)
    return {"steps": steps}


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@router.post("/{goal_id}/evidence")
async def add_evidence(goal_id: str, body: AddEvidenceRequest):
    ev = {
        "id": str(uuid.uuid4()),
        "goal_id": goal_id,
        "requirement": body.requirement,
        "evidence_type": body.evidence_type,
        "evidence_ref": body.evidence_ref,
        "created_at": _now(),
    }
    goals_store.add_evidence(ev)
    return {"ok": True, "evidence": ev}


@router.get("/{goal_id}/evidence")
async def get_evidence(goal_id: str):
    evidence = goals_store.get_evidence(goal_id)
    return {"evidence": evidence}


# ---------------------------------------------------------------------------
# Audit gate
# ---------------------------------------------------------------------------

@router.post("/{goal_id}/audit")
async def audit_goal(goal_id: str, body: AuditRequest):
    """
    Run the completion audit. Returns {ok, missing}.
    If ok=True the goal is safe to complete.
    """
    evidence = goals_store.get_evidence(goal_id)
    checks = [c.model_dump() for c in body.checks]
    result = can_complete_goal(checks, evidence)
    return result
