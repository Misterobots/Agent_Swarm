"""
dev_projects/routes.py — FastAPI router for project CRUD and git-clone provisioning.

Mounts at /v1/dev/projects.

Endpoints:
  GET    /v1/dev/projects                  — list projects for the authenticated user
  POST   /v1/dev/projects                  — create a blank or git-cloned project
  DELETE /v1/dev/projects/{project_id}     — delete a project (removes sandbox dir)
"""
from __future__ import annotations

import uuid
import logging
from typing import Literal, Optional

import psycopg2
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from . import store
from dev_files import docker_exec

logger = logging.getLogger("agents.dev_projects.routes")

router = APIRouter(prefix="/v1/dev/projects", tags=["dev-projects"])


# ---------------------------------------------------------------------------
# Auth helper — mirrors goals/routes.py pattern
# ---------------------------------------------------------------------------

def _owner(request: Request) -> str:
    """Pull owner uid from Authentik forward-auth headers, falling back to 'local'.

    Authentik headers are only present when requests flow through Traefik's
    forward-auth middleware (i.e. via memex.shivelymedia.com). Local dev access
    (hive_ui_dev on :3301, direct agent_runtime on :8009) has no such headers
    and falls back to the 'local' bucket so dev workflows aren't blocked.
    """
    return (
        request.headers.get("x-authentik-username")
        or request.headers.get("x-authentik-uid")
        or "local"
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateProjectRequest(BaseModel):
    name: str
    source: Literal["blank", "git_url"]
    git_url: Optional[str] = None
    git_ref: str = "main"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_projects(request: Request):
    """
    List all dev projects owned by the authenticated user.

    Returns: {"projects": [...]}
    """
    uid = _owner(request)
    projects = store.list_projects(uid)
    return {"projects": projects}


@router.post("", status_code=201)
async def create_project(body: CreateProjectRequest, request: Request):
    """
    Create a new dev project.

    - source="blank":    provisions an empty directory skeleton in the sandbox.
    - source="git_url":  clones the given repository (https:// only) into the sandbox.

    Returns the created project record.
    """
    uid = _owner(request)

    # --- Validate name ---
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name must not be empty")
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Project name must not contain slashes")
    if len(name) > 64:
        raise HTTPException(status_code=400, detail="Project name must not exceed 64 characters")

    # --- Generate IDs and path ---
    project_id = str(uuid.uuid4())
    path = f"/workspace/{uid}/{project_id}"

    # --- Provision filesystem ---
    if body.source == "blank":
        try:
            docker_exec.provision_project_dir(uid, project_id)
        except RuntimeError as exc:
            logger.error(f"[create_project] provision_project_dir failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Sandbox provisioning failed: {exc}")

    elif body.source == "git_url":
        if not body.git_url:
            raise HTTPException(status_code=400, detail="git_url is required when source='git_url'")
        if not (body.git_url.startswith("https://") or body.git_url.startswith("http://")):
            raise HTTPException(
                status_code=400,
                detail="git_url must use https:// scheme",
            )
        try:
            docker_exec.git_clone(uid, project_id, body.git_url, body.git_ref)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            logger.error(f"[create_project] git_clone failed: {exc}")
            raise HTTPException(status_code=502, detail="Git clone failed")

    # --- Persist to DB ---
    try:
        project = store.create_project(
            id=project_id,
            uid=uid,
            name=name,
            source=body.source,
            git_url=body.git_url,
            git_ref=body.git_ref,
            path=path,
        )
    except psycopg2.errors.UniqueViolation:
        # Clean up the directory we just created before returning 409
        try:
            docker_exec.exec_in_sandbox("rm", "-rf", path, timeout=30)
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail="A project with that name already exists",
        )

    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request):
    """
    Delete a dev project and remove its sandbox directory.

    Returns 204 No Content on success, 404 if not found or uid mismatch.
    """
    uid = _owner(request)
    proj = store.get_project(project_id, uid)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Best-effort sandbox cleanup — don't let a sandbox error block the DB delete
    try:
        docker_exec.exec_in_sandbox("rm", "-rf", proj["path"], timeout=30)
    except Exception as exc:
        logger.warning(f"[delete_project] sandbox cleanup failed for {proj['path']!r}: {exc}")

    store.delete_project(project_id, uid)

    return Response(status_code=204)
