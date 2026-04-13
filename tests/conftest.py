"""
Shared fixtures for Agent Swarm tests.

Provides mock objects, environment setup, and common test helpers
that can be reused across all test modules.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Path setup — ensure agents/ and control_plane/ are importable
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
CONTROL_PLANE_DIR = os.path.join(REPO_ROOT, "control_plane")

for p in [AGENTS_DIR, CONTROL_PLANE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Langfuse suppression — prevent real network calls in all tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def no_langfuse(monkeypatch):
    """Suppress Langfuse initialization in all tests."""
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3001")

    langfuse_mock = MagicMock()
    langfuse_mock.Langfuse.return_value = MagicMock()

    class DummyDecorators:
        @staticmethod
        def observe(*args, **kwargs):
            return lambda f: f

    langfuse_mock.decorators = DummyDecorators()
    sys.modules.setdefault("langfuse", langfuse_mock)
    sys.modules.setdefault("langfuse.decorators", langfuse_mock.decorators)


# ---------------------------------------------------------------------------
# MemPalace mock client
# ---------------------------------------------------------------------------
class MockMemPalaceClient:
    """In-memory mock of MemPalaceClient for testing."""

    def __init__(self):
        self._memories = []
        self._snapshots = {}
        self._teams = {}
        self._id_counter = 0

    def _next_id(self):
        self._id_counter += 1
        return f"mock-{self._id_counter}"

    def healthy(self) -> bool:
        return True

    def store(self, content, memory_type="semantic", domain="general",
              agent_id=None, team_id=None, owner_id=None, metadata=None):
        entry = {
            "id": self._next_id(),
            "content": content,
            "memory_type": memory_type,
            "domain": domain,
            "agent_id": agent_id,
            "team_id": team_id,
            "owner_id": owner_id,
            "metadata": metadata or {},
            "created_at": "2026-01-01T00:00:00",
            "access_count": 0,
        }
        self._memories.append(entry)
        return entry

    def search(self, query, owner_id=None, agent_id=None, team_id=None,
               memory_type=None, domain=None, limit=10):
        # Simple substring match for testing (no semantic similarity)
        results = []
        for m in self._memories:
            if owner_id and m.get("owner_id") != owner_id:
                continue
            if agent_id and m.get("agent_id") != agent_id:
                continue
            if team_id and m.get("team_id") != team_id:
                continue
            if memory_type and m.get("memory_type") != memory_type:
                continue
            if domain and m.get("domain") != domain:
                continue
            # Crude relevance: check if any query word appears in content
            score = 0.6 if any(w.lower() in m["content"].lower() for w in query.split()) else 0.3
            results.append({**m, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def delete(self, memory_id):
        self._memories = [m for m in self._memories if m["id"] != memory_id]
        return {"status": "deleted", "id": memory_id}

    def stats(self):
        breakdown = {}
        for m in self._memories:
            key = (m["memory_type"], m["domain"])
            breakdown[key] = breakdown.get(key, 0) + 1
        return {
            "total": len(self._memories),
            "breakdown": [
                {"type": t, "domain": d, "count": c}
                for (t, d), c in breakdown.items()
            ],
        }

    def extract(self, conversation, owner_id=None, agent_id=None, team_id=None):
        # Simulate extraction — return a canned memory
        entry = self.store(
            content=f"Extracted from conversation: {conversation[:50]}",
            memory_type="semantic",
            domain="general",
            owner_id=owner_id,
            agent_id=agent_id,
            team_id=team_id,
        )
        return [entry]

    def save_snapshot(self, agent_id, snapshot_data, owner_id=None):
        key = (agent_id, owner_id)
        version = self._snapshots.get(key, {}).get("version", 0) + 1
        snap = {
            "id": self._next_id(),
            "agent_id": agent_id,
            "owner_id": owner_id,
            "snapshot_data": snapshot_data,
            "version": version,
            "created_at": "2026-01-01T00:00:00",
        }
        self._snapshots[key] = snap
        return snap

    def get_snapshot(self, agent_id, owner_id=None):
        return self._snapshots.get((agent_id, owner_id))

    def team_store(self, team_id, key, value, author_agent=None):
        if team_id not in self._teams:
            self._teams[team_id] = {}
        entry = {
            "id": self._next_id(),
            "team_id": team_id,
            "key": key,
            "value": value,
            "author_agent": author_agent,
            "created_at": "2026-01-01T00:00:00",
        }
        self._teams[team_id][key] = entry
        return entry

    def team_get(self, team_id):
        entries = self._teams.get(team_id, {})
        return list(entries.values())

    def team_search(self, team_id, query, limit=10):
        return self.team_get(team_id)[:limit]

    def team_clear(self, team_id):
        deleted = len(self._teams.get(team_id, {}))
        self._teams.pop(team_id, None)
        return {"status": "cleared", "team_id": team_id, "deleted": deleted}


@pytest.fixture
def mock_mempalace():
    """Provides a fresh MockMemPalaceClient for each test."""
    return MockMemPalaceClient()
