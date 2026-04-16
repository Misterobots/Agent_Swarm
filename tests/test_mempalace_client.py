"""
tests/test_mempalace_client.py

Unit tests for agents/mempalace_client.py — the official mempalace library wrapper.
All mempalace and chromadb internals are mocked; no live services required.

Run:
    pytest tests/test_mempalace_client.py -v
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

# Ensure agents/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

# Provide stub modules so the import doesn't fail when mempalace isn't installed
_fake_searcher = MagicMock()
_fake_kg_mod = MagicMock()
_fake_backends = MagicMock()

sys.modules.setdefault("mempalace", MagicMock())
sys.modules.setdefault("mempalace.searcher", _fake_searcher)
sys.modules.setdefault("mempalace.knowledge_graph", _fake_kg_mod)
sys.modules.setdefault("mempalace.backends", _fake_backends)
sys.modules.setdefault("mempalace.backends.chroma", _fake_backends)
sys.modules.setdefault("mempalace.convo_miner", MagicMock())
sys.modules.setdefault("mempalace.mcp_server", MagicMock())
sys.modules.setdefault("chromadb", MagicMock())

from mempalace_client import MemPalaceClient


@pytest.fixture
def client(tmp_path):
    """Client pointed at a temporary palace directory."""
    palace = tmp_path / "palace"
    palace.mkdir()
    c = MemPalaceClient(palace_path=str(palace))
    # Force _initialized so tests bypass lazy-init import dance
    c._initialized = True
    c._search_fn = MagicMock(return_value=[])
    c._kg = MagicMock()
    c._backend = MagicMock()
    return c


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:

    def test_healthy_returns_true(self, client):
        assert client.healthy() is True

    def test_healthy_returns_false_when_init_fails(self, tmp_path):
        c = MemPalaceClient(palace_path=str(tmp_path / "nonexistent"))
        c._initialized = False
        with patch.object(c, "_ensure_init", return_value=False):
            assert c.healthy() is False


# ═══════════════════════════════════════════════════════════════════════════
# Memories CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestStore:

    def test_store_calls_backend_add(self, client):
        result = client.store(
            content="test memory",
            memory_type="semantic",
            domain="coding",
            owner_id="user1",
        )
        assert client._backend.add.called
        call_kwargs = client._backend.add.call_args
        assert call_kwargs[1]["documents"] == ["test memory"]
        meta = call_kwargs[1]["metadatas"][0]
        assert meta["domain"] == "coding"
        assert meta["hall"] == "hall_facts"
        assert meta["owner_id"] == "user1"
        assert "id" in result

    def test_store_defaults(self, client):
        result = client.store(content="bare minimum")
        meta = client._backend.add.call_args[1]["metadatas"][0]
        assert meta["memory_type"] == "semantic"
        assert meta["domain"] == "general"
        assert meta["wing"] == "wing_agent_swarm"

    def test_store_maps_procedural_to_hall_advice(self, client):
        client.store(content="how to deploy", memory_type="procedural", domain="devops")
        meta = client._backend.add.call_args[1]["metadatas"][0]
        assert meta["hall"] == "hall_advice"

    def test_store_agent_id_creates_wing(self, client):
        client.store(content="note", agent_id="architect")
        meta = client._backend.add.call_args[1]["metadatas"][0]
        assert meta["wing"] == "wing_architect"


class TestSearch:

    def test_search_returns_results(self, client):
        client._search_fn.return_value = [
            {"content": "cyberpunk", "score": 0.85, "id": "1"},
            {"content": "coding style", "score": 0.42, "id": "2"},
        ]
        results = client.search("cyberpunk aesthetics")
        assert len(results) == 2
        assert results[0]["score"] == 0.85

    def test_search_passes_wing_filter(self, client):
        client.search(query="test", agent_id="architect", limit=5)
        call_kwargs = client._search_fn.call_args[1]
        assert call_kwargs["n_results"] == 5
        assert call_kwargs["where"]["wing"] == "wing_architect"

    def test_search_empty_results(self, client):
        client._search_fn.return_value = []
        results = client.search("nonexistent query")
        assert results == []

    def test_search_graceful_on_error(self, client):
        client._search_fn.side_effect = Exception("db error")
        results = client.search("test")
        assert results == []


class TestDelete:

    def test_delete_success(self, client):
        result = client.delete("abc-123")
        client._backend.delete.assert_called_once_with(ids=["abc-123"])
        assert result["deleted"] == "abc-123"


class TestStats:

    def test_stats_returns_overview(self, client, tmp_path):
        mock_col = MagicMock()
        mock_col.count.return_value = 42
        mock_chroma_client = MagicMock()
        mock_chroma_client.get_or_create_collection.return_value = mock_col
        with patch("chromadb.PersistentClient", return_value=mock_chroma_client):
            result = client.stats()
            assert result["total_drawers"] == 42
            assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# Extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestExtract:

    def test_extract_uses_convo_miner(self, client):
        with patch(
            "mempalace.convo_miner.mine_conversation_text",
            return_value=["extracted 1", "extracted 2"],
        ):
            result = client.extract("User: I love Docker\nAssistant: Great choice!")
            assert len(result) == 2

    def test_extract_graceful_on_failure(self, client):
        """Extract should return fallback drawer, not raise."""
        with patch(
            "mempalace.convo_miner.mine_conversation_text",
            side_effect=ImportError("not available"),
        ), patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.extract("some conversation")
            # Falls back to storing raw conversation
            assert len(result) >= 1

    def test_extract_passes_owner_and_agent(self, client):
        with patch(
            "mempalace.convo_miner.mine_conversation_text",
            return_value=[],
        ) as mock_mine:
            client.extract("conversation", owner_id="owner1", agent_id="arch")
            call_kwargs = mock_mine.call_args[1]
            assert call_kwargs["wing"] == "wing_arch"


# ═══════════════════════════════════════════════════════════════════════════
# Snapshots (agent diary)
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshots:

    def test_save_snapshot_uses_diary(self, client):
        with patch("mempalace.mcp_server.diary_write") as mock_diary:
            result = client.save_snapshot("architect", {"rules": ["be concise"]})
            mock_diary.assert_called_once()
            assert result["agent_id"] == "architect"

    def test_get_snapshot_found(self, client):
        with patch(
            "mempalace.mcp_server.diary_read",
            return_value=[{"content": json.dumps({"key": "val"})}],
        ):
            result = client.get_snapshot("architect")
            assert result == {"key": "val"}

    def test_get_snapshot_not_found_returns_none(self, client):
        with patch("mempalace.mcp_server.diary_read", return_value=[]):
            result = client.get_snapshot("nonexistent")
            # Falls back to search, which returns []
            client._search_fn.return_value = []
            result = client.get_snapshot("nonexistent")
            assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Team Memory
# ═══════════════════════════════════════════════════════════════════════════

class TestTeamMemory:

    def test_team_store_adds_kg_triple(self, client):
        result = client.team_store("coord-abc", "summary", "result text", author_agent="worker-1")
        client._kg.add_triple.assert_called_once()
        args = client._kg.add_triple.call_args
        assert args[0][0] == "coord-abc"
        assert "has_summary" in args[0][1]

    def test_team_get_queries_kg(self, client):
        client._kg.query_entity.return_value = [
            {"predicate": "has_research", "object": "findings"},
        ]
        client._search_fn.return_value = []
        result = client.team_get("coord-abc")
        assert len(result) >= 1
        assert result[0]["source"] == "knowledge_graph"

    def test_team_search_delegates_to_search(self, client):
        client._search_fn.return_value = [
            {"content": "arch patterns", "score": 0.7, "id": "1"},
        ]
        result = client.team_search("coord-abc", "architecture patterns", limit=5)
        assert len(result) == 1

    def test_team_clear_invalidates_triples(self, client):
        client._kg.query_entity.return_value = [
            {"predicate": "has_entry", "object": "some data"},
        ]
        result = client.team_clear("coord-abc")
        assert result["status"] == "cleared"
        assert client._kg.invalidate.called


# ═══════════════════════════════════════════════════════════════════════════
# Constructor / Config
# ═══════════════════════════════════════════════════════════════════════════

class TestClientConfig:

    def test_custom_palace_path(self, tmp_path):
        c = MemPalaceClient(palace_path=str(tmp_path / "custom"))
        assert c._palace_path == str(tmp_path / "custom")

    def test_default_palace_path(self):
        c = MemPalaceClient()
        assert "mempalace" in c._palace_path.lower() or "palace" in c._palace_path.lower()
