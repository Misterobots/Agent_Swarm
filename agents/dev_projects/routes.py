"""
dev_projects/routes.py — FastAPI router for project CRUD and git-clone provisioning.

Mounts at /v1/dev/projects.

Endpoints:
  GET    /v1/dev/projects                        — list projects for the authenticated user
  POST   /v1/dev/projects                        — create a blank or git-cloned project
  DELETE /v1/dev/projects/{project_id}            — delete a project (removes sandbox dir)
  GET    /v1/dev/projects/{project_id}/publish/preview — what a Publish-to-GitHub click would do
  POST   /v1/dev/projects/{project_id}/publish    — create a GitHub repo + push a blank project
"""
from __future__ import annotations

import os
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

# Same flag main.py's existing gated push/PR flow uses — one "is GitHub write
# access enabled on this deployment" switch, not a second one for Publish.
GITHUB_PUSH_ENABLED = os.getenv("GITHUB_PUSH_ENABLED", "").lower() in ("1", "true", "yes")


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
            docker_exec.provision_project_dir(uid, project_id, git_ref=body.git_ref)
        except RuntimeError as exc:
            logger.error(f"[create_project] provision_project_dir failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Sandbox provisioning failed: {exc}")

    resolved_git_ref = body.git_ref
    if body.source == "git_url":
        if not body.git_url:
            raise HTTPException(status_code=400, detail="git_url is required when source='git_url'")
        if not (body.git_url.startswith("https://") or body.git_url.startswith("http://")):
            raise HTTPException(
                status_code=400,
                detail="git_url must use https:// scheme",
            )
        try:
            # May differ from body.git_ref: git_clone falls back to the
            # repo's actual default branch when the requested ref doesn't
            # exist anywhere (e.g. "main" against a "master"-default repo).
            # Persist what was ACTUALLY checked out, not what was asked for.
            resolved_git_ref = docker_exec.git_clone(uid, project_id, body.git_url, body.git_ref)
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
            git_ref=resolved_git_ref,
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


# ---------------------------------------------------------------------------
# Publish to GitHub — blank (local, git-inited) project -> new GitHub repo
# ---------------------------------------------------------------------------

def _flatten_files(nodes: list, prefix: str = "", out: Optional[list] = None, limit: int = 200) -> list[str]:
    """Flattens list_tree()'s nested FileNode dicts into relative file paths,
    skipping .git entirely — callers don't need to see git internals in a
    "here's what you're about to publish" preview."""
    if out is None:
        out = []
    for n in nodes:
        if len(out) >= limit:
            break
        if n["path"] == ".git" or n["path"].startswith(".git/"):
            continue
        if n["type"] == "file":
            out.append(n["path"])
        elif n["type"] == "dir":
            _flatten_files(n.get("children", []), n["path"], out, limit)
    return out


def _publish_eligibility(project_id: str, uid: str) -> dict:
    """Shared validation for both publish endpoints — never trust the preview
    response as authorization, so publish/ itself re-runs every one of these
    checks rather than assuming preview/ was called first."""
    if not GITHUB_PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="GitHub publish is not enabled")

    project = store.get_project(project_id, uid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("source") != "blank":
        raise HTTPException(status_code=400, detail="Only a blank (local) project can be published")

    if not docker_exec.project_has_content(uid, project_id):
        raise HTTPException(
            status_code=400,
            detail="This project has no content yet beyond its initial commit — add some files first",
        )

    import github_push_tokens
    status = github_push_tokens.get_status(uid)
    if not status or not status.get("connected"):
        raise HTTPException(status_code=400, detail="Connect a GitHub token first (Settings)")

    return project


@router.get("/{project_id}/publish/preview")
async def publish_preview(project_id: str, request: Request):
    """What a Publish click would do — branch, file list, a suggested repo
    name, and which GitHub account it'll publish as. No side effects."""
    uid = _owner(request)
    project = _publish_eligibility(project_id, uid)

    import github_push_tokens
    status = github_push_tokens.get_status(uid)

    tree = docker_exec.list_tree(uid, project_id, None, depth=6)  # already a list of plain dicts
    files = _flatten_files(tree)

    return {
        "branch": project.get("git_ref") or "main",
        "files": files,
        "suggested_repo_name": project["name"],
        "github_username": status.get("github_username"),
    }


class PublishRequest(BaseModel):
    repo_name: str
    private: bool = True


@router.post("/{project_id}/publish")
async def publish_project(project_id: str, body: PublishRequest, request: Request):
    """Create a new GitHub repo and push this project's current working tree
    to it, then flip the project to source="git_url" so future tasks against
    it route through the normal clone path instead of the local-checkout one."""
    uid = _owner(request)
    project = _publish_eligibility(project_id, uid)  # re-validated, not trusted from preview

    repo_name = (body.repo_name or "").strip()
    if not repo_name:
        raise HTTPException(status_code=400, detail="repo_name is required")

    import github_push_tokens
    import github_publish_audit_store
    from tools.github_publish_ops import create_github_repo, push_project_to_remote, GithubPublishError

    token = github_push_tokens.get_token(uid)
    if not token:
        raise HTTPException(status_code=400, detail="Connect a GitHub token first (Settings)")

    branch = project.get("git_ref") or "main"
    github_publish_audit_store.record(project_id, uid, "publish_requested", target_repo=repo_name)

    try:
        repo = create_github_repo(token, repo_name, body.private)
        push_project_to_remote(uid, project_id, repo["clone_url"], branch, token)
    except GithubPublishError as e:
        github_publish_audit_store.record(project_id, uid, "publish_failed", target_repo=repo_name, error=str(e))
        # Name collisions and similar come back from GitHub as 422 — surface
        # as 409 (conflict) rather than a generic 500 so the UI can say
        # "pick a different name" instead of "something went wrong".
        status_code = 409 if "422" in str(e) else 502
        raise HTTPException(status_code=status_code, detail=str(e))

    updated = store.set_git_url(project_id, uid, repo["clone_url"], branch)
    if not updated:
        # Push succeeded but the DB update raced/failed — don't claim total
        # failure (the repo IS live and pushed), but flag it clearly.
        github_publish_audit_store.record(
            project_id, uid, "publish_failed", target_repo=repo_name,
            error="Pushed successfully but failed to update the project record",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Pushed to {repo['html_url']} but failed to update the project record — refresh and check manually",
        )

    github_publish_audit_store.record(project_id, uid, "publish_succeeded", target_repo=repo_name)
    return {"git_url": repo["clone_url"], "html_url": repo["html_url"]}
