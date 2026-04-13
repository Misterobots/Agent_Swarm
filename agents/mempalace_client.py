"""MemPalace client — sync HTTP interface for the agent runtime.

Usage:
    from mempalace_client import mempalace

    # Store a memory
    mempalace.store("User prefers dark cyberpunk aesthetics", domain="visual")

    # Semantic search
    results = mempalace.search("cyberpunk art style preferences")

    # Extract memories from a conversation
    extracted = mempalace.extract(conversation_text, owner_id="user_123")

    # Agent snapshots
    mempalace.save_snapshot("architect", {"learned_rules": [...]})
    snapshot = mempalace.get_snapshot("architect")

    # Team memory (for coordinator tasks)
    mempalace.team_store("coord-abc123", "research_summary", "The analysis shows...")
    entries = mempalace.team_get("coord-abc123")
"""

import logging
import os
from typing import Optional

import httpx

from config import CONTROL_NODE_IP

logger = logging.getLogger("agents.mempalace_client")

MEMPALACE_URL = os.getenv("MEMPALACE_URL", f"http://{CONTROL_NODE_IP}:8200")
TIMEOUT = float(os.getenv("MEMPALACE_TIMEOUT", "30"))


class MemPalaceClient:
    """Synchronous HTTP client for the MemPalace memory service."""

    def __init__(self, base_url: str = MEMPALACE_URL, timeout: float = TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def healthy(self) -> bool:
        """Check if MemPalace is reachable."""
        try:
            with self._client() as c:
                resp = c.get("/health")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------
    def store(
        self,
        content: str,
        memory_type: str = "semantic",
        domain: str = "general",
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a memory with auto-embedding."""
        with self._client() as c:
            resp = c.post("/v1/memories", json={
                "content": content,
                "memory_type": memory_type,
                "domain": domain,
                "agent_id": agent_id,
                "team_id": team_id,
                "owner_id": owner_id,
                "metadata": metadata or {},
            })
            resp.raise_for_status()
            return resp.json()

    def search(
        self,
        query: str,
        owner_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic similarity search over memories."""
        with self._client() as c:
            resp = c.post("/v1/memories/search", json={
                "query": query,
                "owner_id": owner_id,
                "agent_id": agent_id,
                "team_id": team_id,
                "memory_type": memory_type,
                "domain": domain,
                "limit": limit,
            })
            resp.raise_for_status()
            return resp.json()

    def delete(self, memory_id: str) -> dict:
        """Delete a memory by ID."""
        with self._client() as c:
            resp = c.delete(f"/v1/memories/{memory_id}")
            resp.raise_for_status()
            return resp.json()

    def stats(self) -> dict:
        """Get memory statistics."""
        with self._client() as c:
            resp = c.get("/v1/memories/stats")
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Memory Extraction
    # ------------------------------------------------------------------
    def extract(
        self,
        conversation: str,
        owner_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> list[dict]:
        """Auto-extract and store memories from conversation text."""
        try:
            with self._client() as c:
                resp = c.post("/v1/extract", json={
                    "conversation": conversation,
                    "owner_id": owner_id,
                    "agent_id": agent_id,
                    "team_id": team_id,
                }, timeout=90.0)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Memory extraction failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Agent Snapshots
    # ------------------------------------------------------------------
    def save_snapshot(
        self,
        agent_id: str,
        snapshot_data: dict,
        owner_id: Optional[str] = None,
    ) -> dict:
        """Save a versioned agent state snapshot."""
        with self._client() as c:
            resp = c.post("/v1/snapshots", json={
                "agent_id": agent_id,
                "owner_id": owner_id,
                "snapshot_data": snapshot_data,
            })
            resp.raise_for_status()
            return resp.json()

    def get_snapshot(
        self,
        agent_id: str,
        owner_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Get the latest snapshot for an agent."""
        params = {}
        if owner_id:
            params["owner_id"] = owner_id
        with self._client() as c:
            resp = c.get(f"/v1/snapshots/{agent_id}", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if data else None
            return None

    # ------------------------------------------------------------------
    # Team Memory
    # ------------------------------------------------------------------
    def team_store(
        self,
        team_id: str,
        key: str,
        value: str,
        author_agent: Optional[str] = None,
    ) -> dict:
        """Store a key-value pair in team memory."""
        with self._client() as c:
            resp = c.post(f"/v1/team/{team_id}", json={
                "key": key,
                "value": value,
                "author_agent": author_agent,
            })
            resp.raise_for_status()
            return resp.json()

    def team_get(self, team_id: str) -> list[dict]:
        """Get all team memories."""
        with self._client() as c:
            resp = c.get(f"/v1/team/{team_id}")
            resp.raise_for_status()
            return resp.json()

    def team_search(
        self,
        team_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic search within a team's memory."""
        with self._client() as c:
            resp = c.post(f"/v1/team/{team_id}/search", json={
                "query": query,
                "limit": limit,
            })
            resp.raise_for_status()
            return resp.json()

    def team_clear(self, team_id: str) -> dict:
        """Clear all team memories (post-coordination cleanup)."""
        with self._client() as c:
            resp = c.delete(f"/v1/team/{team_id}")
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# Singleton — graceful fallback if MemPalace is unreachable
# ---------------------------------------------------------------------------
mempalace = MemPalaceClient()
