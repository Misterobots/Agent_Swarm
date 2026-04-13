"""
Skill Loader — Auto-discovery and registration of built-in skills.

The Superpowers framework: skills declare their trigger conditions and the
loader automatically registers them into the SkillRegistry at startup.
The router then resolves applicable skills before dispatching to agents.

Call ``initialize_skills()`` once during app lifespan startup.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from skill_registry import skill_registry, Skill, SkillTriggers

logger = logging.getLogger("SkillLoader")


# ---------------------------------------------------------------------------
# Built-in skill handlers
# ---------------------------------------------------------------------------

def _handle_web_fetch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch a web page and return its text content."""
    from tools.web_browser import fetch_page
    url = str(args.get("url") or args.get("input", ""))
    if not url:
        return {"isError": True, "content": [{"type": "text", "text": "No URL provided"}]}
    result = fetch_page(url)
    return {"isError": result.get("error", False), "content": [{"type": "text", "text": result.get("text", "")}]}


def _handle_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search the web and return results."""
    from tools.web_browser import web_search
    query = str(args.get("query") or args.get("input", ""))
    if not query:
        return {"isError": True, "content": [{"type": "text", "text": "No query provided"}]}
    results = web_search(query)
    text = "\n".join(f"- [{r['title']}]({r['url']}): {r['snippet']}" for r in results)
    return {"isError": False, "content": [{"type": "text", "text": text or "No results found"}]}


def _handle_bash_classify(args: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a bash command for safety."""
    from tools.bash_classifier import classify_command
    command = str(args.get("command") or args.get("input", ""))
    if not command:
        return {"isError": True, "content": [{"type": "text", "text": "No command provided"}]}
    result = classify_command(command)
    return {"isError": False, "content": [{"type": "text", "text": str(result)}]}


def _handle_bash_parse(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a bash command into structural components."""
    from tools.bash_parser import parse_bash
    command = str(args.get("command") or args.get("input", ""))
    if not command:
        return {"isError": True, "content": [{"type": "text", "text": "No command provided"}]}
    result = parse_bash(command)
    return {"isError": False, "content": [{"type": "text", "text": str(result)}]}


# ---------------------------------------------------------------------------
# Skill definitions
# ---------------------------------------------------------------------------

BUILTIN_SKILLS = [
    Skill(
        name="web_fetch",
        category="browser",
        description="Fetch a web page and extract its text content",
        handler=_handle_web_fetch,
        triggers=SkillTriggers(
            intents=["RESEARCH"],
            keywords=["fetch", "browse", "webpage", "website", "url"],
            patterns=[r"https?://"],
        ),
        required_capabilities=["browser.fetch"],
        min_security_level="L2_USER",
        tags=["web", "browser", "research"],
    ),
    Skill(
        name="web_search",
        category="browser",
        description="Search the web for information",
        handler=_handle_web_search,
        triggers=SkillTriggers(
            intents=["RESEARCH"],
            keywords=["search", "look up", "find online", "google"],
        ),
        required_capabilities=["browser.search"],
        min_security_level="L2_USER",
        tags=["web", "search", "research"],
    ),
    Skill(
        name="bash_classify",
        category="bash",
        description="Classify a bash command for safety risk level",
        handler=_handle_bash_classify,
        triggers=SkillTriggers(
            intents=["CODE", "DEVOPS"],
            keywords=["is it safe", "check command", "classify command"],
        ),
        required_capabilities=["terminal.classify"],
        min_security_level="L2_USER",
        tags=["bash", "security", "classification"],
    ),
    Skill(
        name="bash_parse",
        category="bash",
        description="Parse a bash command into structural components (AST)",
        handler=_handle_bash_parse,
        triggers=SkillTriggers(
            intents=["CODE", "DEVOPS"],
            keywords=["parse command", "analyze command", "bash ast"],
        ),
        required_capabilities=["terminal.parse"],
        min_security_level="L2_USER",
        tags=["bash", "parser", "tree-sitter"],
    ),
]


def initialize_skills() -> int:
    """Register all built-in skills and return the count."""
    registered = 0
    for skill in BUILTIN_SKILLS:
        try:
            skill_registry.register(skill)
            registered += 1
        except Exception as e:
            logger.error(f"[SkillLoader] Failed to register skill '{skill.name}': {e}")
    logger.info(f"[SkillLoader] Initialized {registered}/{len(BUILTIN_SKILLS)} built-in skills")
    return registered
