"""
tests/test_skill_registry.py

Unit tests for the Skill Registry (MCP_SKILLS) and Skill Loader (Superpowers).

Run:
    pytest tests/test_skill_registry.py -v
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure agents dir is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


# ═══════════════════════════════════════════════════════════════════════════
# SkillRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillRegistry:
    def _make_registry(self):
        from skill_registry import SkillRegistry
        return SkillRegistry()

    def _make_skill(self, **overrides):
        from skill_registry import Skill, SkillTriggers
        defaults = {
            "name": "test_skill",
            "category": "test",
            "description": "A test skill",
            "handler": lambda args: {"isError": False, "content": [{"type": "text", "text": "ok"}]},
            "triggers": SkillTriggers(),
        }
        defaults.update(overrides)
        return Skill(**defaults)

    def test_register_and_get(self):
        reg = self._make_registry()
        skill = self._make_skill(name="foo")
        reg.register(skill)
        assert reg.get("foo") is skill

    def test_get_nonexistent_returns_none(self):
        reg = self._make_registry()
        assert reg.get("nonexistent") is None

    def test_unregister(self):
        reg = self._make_registry()
        reg.register(self._make_skill(name="bar"))
        assert reg.unregister("bar") is True
        assert reg.get("bar") is None

    def test_unregister_nonexistent(self):
        reg = self._make_registry()
        assert reg.unregister("nope") is False

    def test_list_skills(self):
        reg = self._make_registry()
        reg.register(self._make_skill(name="a", category="browser"))
        reg.register(self._make_skill(name="b", category="bash"))
        reg.register(self._make_skill(name="c", category="browser"))
        assert len(reg.list_skills()) == 3
        assert len(reg.list_skills(category="browser")) == 2
        assert len(reg.list_skills(category="bash")) == 1

    def test_list_enabled_only(self):
        reg = self._make_registry()
        reg.register(self._make_skill(name="on", enabled=True))
        reg.register(self._make_skill(name="off", enabled=False))
        assert len(reg.list_skills(enabled_only=True)) == 1
        assert len(reg.list_skills(enabled_only=False)) == 2

    def test_count(self):
        reg = self._make_registry()
        assert reg.count == 0
        reg.register(self._make_skill(name="x"))
        assert reg.count == 1

    def test_overwrite_warning(self):
        reg = self._make_registry()
        reg.register(self._make_skill(name="dup"))
        reg.register(self._make_skill(name="dup", description="new"))
        assert reg.get("dup").description == "new"
        assert reg.count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Skill Resolution Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillResolution:
    def _make_registry_with_skills(self):
        from skill_registry import SkillRegistry, Skill, SkillTriggers
        reg = SkillRegistry()
        handler = lambda args: {}

        reg.register(Skill(
            name="web_fetch",
            category="browser",
            description="Fetch pages",
            handler=handler,
            triggers=SkillTriggers(intents=["RESEARCH"], keywords=["fetch", "browse"]),
        ))
        reg.register(Skill(
            name="bash_classify",
            category="bash",
            description="Classify commands",
            handler=handler,
            triggers=SkillTriggers(intents=["CODE", "DEVOPS"], keywords=["classify"]),
        ))
        reg.register(Skill(
            name="url_detect",
            category="browser",
            description="Detect URLs",
            handler=handler,
            triggers=SkillTriggers(patterns=[r"https?://"]),
        ))
        reg.register(Skill(
            name="disabled_skill",
            category="test",
            description="Should not resolve",
            handler=handler,
            triggers=SkillTriggers(intents=["RESEARCH"]),
            enabled=False,
        ))
        return reg

    def test_resolve_by_intent(self):
        reg = self._make_registry_with_skills()
        skills = reg.resolve("RESEARCH")
        names = [s.name for s in skills]
        assert "web_fetch" in names
        assert "disabled_skill" not in names

    def test_resolve_by_keyword(self):
        reg = self._make_registry_with_skills()
        skills = reg.resolve("UNKNOWN", user_input="please classify this command")
        names = [s.name for s in skills]
        assert "bash_classify" in names

    def test_resolve_by_pattern(self):
        reg = self._make_registry_with_skills()
        skills = reg.resolve("GENERAL", user_input="check https://example.com")
        names = [s.name for s in skills]
        assert "url_detect" in names

    def test_resolve_no_match(self):
        reg = self._make_registry_with_skills()
        skills = reg.resolve("IMAGE", user_input="draw a cat")
        assert len(skills) == 0

    def test_resolve_case_insensitive_intent(self):
        reg = self._make_registry_with_skills()
        skills = reg.resolve("research")  # lowercase
        names = [s.name for s in skills]
        assert "web_fetch" in names


# ═══════════════════════════════════════════════════════════════════════════
# MCP Descriptor Export Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPDescriptors:
    def test_to_mcp_descriptors(self):
        from skill_registry import SkillRegistry, Skill, SkillTriggers
        reg = SkillRegistry()
        reg.register(Skill(
            name="test",
            category="general",
            description="Test skill",
            handler=lambda a: {},
            version="2.0",
            tags=["testing"],
        ))
        descriptors = reg.to_mcp_descriptors()
        assert len(descriptors) == 1
        d = descriptors[0]
        assert d["name"] == "skill.test"
        assert d["description"] == "Test skill"
        assert d["metadata"]["category"] == "general"
        assert d["metadata"]["version"] == "2.0"
        assert "testing" in d["metadata"]["tags"]

    def test_disabled_skills_excluded(self):
        from skill_registry import SkillRegistry, Skill
        reg = SkillRegistry()
        reg.register(Skill(name="on", category="t", description="", handler=lambda a: {}, enabled=True))
        reg.register(Skill(name="off", category="t", description="", handler=lambda a: {}, enabled=False))
        assert len(reg.to_mcp_descriptors()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Skill Loader Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillLoader:
    def test_initialize_skills_registers_builtins(self):
        # Clear any previous state
        from skill_registry import SkillRegistry
        import skill_registry as sr_mod
        original = sr_mod.skill_registry
        sr_mod.skill_registry = SkillRegistry()

        try:
            from skill_loader import initialize_skills
            count = initialize_skills()
            assert count == 4  # web_fetch, web_search, bash_classify, bash_parse
            assert sr_mod.skill_registry.count == 4
            assert sr_mod.skill_registry.get("web_fetch") is not None
            assert sr_mod.skill_registry.get("web_search") is not None
            assert sr_mod.skill_registry.get("bash_classify") is not None
            assert sr_mod.skill_registry.get("bash_parse") is not None
        finally:
            sr_mod.skill_registry = original

    def test_builtin_skills_have_triggers(self):
        from skill_loader import BUILTIN_SKILLS
        for skill in BUILTIN_SKILLS:
            has_trigger = (
                skill.triggers.intents
                or skill.triggers.keywords
                or skill.triggers.patterns
            )
            assert has_trigger, f"Skill {skill.name} has no triggers"

    def test_builtin_skills_have_capabilities(self):
        from skill_loader import BUILTIN_SKILLS
        for skill in BUILTIN_SKILLS:
            assert skill.required_capabilities, f"Skill {skill.name} has no required capabilities"
