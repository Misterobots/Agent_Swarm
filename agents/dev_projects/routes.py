"""
Dev Projects FastAPI router — stub, mounts at /v1/dev/projects.
Full implementation: task F3 (CRUD + git clone).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/dev/projects", tags=["dev-projects"])


class DevProject(BaseModel):
    id: str | None = None
    name: str
    repo_url: str | None = None
    local_path: str | None = None


@router.get("")
async def list_projects():
    """List all dev projects (stub — returns empty list until F3 lands)."""
    return {"projects": []}


@router.post("")
async def create_project(body: DevProject):
    """Create / clone a dev project (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev projects not yet implemented (task F3)")


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get a specific dev project (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev projects not yet implemented (task F3)")


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a dev project (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev projects not yet implemented (task F3)")
