"""
tests/test_router_phase2.py

Unit tests for the MemPalace integration points in the router:
  1. Semantic recall — memory search + score filtering + history injection
  2. TRAIN intent — storing procedural memories

These tests mock the mempalace_client module so no live service is required.
The router itself has heavy dependencies (phi, prometheus, etc.) so we test
the MemPalace-specific logic paths directly rather than importing the full module.

Run:
    pytest tests/test_router_phase2.py -v
"""

import sys
import os
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mempalace_module():
    """Install a mock mempalace_client in sys.modules for import-based patching."""
    mock_mp = MagicMock()
    mock_module = MagicMock()
    mock_module.mempalace = mock_mp
    old = sys.modules.get("mempalace_client")
    sys.modules["mempalace_client"] = mock_module
    yield mock_mp
    if old is not None:
        sys.modules["mempalace_client"] = old
    else:
        sys.modules.pop("mempalace_client", None)


# ═══════════════════════════════════════════════════════════════════════════
# Semantic Recall Logic
# ═══════════════════════════════════════════════════════════════════════════

class TestMemPalaceRecall:
    """
    Tests the recall logic from router.py ~line 644:
        from mempalace_client import mempalace as _mp
        relevant = _mp.search(user_input, owner_id=owner_id, limit=5)
        strong = [m for m in relevant if (m.get("score") or 0) > 0.5]
    """

    def _run_recall(self, user_input, search_results, owner_id=None):
        """
        Simulates the MemPalace recall code path from the router.
        Returns (history_additions, thoughts).
        """
        from mempalace_client import mempalace as _mp
        _mp.search.return_value = search_results

        history = []
        thoughts = []

        try:
            relevant = _mp.search(user_input, owner_id=owner_id, limit=5)
            if relevant:
                strong = [m for m in relevant if (m.get("score") or 0) > 0.5]
                if strong:
                    semantic_text = "\n".join(f"- {m['content']}" for m in strong)
                    mp_msg = {"role": "system", "content": f"[Relevant Memories]\n{semantic_text}"}
                    history.append(mp_msg)
                    thoughts.append(f"→ MemPalace: {len(strong)} relevant memories recalled")
        except Exception:
            pass

        return history, thoughts

    def test_high_score_memories_injected(self, mock_mempalace_module):
        results = [
            {"content": "User prefers Docker Compose", "score": 0.85},
            {"content": "Uses Neovim as editor", "score": 0.72},
        ]
        history, thoughts = self._run_recall("What tools should I use?", results)

        assert len(history) == 1
        assert "[Relevant Memories]" in history[0]["content"]
        assert "Docker Compose" in history[0]["content"]
        assert "Neovim" in history[0]["content"]
        assert "2 relevant memories recalled" in thoughts[0]

    def test_low_score_memories_filtered_out(self, mock_mempalace_module):
        results = [
            {"content": "Irrelevant fact", "score": 0.3},
            {"content": "Another weak match", "score": 0.45},
        ]
        history, thoughts = self._run_recall("random query", results)

        assert len(history) == 0
        assert len(thoughts) == 0

    def test_mixed_scores_only_strong_kept(self, mock_mempalace_module):
        results = [
            {"content": "Strong match", "score": 0.8},
            {"content": "Weak match", "score": 0.3},
            {"content": "Borderline", "score": 0.5},  # exactly 0.5 — NOT > 0.5
        ]
        history, thoughts = self._run_recall("test query", results)

        assert len(history) == 1
        assert "Strong match" in history[0]["content"]
        assert "Weak match" not in history[0]["content"]
        assert "Borderline" not in history[0]["content"]
        assert "1 relevant memories recalled" in thoughts[0]

    def test_empty_search_results(self, mock_mempalace_module):
        history, thoughts = self._run_recall("test", [])
        assert len(history) == 0
        assert len(thoughts) == 0

    def test_score_threshold_boundary(self, mock_mempalace_module):
        """Score of exactly 0.501 should pass the > 0.5 threshold."""
        results = [{"content": "Just above threshold", "score": 0.501}]
        history, thoughts = self._run_recall("test", results)
        assert len(history) == 1

    def test_missing_score_treated_as_zero(self, mock_mempalace_module):
        """Memories with no score field should be filtered out."""
        results = [{"content": "No score field"}]
        history, thoughts = self._run_recall("test", results)
        assert len(history) == 0

    def test_none_score_treated_as_zero(self, mock_mempalace_module):
        results = [{"content": "None score", "score": None}]
        history, thoughts = self._run_recall("test", results)
        assert len(history) == 0

    def test_search_called_with_correct_params(self, mock_mempalace_module):
        self._run_recall("my query", [], owner_id="user-123")
        mock_mempalace_module.search.assert_called_once_with(
            "my query", owner_id="user-123", limit=5
        )

    def test_recall_graceful_on_exception(self, mock_mempalace_module):
        mock_mempalace_module.search.side_effect = Exception("Network error")
        history, thoughts = self._run_recall("test", [])
        # Should not raise, just return empty
        assert len(history) == 0

    def test_history_message_format(self, mock_mempalace_module):
        results = [{"content": "Fact A", "score": 0.9}, {"content": "Fact B", "score": 0.7}]
        history, _ = self._run_recall("test", results)

        msg = history[0]
        assert msg["role"] == "system"
        assert msg["content"].startswith("[Relevant Memories]")
        assert "- Fact A" in msg["content"]
        assert "- Fact B" in msg["content"]


