"""
tests/test_mempalace_client.py

Unit tests for agents/mempalace_client.py — the sync HTTP wrapper.
All httpx calls are mocked; no live services required.

Run:
    pytest tests/test_mempalace_client.py -v
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest
import httpx

# Ensure agents/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

# Patch config before importing the client so it doesn't fail on missing config deps
sys.modules.setdefault("config", MagicMock(CONTROL_NODE_IP="127.0.0.1"))

from mempalace_client import MemPalaceClient


@pytest.fixture
def client():
    """Client pointed at a fake URL (all HTTP calls will be mocked)."""
    return MemPalaceClient(base_url="http://test:8200", timeout=5.0)


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:

    def test_healthy_returns_true(self, client):
        with patch.object(httpx.Client, "get", return_value=_mock_response(200)):
            assert client.healthy() is True

    def test_healthy_returns_false_on_error(self, client):
        with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("down")):
            assert client.healthy() is False

    def test_healthy_returns_false_on_500(self, client):
        with patch.object(httpx.Client, "get", return_value=_mock_response(500)):
            assert client.healthy() is False


# ═══════════════════════════════════════════════════════════════════════════
# Memories CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestStore:

    def test_store_sends_correct_payload(self, client):
        expected_response = {
            "id": "abc-123",
            "content": "test memory",
            "memory_type": "semantic",
            "domain": "coding",
        }
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, expected_response)) as mock_post:
            result = client.store(
                content="test memory",
                memory_type="semantic",
                domain="coding",
                owner_id="user1",
            )

            # Verify the HTTP call
            call_args = mock_post.call_args
            assert call_args[0][0] == "/v1/memories"
            payload = call_args[1]["json"]
            assert payload["content"] == "test memory"
            assert payload["memory_type"] == "semantic"
            assert payload["domain"] == "coding"
            assert payload["owner_id"] == "user1"

            # Verify response
            assert result["id"] == "abc-123"

    def test_store_defaults(self, client):
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, {})) as mock_post:
            client.store(content="bare minimum")
            payload = mock_post.call_args[1]["json"]
            assert payload["memory_type"] == "semantic"
            assert payload["domain"] == "general"
            assert payload["metadata"] == {}


class TestSearch:

    def test_search_returns_results(self, client):
        search_results = [
            {"id": "1", "content": "cyberpunk", "score": 0.85},
            {"id": "2", "content": "coding style", "score": 0.42},
        ]
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, search_results)):
            results = client.search("cyberpunk aesthetics")
            assert len(results) == 2
            assert results[0]["score"] == 0.85

    def test_search_passes_filters(self, client):
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, [])) as mock_post:
            client.search(
                query="test",
                owner_id="owner1",
                agent_id="architect",
                memory_type="procedural",
                domain="visual",
                limit=5,
            )
            payload = mock_post.call_args[1]["json"]
            assert payload["owner_id"] == "owner1"
            assert payload["agent_id"] == "architect"
            assert payload["memory_type"] == "procedural"
            assert payload["domain"] == "visual"
            assert payload["limit"] == 5

    def test_search_empty_results(self, client):
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, [])):
            results = client.search("nonexistent query")
            assert results == []


class TestDelete:

    def test_delete_success(self, client):
        with patch.object(httpx.Client, "delete", return_value=_mock_response(200, {"status": "deleted"})):
            result = client.delete("abc-123")
            assert result["status"] == "deleted"

    def test_delete_404(self, client):
        with patch.object(httpx.Client, "delete", return_value=_mock_response(404)):
            with pytest.raises(httpx.HTTPStatusError):
                client.delete("nonexistent")


class TestStats:

    def test_stats_returns_breakdown(self, client):
        stats_data = {
            "total": 42,
            "breakdown": [
                {"type": "semantic", "domain": "general", "count": 30},
                {"type": "procedural", "domain": "coding", "count": 12},
            ],
        }
        with patch.object(httpx.Client, "get", return_value=_mock_response(200, stats_data)):
            result = client.stats()
            assert result["total"] == 42
            assert len(result["breakdown"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestExtract:

    def test_extract_returns_extracted_memories(self, client):
        extracted = [{"id": "1", "content": "User likes Docker", "memory_type": "semantic"}]
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, extracted)):
            result = client.extract("User: I love Docker\nAssistant: Great choice!")
            assert len(result) == 1
            assert result[0]["content"] == "User likes Docker"

    def test_extract_passes_owner_and_agent(self, client):
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, [])) as mock_post:
            client.extract("conversation", owner_id="owner1", agent_id="arch")
            payload = mock_post.call_args[1]["json"]
            assert payload["owner_id"] == "owner1"
            assert payload["agent_id"] == "arch"

    def test_extract_graceful_on_failure(self, client):
        """Extract should return [] on HTTP errors, not raise."""
        with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("down")):
            result = client.extract("some conversation")
            assert result == []

    def test_extract_graceful_on_timeout(self, client):
        with patch.object(httpx.Client, "post", side_effect=httpx.ReadTimeout("slow")):
            result = client.extract("some conversation")
            assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# Snapshots
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshots:

    def test_save_snapshot(self, client):
        snap = {"id": "s1", "agent_id": "architect", "version": 3}
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, snap)):
            result = client.save_snapshot("architect", {"rules": ["be concise"]})
            assert result["version"] == 3

    def test_get_snapshot_found(self, client):
        snap = {"id": "s1", "agent_id": "architect", "snapshot_data": {"key": "val"}, "version": 2}
        with patch.object(httpx.Client, "get", return_value=_mock_response(200, snap)):
            result = client.get_snapshot("architect")
            assert result["version"] == 2

    def test_get_snapshot_not_found_returns_none(self, client):
        resp = _mock_response(200, None)
        resp.json.return_value = None
        with patch.object(httpx.Client, "get", return_value=resp):
            result = client.get_snapshot("nonexistent")
            assert result is None

    def test_get_snapshot_empty_response_returns_none(self, client):
        resp = _mock_response(200, {})
        resp.json.return_value = {}
        with patch.object(httpx.Client, "get", return_value=resp):
            result = client.get_snapshot("empty")
            # Empty dict is falsy → None
            assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Team Memory
# ═══════════════════════════════════════════════════════════════════════════

class TestTeamMemory:

    def test_team_store(self, client):
        entry = {"id": "t1", "team_id": "coord-abc", "key": "summary", "value": "result text"}
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, entry)):
            result = client.team_store("coord-abc", "summary", "result text", author_agent="worker-1")
            assert result["key"] == "summary"

    def test_team_get(self, client):
        entries = [
            {"id": "t1", "key": "research", "value": "findings"},
            {"id": "t2", "key": "synthesis", "value": "combined"},
        ]
        with patch.object(httpx.Client, "get", return_value=_mock_response(200, entries)):
            result = client.team_get("coord-abc")
            assert len(result) == 2

    def test_team_search(self, client):
        with patch.object(httpx.Client, "post", return_value=_mock_response(200, [])) as mock_post:
            client.team_search("coord-abc", "architecture patterns", limit=5)
            payload = mock_post.call_args[1]["json"]
            assert payload["query"] == "architecture patterns"
            assert payload["limit"] == 5

    def test_team_clear(self, client):
        with patch.object(httpx.Client, "delete", return_value=_mock_response(200, {"status": "cleared", "deleted": 3})):
            result = client.team_clear("coord-abc")
            assert result["deleted"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# Constructor / Config
# ═══════════════════════════════════════════════════════════════════════════

class TestClientConfig:

    def test_custom_base_url(self):
        c = MemPalaceClient(base_url="http://custom:9000/")
        assert c._base_url == "http://custom:9000"  # trailing slash stripped

    def test_custom_timeout(self):
        c = MemPalaceClient(timeout=99.0)
        assert c._timeout == 99.0

    def test_default_timeout(self):
        c = MemPalaceClient(base_url="http://test:8200")
        assert c._timeout == float(os.getenv("MEMPALACE_TIMEOUT", "30"))
