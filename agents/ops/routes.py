"""Mission Control operational mutation routes."""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi import HTTPException
from pydantic import BaseModel

from .actions import dispatch_janitor, dispatch_restart


router = APIRouter(prefix="/api/v1/ops", tags=["operations"])


class JanitorRequest(BaseModel):
    node: str = "lovelace"
    mode: str = "dry_run"
    include_stopped: bool = False
    confirm: bool = False


def _actor(request: Request) -> str:
    """Best-effort caller identity supplied by Authentik/Traefik."""

    return (
        request.headers.get("x-authentik-username")
        or request.headers.get("x-authentik-uid")
        or "unknown"
    )


def _request_is_admin(request: Request) -> bool:
    """Require an explicit admin assertion for host-affecting operations.

    AuthorizationMiddleware is intentionally staged in this deployment and
    may run in parse/soft mode.  These routes therefore enforce the
    host-mutation boundary themselves using the forwarded Authentik group
    assertion, while also honoring a validated agent card when one is present.
    """

    groups = [
        group.strip().lower()
        for group in re.split(r"[|,]", request.headers.get("x-authentik-groups", ""))
        if group.strip()
    ]
    if any("admin" in group for group in groups):
        return True

    agent_card = getattr(request.state, "agent_card", None)
    capabilities = set(getattr(agent_card, "activated_capabilities", []) or [])
    return bool({"admin", "system_admin"} & capabilities)


def _require_admin(request: Request) -> None:
    if not _request_is_admin(request):
        raise HTTPException(status_code=403, detail="Administrator authorization is required")


@router.post("/fleet/{node}/{container}/restart")
async def restart_container(node: str, container: str, request: Request):
    """Queue a validated container restart through auto_repair_daemon."""

    _require_admin(request)
    return dispatch_restart(node, container, requested_by=_actor(request))


@router.post("/janitor")
async def janitor(body: JanitorRequest, request: Request):
    """Queue a dry-run or explicitly requested safe Docker cleanup."""

    _require_admin(request)
    return dispatch_janitor(
        body.node,
        requested_by=_actor(request),
        mode=body.mode,
        include_stopped=body.include_stopped,
        confirm=body.confirm,
    )