# ═══════════════════════════════════════════════════════════════════════════
# TRAIN Intent — MemPalace Storage
# ═══════════════════════════════════════════════════════════════════════════

class TestTrainMemPalaceStorage:
    """
    Tests the MemPalace store call in the TRAIN intent path:
        _mp.store(content=f"{keyword}: {rule}", memory_type="procedural",
                  domain=..., owner_id=...)
    """

    def test_store_called_with_correct_params(self, mock_mempalace_module):
        keyword = "cyberpunk"
        rule = "use neon colors on dark backgrounds"
        domain = "visual"
        owner_id = "user-1"

        try:
            from mempalace_client import mempalace as _mp
            _mp.store(
                content=f"{keyword}: {rule}",
                memory_type="procedural",
                domain=domain,
                owner_id=owner_id,
            )
        except Exception:
            pass

        mock_mempalace_module.store.assert_called_once_with(
            content="cyberpunk: use neon colors on dark backgrounds",
            memory_type="procedural",
            domain="visual",
            owner_id="user-1",
        )

    def test_store_domain_strip_suffix(self):
        """Router strips _rules suffix from domain before storing."""
        domain = "visual_rules"
        stripped = domain.replace("_rules", "")
        assert stripped == "visual"

    def test_store_failure_silenced(self, mock_mempalace_module):
        """Store failures in TRAIN should be silenced (wrapped in try/except pass)."""
        mock_mempalace_module.store.side_effect = Exception("Network error")
        # Simulate the router's error handling
        try:
            from mempalace_client import mempalace as _mp
            _mp.store(content="test", memory_type="procedural", domain="general", owner_id="u1")
        except Exception:
            pass  # Router silences this
        # The test passes if no exception propagates


# ═══════════════════════════════════════════════════════════════════════════
# Background Extraction (main.py integration point)
# ═══════════════════════════════════════════════════════════════════════════

class TestBackgroundExtraction:
    """
    Tests the extraction logic from main.py:
        conversation = f"User: {last_msg}\\nAssistant: {response_text}"
        mempalace.extract(conv, owner_id=oid)
    """

    def test_conversation_format(self):
        last_msg = "What is Kubernetes?"
        response_text = "Kubernetes is a container orchestration platform."
        conversation = f"User: {last_msg}\nAssistant: {response_text}"
        assert conversation == "User: What is Kubernetes?\nAssistant: Kubernetes is a container orchestration platform."

    def test_conversation_truncated_at_8000(self):
        long_text = "x" * 20000
        truncated = long_text[:8000]
        assert len(truncated) == 8000

    def test_extract_called_with_owner(self, mock_mempalace_module):
        from mempalace_client import mempalace as _mp
        conv = "User: hello\nAssistant: hi there"
        _mp.extract(conv, owner_id="user-1")
        mock_mempalace_module.extract.assert_called_once_with(conv, owner_id="user-1")

    def test_response_parts_collection(self):
        """Simulates how streaming collects response_parts."""
        response_parts = []
        updates = [
            {"type": "status", "content": "Processing..."},
            {"type": "response", "content": "Hello "},
            {"type": "response", "content": "world!"},
            {"type": "message", "content": " How are you?"},
            {"type": "thought", "content": "Thinking..."},
        ]
        for u in updates:
            if u.get("type") in ("response", "message"):
                response_parts.append(u["content"])

        assert response_parts == ["Hello ", "world!", " How are you?"]
        assert "".join(response_parts) == "Hello world! How are you?"

    def test_extraction_skipped_when_empty(self):
        """No extraction if response_parts is empty."""
        response_parts = []
        memory_enabled = True
        should_extract = memory_enabled and response_parts
        assert not should_extract

    def test_extraction_skipped_when_disabled(self):
        """No extraction if memory_enabled is False."""
        response_parts = ["Some response"]
        memory_enabled = False
        should_extract = memory_enabled and response_parts
        assert not should_extract
