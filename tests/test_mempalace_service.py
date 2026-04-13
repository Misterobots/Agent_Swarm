"""
tests/test_mempalace_service.py

Unit tests for the MemPalace FastAPI service (control_plane/mempalace/app/main.py).
Uses FastAPI TestClient with mocked database sessions and embedding calls.

Run:
    pytest tests/test_mempalace_service.py -v
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the mempalace package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control_plane", "mempalace"))

# We need to mock database and embeddings before importing the FastAPI app
# so that the lifespan doesn't try to connect to a real database.

# Create a fake embedding vector (768-dim zeros)
FAKE_EMBEDDING = [0.0] * 768


# ---------------------------------------------------------------------------
# Mock database layer
# ---------------------------------------------------------------------------
class FakeMemory:
    """In-memory stand-in for the Memory ORM object."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.content = kwargs.get("content", "")
        self.memory_type = kwargs.get("memory_type", "semantic")
        self.domain = kwargs.get("domain", "general")
        self.agent_id = kwargs.get("agent_id")
        self.team_id = kwargs.get("team_id")
        self.owner_id = kwargs.get("owner_id")
        self.embedding = kwargs.get("embedding")
        self.metadata_ = kwargs.get("metadata_", {})
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
        self.access_count = kwargs.get("access_count", 0)
        self.relevance_decay = kwargs.get("relevance_decay", 1.0)


class FakeSnapshot:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.agent_id = kwargs.get("agent_id", "test-agent")
        self.owner_id = kwargs.get("owner_id")
        self.snapshot_data = kwargs.get("snapshot_data", {})
        self.version = kwargs.get("version", 1)
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))


class FakeTeamMemory:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.team_id = kwargs.get("team_id", "team-1")
        self.key = kwargs.get("key", "")
        self.value = kwargs.get("value", "")
        self.embedding = kwargs.get("embedding")
        self.author_agent = kwargs.get("author_agent")
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))


# Store for in-memory data
_memory_store = []
_snapshot_store = []
_team_store = []


def reset_stores():
    global _memory_store, _snapshot_store, _team_store
    _memory_store = []
    _snapshot_store = []
    _team_store = []


# ---------------------------------------------------------------------------
# Patch the database and embeddings modules before importing the app
# ---------------------------------------------------------------------------

# Mock the embeddings module
mock_embed_text = AsyncMock(return_value=FAKE_EMBEDDING)
mock_embed_texts = AsyncMock(side_effect=lambda texts: [FAKE_EMBEDDING] * len(texts))
mock_extract_memories = AsyncMock(return_value=[
    {"content": "User likes Python", "type": "semantic", "domain": "coding"},
    {"content": "Prefers dark mode", "type": "procedural", "domain": "preferences"},
])
mock_close_client = AsyncMock()

# Patch before importing
with patch.dict(sys.modules, {}):
    pass

import app.embeddings as embeddings_mod
embeddings_mod.embed_text = mock_embed_text
embeddings_mod.embed_texts = mock_embed_texts
embeddings_mod.extract_memories = mock_extract_memories
embeddings_mod.close_client = mock_close_client

# Now mock the database session
import app.database as db_mod

# We need a context-manager-compatible async session mock
class MockAsyncSession:
    """Fake async session that stores in memory."""

    def __init__(self):
        self._added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        for obj in self._added:
            if isinstance(obj, db_mod.Memory):
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = uuid.uuid4()
                if not hasattr(obj, 'created_at') or obj.created_at is None:
                    obj.created_at = datetime.now(timezone.utc)
                if not hasattr(obj, 'access_count') or obj.access_count is None:
                    obj.access_count = 0
                _memory_store.append(obj)
            elif isinstance(obj, db_mod.AgentSnapshot):
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = uuid.uuid4()
                if not hasattr(obj, 'created_at') or obj.created_at is None:
                    obj.created_at = datetime.now(timezone.utc)
                _snapshot_store.append(obj)
            elif isinstance(obj, db_mod.TeamMemory):
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = uuid.uuid4()
                if not hasattr(obj, 'created_at') or obj.created_at is None:
                    obj.created_at = datetime.now(timezone.utc)
                _team_store.append(obj)
        self._added = []

    async def refresh(self, obj):
        # Simulate DB defaults
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid.uuid4()
        if not hasattr(obj, 'created_at') or obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if not hasattr(obj, 'access_count') or obj.access_count is None:
            obj.access_count = 0

    async def execute(self, stmt):
        # Return a mock result
        return MockResult()

    async def scalar(self):
        return 0


class MockResult:
    def __init__(self, rows=None, scalar_val=None):
        self._rows = rows or []
        self._scalar_val = scalar_val

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar_val

    def scalar_one_or_none(self):
        return self._scalar_val

    def scalars(self):
        return self

    @property
    def rowcount(self):
        return 1


def mock_async_session():
    return MockAsyncSession()


# Patch the database session factory
original_async_session = db_mod.async_session
db_mod.async_session = mock_async_session

# Now we can import the FastAPI app
from app.main import app as fastapi_app

# Override the lifespan to not init real DB
from contextlib import asynccontextmanager

@asynccontextmanager
async def _noop_lifespan(app):
    yield

fastapi_app.router.lifespan_context = _noop_lifespan

from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_stores():
    """Reset in-memory stores before each test."""
    reset_stores()
    mock_embed_text.reset_mock()
    mock_embed_texts.reset_mock()
    mock_extract_memories.reset_mock()
    yield


@pytest.fixture
def tc():
    """FastAPI TestClient."""
    return TestClient(fastapi_app)


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:

    def test_health_returns_ok(self, tc):
        resp = tc.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "mempalace"


# ═══════════════════════════════════════════════════════════════════════════
# Store Memory
# ═══════════════════════════════════════════════════════════════════════════

