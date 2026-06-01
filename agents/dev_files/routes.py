"""
Dev Files FastAPI router — stub, mounts at /v1/dev/files.
Full implementation: task F2 (Docker exec tree + read + write).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/dev/files", tags=["dev-files"])


class FileWriteRequest(BaseModel):
    path: str
    content: str
    container: str = "agent_runtime"


@router.get("/tree")
async def get_file_tree(container: str = "agent_runtime", path: str = "/workspace"):
    """Return workspace file tree (stub — returns empty list until F2 lands)."""
    return {"tree": [], "path": path, "container": container}


@router.get("/read")
async def read_file(path: str, container: str = "agent_runtime"):
    """Read a file from the workspace container (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev files not yet implemented (task F2)")


@router.post("/write")
async def write_file(body: FileWriteRequest):
    """Write a file to the workspace container (stub)."""
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail="Dev files not yet implemented (task F2)")
