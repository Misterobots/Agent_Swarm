"""
role_model_resolver.py — Team Builder integration for church.py

Helper functions to resolve which model to use for a given role, considering:
1. User's team builder configuration (highest priority)
2. Environment variables (CODER_MODEL, DEVOPS_MODEL, etc.)
3. Default fallbacks (ARCHITECT_MODEL → PRIMARY_MODEL)

Usage in church.py:
    from role_model_resolver import get_model_for_role
    
    # Get model for a specific intent/role
    model = get_model_for_role(uid="user123", role="coder", default=ARCHITECT_MODEL)
"""

import os
from typing import Optional

from logger_setup import setup_logger
from config import (
    ARCHITECT_MODEL, CODER_MODEL, DEVOPS_MODEL, RESEARCHER_MODEL,
    ANALYST_MODEL, VERIFIER_MODEL, COORDINATOR_MODEL
)

logger = setup_logger("role_model_resolver")

# Map role names to config variables (fallback when team builder has no config)
_ROLE_ENV_MAP = {
    "coordinator": COORDINATOR_MODEL,
    "architect": ARCHITECT_MODEL,
    "coder": CODER_MODEL,
    "devops": DEVOPS_MODEL,
    "researcher": RESEARCHER_MODEL,
    "analyst": ANALYST_MODEL,
    "verifier": VERIFIER_MODEL,
}


def get_model_for_role(
    uid: Optional[str],
    role: str,
    default: Optional[str] = None
) -> str:
    """
    Resolve which model to use for a given role and user.
    
    Resolution order:
    1. User's team builder configuration (if uid provided and config exists)
    2. Environment variable for that role (e.g., CODER_MODEL)
    3. Provided default parameter
    4. ARCHITECT_MODEL (ultimate fallback)
    
    Args:
        uid: User identifier (from X-authentik-uid header), None for anonymous
        role: Role name (coordinator, coder, devops, etc.)
        default: Fallback model if no configuration found
    
    Returns:
        Model name to use
    """
    role_lower = role.lower()
    
    # Step 1: Check team builder configuration
    if uid:
        try:
            from team_builder import get_model_for_role as get_team_model
            team_model = get_team_model(uid, role_lower, default=None)
            if team_model:
                logger.debug(f"[RoleResolver] User {uid} role={role_lower} → team config: {team_model}")
                return team_model
        except Exception as e:
            logger.debug(f"[RoleResolver] Failed to load team config for {uid}: {e}")
    
    # Step 2: Check environment variable for role
    env_model = _ROLE_ENV_MAP.get(role_lower)
    if env_model:
        logger.debug(f"[RoleResolver] role={role_lower} → env var: {env_model}")
        return env_model
    
    # Step 3: Use provided default
    if default:
        logger.debug(f"[RoleResolver] role={role_lower} → provided default: {default}")
        return default
    
    # Step 4: Ultimate fallback
    logger.debug(f"[RoleResolver] role={role_lower} → ultimate fallback: {ARCHITECT_MODEL}")
    return ARCHITECT_MODEL
