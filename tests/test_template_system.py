"""
ExpertiseTemplate System Tests
================================

Tests for the template registry, versioning, performance recording,
and async updater logic.

Uses mocked PostgreSQL to test logic in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestTemplateModels:
    """Test Pydantic data models."""

    def test_expertise_template_creation(self):
        from expertise.template_registry import ExpertiseTemplate

        t = ExpertiseTemplate(
            id="code_developer",
            name="Code Developer",
            intent="CODE",
            capabilities=["file_read", "file_write"],
            security_level="L3_ADMIN",
        )
        assert t.id == "code_developer"
        assert t.current_version == "1.0"
        assert len(t.capabilities) == 2

    def test_template_version_defaults(self):
        from expertise.template_registry import TemplateVersion

        v = TemplateVersion(
            template_id="test",
            version="1.0",
        )
        assert v.avg_score == 0.0
        assert v.total_invocations == 0
        assert v.config == {}

    def test_performance_record_creation(self):
        from expertise.template_registry import PerformanceRecord

        r = PerformanceRecord(
            template_id="code_developer",
            template_version="1.0",
            trace_id="trace-123",
            final_score=0.85,
            iterations=2,
            corrector_invoked=True,
        )
        assert r.final_score == 0.85
        assert r.corrector_invoked is True

    def test_performance_summary_defaults(self):
        from expertise.template_registry import PerformanceSummary

        s = PerformanceSummary(
            template_id="test",
            template_version="1.0",
        )
        assert s.avg_score == 0.0
        assert s.total_invocations == 0


class TestSeedData:
    """Test seed template definitions."""

    def test_seed_templates_exist(self):
        from expertise.template_registry import _SEED_TEMPLATES

        assert len(_SEED_TEMPLATES) >= 7

        ids = [t["id"] for t in _SEED_TEMPLATES]
        assert "code_developer" in ids
        assert "art_director" in ids
        assert "librarian" in ids
        assert "technical_writer" in ids
        assert "iot_controller" in ids

    def test_seed_templates_have_required_fields(self):
        from expertise.template_registry import _SEED_TEMPLATES

        for seed in _SEED_TEMPLATES:
            assert "id" in seed, f"Missing id in seed: {seed}"
            assert "name" in seed, f"Missing name in seed: {seed}"
            assert "intent" in seed, f"Missing intent in seed: {seed}"
            assert "capabilities" in seed, f"Missing capabilities in seed: {seed}"
            assert isinstance(seed["capabilities"], list)
            assert len(seed["capabilities"]) > 0

    def test_seed_intents_cover_router(self):
        """Seed templates should cover all major router intents."""
        from expertise.template_registry import _SEED_TEMPLATES

        seed_intents = {t["intent"] for t in _SEED_TEMPLATES}
        required_intents = {"CODE", "IMAGE", "3D", "RESEARCH", "DOCUMENTATION", "TRAIN", "IOT_CONTROL"}
        assert required_intents.issubset(seed_intents), f"Missing intents: {required_intents - seed_intents}"


class TestTemplateRegistryWithMockedDB:
    """Test TemplateRegistry methods with mocked psycopg2."""

    @pytest.fixture
    def mock_registry(self):
        """Create a registry with mocked database connection."""
        with patch("expertise.template_registry.TemplateRegistry._get_connection") as mock_conn:
            from expertise.template_registry import TemplateRegistry

            # Create mock connection and cursor
            conn = MagicMock()
            cursor = MagicMock()
            conn.cursor.return_value = cursor
            mock_conn.return_value = conn

            registry = TemplateRegistry(db_url="mock://db")
            registry._pool = MagicMock()  # Skip pool creation

            yield registry, conn, cursor

    def test_get_template_returns_model(self, mock_registry):
        registry, conn, cursor = mock_registry

        cursor.fetchone.return_value = (
            "code_developer", "Code Developer", "Full-stack engineer",
            "CODE", "1.0", "You are a code developer.",
            ["file_read", "file_write"], "L3_ADMIN",
            "qwen2.5-coder:14b", {"temperature": 0.7}, "seed",
        )

        template = registry.get_template("code_developer")
        assert template is not None
        assert template.id == "code_developer"
        assert template.intent == "CODE"
        assert "file_read" in template.capabilities

    def test_get_template_not_found(self, mock_registry):
        registry, conn, cursor = mock_registry
        cursor.fetchone.return_value = None

        template = registry.get_template("nonexistent")
        assert template is None

    def test_get_template_version_latest(self, mock_registry):
        registry, conn, cursor = mock_registry

        cursor.fetchone.return_value = (
            1, "code_developer", "1.2", "You are a developer.",
            ["file_read"], {}, 0.85, 100, 90,
            datetime(2026, 3, 17), datetime(2026, 3, 17),
        )

        version = registry.get_template_version("code_developer", "latest")
        assert version is not None
        assert version.version == "1.2"
        assert version.avg_score == 0.85
        assert version.total_invocations == 100

    def test_record_performance(self, mock_registry):
        from expertise.template_registry import PerformanceRecord

        registry, conn, cursor = mock_registry

        record = PerformanceRecord(
            template_id="code_developer",
            template_version="1.0",
            trace_id="trace-abc",
            final_score=0.92,
            iterations=1,
        )

        result = registry.record_performance(record)
        assert result is True
        assert cursor.execute.call_count == 2  # INSERT + UPDATE
        conn.commit.assert_called_once()

    def test_bump_version(self, mock_registry):
        registry, conn, cursor = mock_registry

        # Mock: current template is at version 1.2
        cursor.fetchone.side_effect = [
            ("1.2", "Current prompt", ["file_read"], {"temp": 0.7}),  # SELECT current
            (5, datetime(2026, 3, 17)),  # INSERT RETURNING
        ]

        new_version = registry.bump_version("code_developer", {"system_prompt": "Updated prompt"})
        assert new_version is not None
        assert new_version.version == "1.3"
        assert new_version.system_prompt == "Updated prompt"

    def test_cache_hit(self, mock_registry):
        """Second call should use cache, not DB."""
        registry, conn, cursor = mock_registry

        cursor.fetchone.return_value = (
            "test", "Test", None, "CODE", "1.0", None,
            ["file_read"], "L2_USER", None, {}, "seed",
        )

        # First call hits DB
        t1 = registry.get_template("test")
        # Second call should use cache
        t2 = registry.get_template("test")

        assert t1 is t2  # Same cached object
        assert cursor.execute.call_count == 1  # Only one DB call

    def test_db_unavailable_returns_none(self):
        """Registry should return None gracefully when DB is down."""
        with patch("expertise.template_registry.TemplateRegistry._get_connection", return_value=None):
            from expertise.template_registry import TemplateRegistry
            registry = TemplateRegistry(db_url="mock://db")
            assert registry.get_template("test") is None
            assert registry.list_templates() == []


class TestAsyncTemplateUpdater:
    """Test the async updater logic."""

    def test_updater_initializes(self):
        from expertise.async_template_updater import AsyncTemplateUpdater

        updater = AsyncTemplateUpdater(registry=MagicMock())
        assert updater._running is False

    @pytest.mark.asyncio
    async def test_updater_start_stop(self):
        from expertise.async_template_updater import AsyncTemplateUpdater

        mock_registry = MagicMock()
        mock_registry.list_templates.return_value = []

        updater = AsyncTemplateUpdater(registry=mock_registry)
        await updater.start()
        assert updater._running is True

        await updater.stop()
        assert updater._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