class TestStoreMemory:

    def test_store_returns_201_like_fields(self, tc):
        resp = tc.post("/v1/memories", json={
            "content": "User prefers dark mode",
            "memory_type": "procedural",
            "domain": "preferences",
            "owner_id": "user-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "User prefers dark mode"
        assert data["memory_type"] == "procedural"
        assert data["domain"] == "preferences"
        assert data["owner_id"] == "user-1"
        assert "id" in data
        assert "created_at" in data

    def test_store_calls_embed_text(self, tc):
        tc.post("/v1/memories", json={"content": "test embedding call"})
        mock_embed_text.assert_called()
        call_arg = mock_embed_text.call_args[0][0]
        assert call_arg == "test embedding call"

    def test_store_defaults(self, tc):
        resp = tc.post("/v1/memories", json={"content": "minimal"})
        data = resp.json()
        assert data["memory_type"] == "semantic"
        assert data["domain"] == "general"

    def test_store_missing_content_fails(self, tc):
        resp = tc.post("/v1/memories", json={"memory_type": "semantic"})
        assert resp.status_code == 422  # validation error


# ═══════════════════════════════════════════════════════════════════════════
# Search (limited — mock session doesn't do real vector search)
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchMemories:

    def test_search_calls_embed(self, tc):
        resp = tc.post("/v1/memories/search", json={"query": "cyberpunk aesthetics"})
        assert resp.status_code == 200
        mock_embed_text.assert_called()

    def test_search_returns_list(self, tc):
        resp = tc.post("/v1/memories/search", json={"query": "test", "limit": 5})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_search_accepts_filters(self, tc):
        resp = tc.post("/v1/memories/search", json={
            "query": "test",
            "owner_id": "user-1",
            "memory_type": "procedural",
            "domain": "visual",
            "limit": 3,
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Delete
# ═══════════════════════════════════════════════════════════════════════════

class TestDeleteMemory:

    def test_delete_valid_uuid(self, tc):
        fake_id = str(uuid.uuid4())
        resp = tc.delete(f"/v1/memories/{fake_id}")
        # Our mock always returns rowcount=1
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_invalid_uuid_format(self, tc):
        resp = tc.delete("/v1/memories/not-a-uuid")
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════════

class TestStats:

    def test_stats_returns_total(self, tc):
        resp = tc.get("/v1/memories/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "breakdown" in data


# ═══════════════════════════════════════════════════════════════════════════
# Extract
# ═══════════════════════════════════════════════════════════════════════════

class TestExtract:

    def test_extract_calls_llm(self, tc):
        resp = tc.post("/v1/extract", json={
            "conversation": "User: I love Python\nAssistant: Great language!",
            "owner_id": "user-1",
        })
        assert resp.status_code == 200
        mock_extract_memories.assert_called_once()

    def test_extract_returns_stored_memories(self, tc):
        resp = tc.post("/v1/extract", json={
            "conversation": "User: test\nAssistant: response",
        })
        data = resp.json()
        assert isinstance(data, list)
        # From mock: 2 memories extracted
        assert len(data) == 2
        assert data[0]["content"] == "User likes Python"
        assert data[1]["content"] == "Prefers dark mode"

    def test_extract_empty_conversation(self, tc):
        mock_extract_memories.return_value = []
        resp = tc.post("/v1/extract", json={"conversation": ""})
        assert resp.status_code == 200
        assert resp.json() == []
        # Reset for other tests
        mock_extract_memories.return_value = [
            {"content": "User likes Python", "type": "semantic", "domain": "coding"},
            {"content": "Prefers dark mode", "type": "procedural", "domain": "preferences"},
        ]


# ═══════════════════════════════════════════════════════════════════════════
# Snapshots
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshots:

    def test_save_snapshot(self, tc):
        resp = tc.post("/v1/snapshots", json={
            "agent_id": "architect",
            "owner_id": "user-1",
            "snapshot_data": {"learned_rules": ["be concise"]},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "architect"
        assert data["snapshot_data"]["learned_rules"] == ["be concise"]
        assert "version" in data

    def test_get_snapshot_empty(self, tc):
        resp = tc.get("/v1/snapshots/nonexistent")
        assert resp.status_code == 200
        # mock returns None → null JSON


# ═══════════════════════════════════════════════════════════════════════════
# Team Memory
# ═══════════════════════════════════════════════════════════════════════════

class TestTeamMemory:

    def test_store_team_memory(self, tc):
        resp = tc.post("/v1/team/coord-abc", json={
            "key": "research_summary",
            "value": "Docker is popular for containers",
            "author_agent": "worker-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_id"] == "coord-abc"
        assert data["key"] == "research_summary"

    def test_get_team_memories(self, tc):
        resp = tc.get("/v1/team/coord-abc")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_clear_team_memory(self, tc):
        resp = tc.delete("/v1/team/coord-abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cleared"

    def test_search_team_memory(self, tc):
        resp = tc.post("/v1/team/coord-abc/search", json={
            "query": "architecture",
            "limit": 5,
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestSchemaValidation:

    def test_memory_create_requires_content(self, tc):
        resp = tc.post("/v1/memories", json={})
        assert resp.status_code == 422

    def test_search_requires_query(self, tc):
        resp = tc.post("/v1/memories/search", json={})
        assert resp.status_code == 422

    def test_extraction_requires_conversation(self, tc):
        resp = tc.post("/v1/extract", json={})
        assert resp.status_code == 422

    def test_snapshot_requires_agent_id(self, tc):
        resp = tc.post("/v1/snapshots", json={"snapshot_data": {}})
        assert resp.status_code == 422

    def test_team_store_requires_key_value(self, tc):
        resp = tc.post("/v1/team/team1", json={})
        assert resp.status_code == 422
