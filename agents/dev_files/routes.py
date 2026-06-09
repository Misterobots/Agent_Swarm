"""
dev_files/routes.py — FastAPI router for filesystem operations.

Mounts at /v1/dev/files.

Endpoints:
    GET  /v1/dev/files/tree     — list directory tree
    GET  /v1/dev/files/content  — read file content
    PUT  /v1/dev/files/content  — write file content
"""
from __future__ import annotations

import logging
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import AGNO_DB_URL
from . import docker_exec

logger = logging.getLogger("dev_files.routes")

router = APIRouter(prefix="/v1/dev/files", tags=["dev-files"])


# ---------------------------------------------------------------------------
# Auth helper — mirrors pattern from goals/routes.py
# ---------------------------------------------------------------------------

def _owner(request: Request) -> str:
    """Pull owner uid from Authentik forward-auth headers, falling back to 'local'.

    Authentik headers are only present when requests flow through Traefik's
    forward-auth middleware. Local dev access has no such headers and falls back
    to the 'local' bucket so projects created via dev_projects (also 'local')
    remain readable.
    """
    return (
        request.headers.get("x-authentik-username")
        or request.headers.get("x-authentik-uid")
        or "local"
    )


# ---------------------------------------------------------------------------
# Project ownership validation
# ---------------------------------------------------------------------------

def _get_project(project_id: str, uid: str) -> Optional[dict]:
    """
    Return project dict if found and owned by uid, else None.
    Handles the case where the dev_projects table doesn't exist yet (F3
    may not have run) by catching ProgrammingError and returning None —
    this surfaces as a 404, which is correct behaviour until F3 merges.
    """
    try:
        conn = psycopg2.connect(AGNO_DB_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, uid, name, created_at
                    FROM swarm.dev_projects
                    WHERE id = %s AND uid = %s
                    """,
                    (project_id, uid),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()
    except psycopg2.errors.UndefinedTable:
        # F3 hasn't created the table yet — treat as not found
        logger.debug("dev_projects table does not exist yet (F3 pending)")
        return None
    except psycopg2.ProgrammingError as exc:
        logger.debug("dev_projects lookup programming error (F3 pending?): %s", exc)
        return None
    except Exception as exc:
        logger.warning("dev_projects lookup failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class WriteFileBody(BaseModel):
    path: str
    content: str
    encoding: str = "utf8"  # "utf8" | "base64"


# ---------------------------------------------------------------------------
# GET /v1/dev/files/tree
# ---------------------------------------------------------------------------

@router.get("/tree")
async def get_file_tree(
    request: Request,
    project_id: str,
    path: Optional[str] = None,
    depth: int = 3,
):
    """
    Return a nested file-tree for the project directory (or a sub-path).

    Query params:
        project_id  — required; must be owned by the authenticated user
        path        — optional relative path inside the project (default: root)
        depth       — max directory depth (default 3, max 10)
    """
    uid = _owner(request)
    project = _get_project(project_id, uid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    depth = max(1, min(depth, 10))  # clamp 1–10

    try:
        tree = docker_exec.list_tree(uid, project_id, path, depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("list_tree runtime error: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Sandbox unavailable: {exc}")

    return {"tree": tree}


# ---------------------------------------------------------------------------
# GET /v1/dev/files/content
# ---------------------------------------------------------------------------

@router.get("/content")
async def get_file_content(
    request: Request,
    project_id: str,
    path: str,
):
    """
    Read a file from the project directory.

    Query params:
        project_id  — required
        path        — project-relative path to the file (required)

    Returns:
        { "content": str, "encoding": "utf8"|"base64", "size": int, "mime": str }
    """
    uid = _owner(request)
    project = _get_project(project_id, uid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        result = docker_exec.read_file(uid, project_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except IOError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except RuntimeError as exc:
        logger.error("read_file runtime error: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Sandbox unavailable: {exc}")

    return result


# ---------------------------------------------------------------------------
# PUT /v1/dev/files/content
# ---------------------------------------------------------------------------

@router.put("/content", status_code=204)
async def put_file_content(
    request: Request,
    project_id: str,
    body: WriteFileBody,
):
    """
    Write (create or overwrite) a file in the project directory.

    Query params:
        project_id  — required

    Body (JSON):
        path      — project-relative path
        content   — file content string
        encoding  — "utf8" (default) or "base64"

    Returns 204 on success.
    """
    uid = _owner(request)
    project = _get_project(project_id, uid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.encoding not in ("utf8", "base64"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid encoding {body.encoding!r}; must be 'utf8' or 'base64'",
        )

    try:
        docker_exec.write_file(uid, project_id, body.path, body.content, body.encoding)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except IOError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except RuntimeError as exc:
        logger.error("write_file runtime error: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Sandbox unavailable: {exc}")

    # 204 No Content — FastAPI returns empty body automatically
