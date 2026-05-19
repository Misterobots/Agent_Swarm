"""
Skill Registry — Central catalog for MCP skills.

Each skill is a named, versioned unit with:
  - Trigger conditions (intents, keywords, regex patterns)
  - Required capabilities (checked at execution time)
  - A handler callable that receives (arguments: dict) → dict
  - Metadata for discovery and UI display

Usage:
    from skill_registry import skill_registry, Skill

    skill_registry.register(Skill(
        name="summarize",
        category="text",
        description="Summarize long text into key points",
        handler=summarize_handler,
        triggers=SkillTriggers(intents=["EXPLAIN", "RESEARCH"]),
        required_capabilities=["file_ops.read"],
    ))

    # Auto-resolve skills for an intent
    skills = skill_registry.resolve("EXPLAIN")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SkillRegistry")


@dataclass
class SkillTriggers:
    """Conditions under which a skill should auto-activate."""
    intents: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)  # regex patterns


@dataclass
class Skill:
    """A registered skill unit."""
    name: str
    category: str  # "browser", "bash", "code_analysis", "text", "iot", etc.
    description: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    triggers: SkillTriggers = field(default_factory=SkillTriggers)
    required_capabilities: List[str] = field(default_factory=list)
    min_security_level: str = "L2_USER"
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


class SkillRegistry:
    """Central registry for all skills.

    Skills are stored by name and can be resolved by intent, keyword, or
    regex pattern matching against user input.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            logger.warning(f"[SkillRegistry] Overwriting existing skill: {skill.name}")
        self._skills[skill.name] = skill
        logger.info(f"[SkillRegistry] Registered skill: {skill.name} (category={skill.category})")

    def unregister(self, name: str) -> bool:
        if name in self._skills:
            del self._skills[name]
            logger.info(f"[SkillRegistry] Unregistered skill: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self, category: Optional[str] = None, enabled_only: bool = True) -> List[Skill]:
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        if category:
            skills = [s for s in skills if s.category == category]
        return skills

    def resolve(self, intent: str, user_input: str = "") -> List[Skill]:
        """Find all skills that should activate for a given intent + input.

        Resolution order:
          1. Skills whose triggers.intents include the intent
          2. Skills whose triggers.keywords appear in user_input
          3. Skills whose triggers.patterns match user_input
        """
        matched: Dict[str, Skill] = {}
        intent_upper = intent.upper()
        input_lower = user_input.lower()

        for skill in self._skills.values():
            if not skill.enabled:
                continue

            # Intent match
            if intent_upper in [i.upper() for i in skill.triggers.intents]:
                matched[skill.name] = skill
                continue

            # Keyword match
            if input_lower and any(kw.lower() in input_lower for kw in skill.triggers.keywords):
                matched[skill.name] = skill
                continue

            # Regex pattern match
            if user_input and any(re.search(p, user_input, re.IGNORECASE) for p in skill.triggers.patterns):
                matched[skill.name] = skill
                continue

        return list(matched.values())

    def to_mcp_descriptors(self) -> List[Dict[str, Any]]:
        """Export all enabled skills as MCP tool descriptors for tools/list."""
        descriptors = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            descriptors.append({
                "name": f"skill.{skill.name}",
                "description": skill.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input text or data for the skill"},
                    },
                },
                "metadata": {
                    "category": skill.category,
                    "version": skill.version,
                    "tags": skill.tags,
                    "min_security_level": skill.min_security_level,
                },
            })
        return descriptors

    @property
    def count(self) -> int:
        return len(self._skills)


# Global singleton
skill_registry = SkillRegistry()
