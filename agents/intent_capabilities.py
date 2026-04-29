"""
Intent-to-Capability Mapping
==============================

Maps SemanticRouter intents to agent capabilities, security levels,
and template IDs for JWT-ACE token issuance.

Aligned with agents/registry.py AgentCard definitions and
agents/security/capability_gate.py STANDARD_CAPABILITIES.
"""

# Each intent maps to the agent identity and capabilities needed to service it.
# Used by router.py to build EphemeralAgentCards after intent classification.

INTENT_CAPABILITY_MAP = {
    "CODE": {
        "agent_name": "Code Developer",
        "template_id": "code_developer",
        "capabilities": [
            "file_read", "file_write", "file_delete",
            "terminal_exec", "terminal_read",
            "git_read", "git_write",
            "model_generate",
            "api_call",
        ],
        "security_level": "L3_ADMIN",
        "expiry_hours": 2,
    },
    "IMAGE": {
        "agent_name": "Art Director",
        "template_id": "art_director",
        "capabilities": [
            "image_generate", "image_upload",
            "file_read",
            "model_generate",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 1,
    },
    "3D": {
        "agent_name": "Art Director",
        "template_id": "3d_creator",
        "capabilities": [
            "image_generate", "image_upload",
            "file_read", "file_write",
            "model_generate",
            "resource_access",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 2,
    },
    "ACTION_FIGURE": {
        "agent_name": "Action Figure Forge",
        "template_id": "action_figure_creator",
        "capabilities": [
            "image_generate", "image_upload",
            "file_read", "file_write",
            "model_generate",
            "resource_access",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 2,
    },
    "RESEARCH": {
        "agent_name": "Librarian",
        "template_id": "librarian",
        "capabilities": [
            "model_generate",
            "api_call",
            "file_read",
        ],
        "security_level": "L1_PUBLIC",
        "expiry_hours": 1,
    },
    "DOCUMENTATION": {
        "agent_name": "Technical Writer",
        "template_id": "technical_writer",
        "capabilities": [
            "model_generate",
            "file_read",
            "api_call",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 1,
    },
    "TRAIN": {
        "agent_name": "Memory Controller",
        "template_id": "memory_controller",
        "capabilities": [
            "db_read", "db_write",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 1,
    },
    "IOT_CONTROL": {
        "agent_name": "IoT Controller",
        "template_id": "iot_controller",
        "capabilities": [
            "api_call",
            "model_generate",
        ],
        "security_level": "L2_USER",
        "expiry_hours": 1,
    },
    "IOT_DEV": {
        "agent_name": "IoT Controller",
        "template_id": "iot_developer",
        "capabilities": [
            "file_read", "file_write",
            "terminal_exec", "terminal_read",
            "api_call",
            "model_generate",
        ],
        "security_level": "L3_ADMIN",
        "expiry_hours": 2,
    },
    "VISION": {
        "agent_name": "Vision Analyst",
        "template_id": "vision_analyst",
        "capabilities": [
            "image_read",
            "model_generate",
            "file_read",
        ],
        "security_level": "L1_PUBLIC",
        "expiry_hours": 1,
    },
    "COORDINATE": {
        "agent_name": "Coordinator",
        "template_id": "coordinator",
        "capabilities": [
            "model_generate",
            "file_read", "file_write",
            "terminal_exec", "terminal_read",
            "api_call",
            "resource_access",
        ],
        "security_level": "L3_ADMIN",
        "expiry_hours": 4,
    },
    "CONVERSATION": {
        "agent_name": "Hive Mind",
        "template_id": "conversationalist",
        "capabilities": [
            "model_generate",
            # Baseline: conversation only for L1_PUBLIC/L2_USER
            # Developer mode adds workspace-scoped file/terminal
            # L3_ADMIN adds full system access + git operations
        ],
        "security_level": "L1_PUBLIC",
        "expiry_hours": 1,
    },
}

# Safe default for unknown or AMBIGUOUS intents
DEFAULT_CAPABILITIES = {
    "agent_name": "Router",
    "template_id": "default",
    "capabilities": ["model_generate"],
    "security_level": "L1_PUBLIC",
    "expiry_hours": 1,
}


def get_capabilities_for_intent(intent: str) -> dict:
    """
    Look up capability profile for a given intent.

    Args:
        intent: SemanticRouter intent string (e.g., "CODE", "IMAGE")

    Returns:
        Dict with agent_name, template_id, capabilities, security_level, expiry_hours
    """
    return INTENT_CAPABILITY_MAP.get(intent, DEFAULT_CAPABILITIES)


def get_session_capabilities() -> dict:
    """
    Return a *session-level* capability profile suitable for a long-lived
    agent card that spans multiple intents.

    The capability set is the **union** of all known intent capabilities,
    the security level is the highest defined, and the expiry is the longest.
    Per-intent narrowing happens via active_scope in the execution context.
    """
    all_caps: set[str] = set()
    max_level = "L1_PUBLIC"
    max_expiry = 1
    level_order = ["L1_PUBLIC", "L2_USER", "L3_ADMIN", "L4_SYSTEM"]

    for profile in INTENT_CAPABILITY_MAP.values():
        all_caps.update(profile.get("capabilities", []))
        lvl = profile.get("security_level", "L1_PUBLIC")
        if lvl in level_order and level_order.index(lvl) > level_order.index(max_level):
            max_level = lvl
        exp = profile.get("expiry_hours", 1)
        if exp > max_expiry:
            max_expiry = exp

    return {
        "agent_name": "SessionAgent",
        "template_id": "session_agent",
        "capabilities": sorted(all_caps),
        "security_level": max_level,
        "expiry_hours": max_expiry,
    }
