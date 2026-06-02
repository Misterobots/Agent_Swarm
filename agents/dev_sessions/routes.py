"""
Dev sessions FastAPI router — mounts at /v1/dev/sessions.

A "session" is the editor's persisted UI state for one user:
  - which project is open
  - which file is active
  - which view mode (code/preview/split) is shown
  - which sidebar node is selected
  - which goals are pinned open

Sessions belong to a uid extracted from the Authentik forward-auth header.
Cross-uid access always returns 404 (not 403) to avoid existence disclosure.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from . import store

router = APIRouter(prefix="/v1/dev/sessions", tags=["dev-sessions"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _owner(request: Request) -> str:
    """Extract uid from Authentik forward-auth headers. Returns '' if absent."""
    return (
        request.headers.get("x-authentik-uid")
        or request.headers.get("x-authentik-username")
        or ""
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    project_id:    Optional[str] = None
    active_file:   Optional[str] = None
    view_mode:     str = "code"
    selected_node: str = "workspace"
    open_goal_ids: List[str] = []


class SessionUpdate(BaseModel):
    project_id:    Optional[str] = None
    active_file:   Optional[str] = None
    view_mode:     Optional[str] = None
    selected_node: Optional[str] = None
    open_goal_ids: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_sessions(request: Request):
    """
    List all non-archived sessions for the requesting user.
    Returns an empty list when the user has no sessions.
    """
    uid = _owner(request)
    sessions = store.list_sessions(uid)
    return {"sessions": sessions}


@router.post("", status_code=201)
async def create_session(body: SessionCreate, request: Request):
    """
    Create a new session for the requesting user.
    The id is server-generated (UUID4).
    Returns 201 with the created session object.
    """
    uid = _owner(request)
    session_id = str(uuid.uuid4())
    session = store.create_session(
        id=session_id,
        uid=uid,
        project_id=body.project_id,
        active_file=body.active_file,
        view_mode=body.view_mode,
        selected_node=body.selected_node,
        open_goal_ids=body.open_goal_ids,
    )
    return {"session": session}


@router.get("/{session_id}")
async def get_session(session_id: str, request: Request):
    """
    Get a single session by id.
    Returns 404 if the session does not exist OR belongs to a different user.
    """
    uid = _owner(request)
    session = store.get_session(session_id, uid)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.put("/{session_id}")
async def update_session(session_id: str, body: SessionUpdate, request: Request):
    """
    Replace mutable fields on an existing session.
    Only fields present in the request body are updated (partial update).
    Returns 404 if the session does not exist OR belongs to a different user.
    """
    uid = _owner(request)
    # Build kwargs from only the fields that were explicitly set
    fields = body.model_dump(exclude_none=True)
    session = store.update_session(session_id, uid, **fields)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.delete("/{session_id}", status_code=204)
async def archive_session(session_id: str, request: Request):
    """
    Soft-delete (archive) a session.
    Returns 204 No Content on success.
    Returns 404 if the session does not exist OR belongs to a different user.
    """
    uid = _owner(request)
    found = store.archive_session(session_id, uid)
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)
