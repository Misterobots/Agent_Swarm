"""
Dev Sessions FastAPI router — stub, mounts at /v1/dev/sessions.
Full implementation: task F1 (CRUD + DB model).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/dev/sessions", tags=["dev-sessions"])


class DevSession(BaseModel):
    id: str
    name: str
    project_id: str | None = None
    created_at: str | None = None


@router.get("")
async def list_sessions():
    """List all dev sessions (stub — returns empty list until F1 lands)."""
    return {"sessions": []}


@router.post("")
async def create_session(body: DevSession):
    """Create a dev session (stub — 501 until F1 lands)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev sessions not yet implemented (task F1)")


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get a specific dev session (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev sessions not yet implemented (task F1)")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a dev session (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev sessions not yet implemented (task F1)")
