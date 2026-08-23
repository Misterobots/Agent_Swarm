"""Mission Control operational mutation routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from .actions import dispatch_restart


router = APIRouter(prefix="/api/v1/ops", tags=["operations"])


def _actor(request: Request) -> str:
    """Best-effort caller identity supplied by Authentik/Traefik."""

    return (
        request.headers.get("x-authentik-username")
        or request.headers.get("x-authentik-uid")
        or "unknown"
    )


@router.post("/fleet/{node}/{container}/restart")
async def restart_container(node: str, container: str, request: Request):
    """Queue a validated container restart through auto_repair_daemon."""

    return dispatch_restart(node, container, requested_by=_actor(request))
