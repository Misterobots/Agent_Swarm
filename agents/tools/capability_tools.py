"""
Capability Introspection & Governance Tools
=============================================

Two callable tools that give agents real introspection into the Hive's
capabilities and a bridge to the governance system for requesting access
to missing tooling.

Used by the Conversationalist (and any agent handling meta-questions) so
that capability inquiries produce real registry lookups — not LLM hallucinations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("CapabilityTools")


# ---------------------------------------------------------------------------
# Tool 1: check_capability
# ---------------------------------------------------------------------------

def check_capability(capability_name: str) -> str:
    """Check whether a specific capability or tool is available in the Hive system.

    Use this whenever the user asks about access to a specific tool, capability,
    or functionality (e.g., "Do you have access to Browser?", "Can you search the web?").

    Args:
        capability_name: The capability to look up (e.g. "browser", "terminal", "iot",
                         "file_ops", "image_gen", "voice", "git").
                         Partial names are matched — "browser" matches "browser.fetch",
                         "browser.search", etc.

    Returns:
        A human-readable report of the capability's availability, which agents
        have it, and any governance actions needed.
    """
    capability_name = capability_name.strip().lower()
    if not capability_name:
        return "No capability name provided. Please specify what you want to check (e.g. 'browser', 'terminal', 'iot')."

    results: List[str] = []

    # --- 1. Check AgentRegistry ---
    try:
        from registry import registry as agent_registry
        agent_matches = []
        for card in agent_registry.list_agents():
            matching_caps = [
                c for c in card.capabilities
                if capability_name in c.lower()
            ]
            if matching_caps:
                agent_matches.append({
                    "agent": card.name,
                    "role": card.role,
                    "security_level": card.security_level,
                    "capabilities": matching_caps,
                    "endpoint": card.endpoint,
                })

        if agent_matches:
            results.append(f"**Agent Registry** — {len(agent_matches)} agent(s) have '{capability_name}' capabilities:")
            for m in agent_matches:
                caps_str = ", ".join(m["capabilities"])
                results.append(f"  • **{m['agent']}** ({m['role']}, {m['security_level']}): [{caps_str}]")
        else:
            results.append(f"**Agent Registry** — No agents have '{capability_name}' capabilities registered.")
    except Exception as e:
        logger.error(f"[CapabilityTools] AgentRegistry lookup failed: {e}")
        results.append(f"**Agent Registry** — Lookup error: {e}")

    # --- 2. Check SkillRegistry ---
    try:
        from skill_registry import skill_registry
        skill_matches = []
        for skill in skill_registry.list_skills(enabled_only=False):
            name_match = capability_name in skill.name.lower()
            cat_match = capability_name in skill.category.lower()
            cap_match = any(capability_name in c.lower() for c in skill.required_capabilities)
            tag_match = any(capability_name in t.lower() for t in skill.tags)
            desc_match = capability_name in skill.description.lower()
            if name_match or cat_match or cap_match or tag_match or desc_match:
                skill_matches.append(skill)

        if skill_matches:
            results.append(f"\n**Skill Registry** — {len(skill_matches)} skill(s) match '{capability_name}':")
            for s in skill_matches:
                status = "✅ Enabled" if s.enabled else "❌ Disabled"
                results.append(
                    f"  • **{s.name}** ({s.category}) — {s.description} "
                    f"[{status}, requires: {', '.join(s.required_capabilities)}, "
                    f"min level: {s.min_security_level}]"
                )
        else:
            results.append(f"\n**Skill Registry** — No skills match '{capability_name}'.")
    except Exception as e:
        logger.error(f"[CapabilityTools] SkillRegistry lookup failed: {e}")
        results.append(f"\n**Skill Registry** — Lookup error: {e}")

    # --- 3. Check Intent-Capability Map ---
    try:
        from intent_capabilities import INTENT_CAPABILITY_MAP
        intent_matches = []
        for intent, profile in INTENT_CAPABILITY_MAP.items():
            matching_caps = [
                c for c in profile.get("capabilities", [])
                if capability_name in c.lower()
            ]
            if matching_caps:
                intent_matches.append({
                    "intent": intent,
                    "agent": profile.get("agent_name", "unknown"),
                    "caps": matching_caps,
                })

        if intent_matches:
            results.append(f"\n**Intent Routing** — '{capability_name}' is available through these intents:")
            for m in intent_matches:
                results.append(f"  • Intent **{m['intent']}** → {m['agent']}: [{', '.join(m['caps'])}]")
        else:
            results.append(f"\n**Intent Routing** — No intents map to '{capability_name}' capabilities.")
    except Exception as e:
        logger.error(f"[CapabilityTools] IntentCapabilities lookup failed: {e}")

    # --- Summary ---
    has_agents = "No agents" not in results[0] if results else False
    has_skills = any("Skill Registry" in r and "skill(s) match" in r for r in results)

    if has_agents or has_skills:
        results.append(f"\n**Summary**: '{capability_name}' capability IS available in the Hive system.")
    else:
        results.append(
            f"\n**Summary**: '{capability_name}' capability is NOT currently available. "
            f"You can request access through the governance system using the request_tooling_access tool."
        )

    return "\n".join(results)


# ---------------------------------------------------------------------------
# Tool 2: request_tooling_access
# ---------------------------------------------------------------------------

def request_tooling_access(capability: str, reason: str) -> str:
    """Submit a governance request to gain access to a missing capability or tool.

    Use this when check_capability shows a capability is missing or the user
    explicitly asks to request access to new tooling.

    Args:
        capability: The capability being requested (e.g. "browser.fetch", "voice.clone").
        reason: Why this capability is needed (user's stated purpose).

    Returns:
        A confirmation message with the governance request ID and status.
    """
    capability = capability.strip()
    reason = reason.strip()

    if not capability:
        return "Please specify which capability you need (e.g. 'browser.fetch', 'voice.clone')."
    if not reason:
        return "Please provide a reason for the request so it can be properly assessed."

    try:
        from governance import governance_manager, RequestType

        description = f"Tooling access request: {capability} — Reason: {reason}"
        request = governance_manager.submit_request(
            type=RequestType.FEATURE,
            description=description,
            user="hive_user",
        )

        status_emoji = {
            "PENDING": "🟡",
            "APPROVED": "🟢",
            "REJECTED": "🔴",
            "ASSESSING": "🔵",
        }
        emoji = status_emoji.get(request.status, "⚪")

        result = (
            f"**Governance Request Submitted**\n"
            f"  • Request ID: `{request.id}`\n"
            f"  • Type: {request.type}\n"
            f"  • Capability: {capability}\n"
            f"  • Status: {emoji} {request.status}\n"
        )

        if request.assessment_notes:
            result += "  • Assessment Notes:\n"
            for note in request.assessment_notes:
                result += f"    - {note}\n"

        if request.status == "REJECTED":
            result += "\n⚠️ Request was auto-rejected by security assessment. An admin can override this."
        elif request.status == "PENDING":
            result += "\n📋 Request is pending admin review. You'll be notified when it's processed."

        return result

    except Exception as e:
        logger.error(f"[CapabilityTools] Governance request failed: {e}")
        return f"Failed to submit governance request: {e}. Please try again or contact an admin."
