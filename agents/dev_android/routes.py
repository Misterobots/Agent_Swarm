"""Authenticated Android build endpoint for Dev Workspace."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dev_projects import store
from .builder import AndroidBuildError, build_android_project

router = APIRouter(prefix="/v1/dev/android", tags=["dev-android"])


class AndroidBuildRequest(BaseModel):
    project_id: str
    source_container: str = "dev_sandbox"


def _owner(request: Request) -> str:
    return request.headers.get("x-authentik-username") or request.headers.get("x-authentik-uid") or "local"


@router.post("/build")
async def build_android(body: AndroidBuildRequest, request: Request):
    uid = _owner(request)
    project = store.get_project(body.project_id, uid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.source_container != "dev_sandbox":
        raise HTTPException(status_code=400, detail="Unsupported Android source container")
    try:
        return await asyncio.to_thread(build_android_project, uid, body.project_id)
    except AndroidBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
