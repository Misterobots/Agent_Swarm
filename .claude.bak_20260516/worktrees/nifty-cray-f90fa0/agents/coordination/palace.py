"""MemPalace HTTP client — team scratchpad and project memory."""

import os

import requests

from logger_setup import setup_logger

logger = setup_logger("Lamport")

_MEMPALACE_URL = os.getenv("MEMPALACE_API_URL", "http://192.168.2.102:8200")
_MEMPALACE_TIMEOUT = 5.0


def _team_store(team_id: str, key: str, value: str, author: str = "lamport"):
    """Upsert a team-scoped key/value into MemPalace via /v1/team/{team_id}."""
    try:
        requests.post(
            f"{_MEMPALACE_URL}/v1/team/{team_id}",
            json={"key": key, "value": value, "author_agent": author},
            timeout=_MEMPALACE_TIMEOUT,
        )
    except Exception as e:
        logger.debug(f"[Coordinator] Team memory store failed (non-fatal): {e}")


def _team_clear(team_id: str):
    """Clear a team's scratchpad via DELETE /v1/team/{team_id}."""
    try:
        requests.delete(
            f"{_MEMPALACE_URL}/v1/team/{team_id}",
            timeout=_MEMPALACE_TIMEOUT,
        )
    except Exception as e:
        logger.debug(f"[Coordinator] Team memory clear failed (non-fatal): {e}")


def _palace_project_lookup(owner_id: str, query: str, limit: int = 3) -> list[dict]:
    """Search the user's project memories via /v1/memories/search."""
    if not owner_id:
        return []
    try:
        resp = requests.post(
            f"{_MEMPALACE_URL}/v1/memories/search",
            json={
                "query": query,
                "owner_id": owner_id,
                "domain": "projects",
                "limit": limit,
            },
            timeout=_MEMPALACE_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json() or []
        logger.debug(f"[Coordinator] Palace project lookup HTTP {resp.status_code}: {resp.text[:200]}")
        return []
    except Exception as e:
        logger.debug(f"[Coordinator] Palace project lookup failed (non-fatal): {e}")
        return []


def _palace_project_save(owner_id: str, slug: str, url: str, description: str, path: str = None) -> None:
    """Record a completed project under the user's palace wing as an episodic memory."""
    if not owner_id:
        return
    try:
        from datetime import datetime as _dt
        content = (
            f"PROJECT: {slug}\n"
            f"URL: {url}\n"
            f"PATH: {path or f'user_projects/{slug}/index.html'}\n"
            f"DESCRIPTION: {description}\n"
            f"STATUS: active\n"
            f"BUILT: {_dt.now().strftime('%Y-%m-%d')}\n"
        )
        requests.post(
            f"{_MEMPALACE_URL}/v1/memories",
            json={
                "content": content,
                "memory_type": "episodic",
                "domain": "projects",
                "owner_id": owner_id,
                "agent_id": "lamport",
            },
            timeout=_MEMPALACE_TIMEOUT,
        )
        logger.info(f"[Coordinator] Saved project '{slug}' to palace wing for '{owner_id}'")
    except Exception as e:
        logger.debug(f"[Coordinator] Palace project save failed (non-fatal): {e}")
