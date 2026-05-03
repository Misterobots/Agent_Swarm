"""
team_builder.py — Role-based model configuration storage.

Stores per-user team builder configurations (which model each agent role uses).
Stored in JSON files at: /workspace/user_projects/{uid}/team_config.json

Each config maps role names to model names:
{
  "coordinator": "qwen3:14b",
  "coder": "qwen2.5-coder:14b",
  "devops": "nemotron:70b",
  ...
}
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from logger_setup import setup_logger

logger = setup_logger("team_builder")

# Base directory for user projects
USER_PROJECTS_DIR = Path(os.getenv("USER_PROJECTS_DIR", "/workspace/user_projects"))
TEAM_CONFIG_FILENAME = "team_config.json"

# Valid role names (must match coordinator and config.py role names)
VALID_ROLES = {
    "coordinator",
    "architect",
    "coder",
    "devops",
    "researcher",
    "analyst",
    "verifier",
}


def _get_user_team_config_path(uid: str) -> Path:
    """Get the path to a user's team configuration file."""
    user_dir = USER_PROJECTS_DIR / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / TEAM_CONFIG_FILENAME


def get_team_config(uid: str) -> Dict[str, str]:
    """
    Load the user's team builder configuration.
    Returns a dict mapping role → model name.
    If no config exists, returns empty dict (will use defaults).
    """
    config_path = _get_user_team_config_path(uid)
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Validate role names
        validated = {k: v for k, v in config.items() if k in VALID_ROLES and v}
        if len(validated) != len(config):
            logger.warning(f"[TeamBuilder] User {uid} has invalid roles in config, filtered them out")
        
        return validated
    except Exception as e:
        logger.error(f"[TeamBuilder] Error loading config for {uid}: {e}")
        return {}


def save_team_config(uid: str, config: Dict[str, str]) -> None:
    """
    Save the user's team builder configuration.
    
    Args:
        uid: User identifier
        config: Dict mapping role → model name
    
    Raises:
        ValueError: If config contains invalid role names
    """
    # Validate roles
    invalid_roles = [r for r in config.keys() if r not in VALID_ROLES]
    if invalid_roles:
        raise ValueError(f"Invalid role names: {invalid_roles}. Valid roles: {VALID_ROLES}")
    
    # Filter empty values
    filtered_config = {k: v for k, v in config.items() if v}
    
    config_path = _get_user_team_config_path(uid)
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(filtered_config, f, indent=2)
        logger.info(f"[TeamBuilder] Saved config for user {uid}: {list(filtered_config.keys())}")
    except Exception as e:
        logger.error(f"[TeamBuilder] Error saving config for {uid}: {e}")
        raise


def get_model_for_role(uid: str, role: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get the configured model for a specific role for a user.
    
    Args:
        uid: User identifier
        role: Role name (coordinator, coder, devops, etc.)
        default: Default model to return if not configured
    
    Returns:
        Model name, or default if not configured
    """
    config = get_team_config(uid)
    return config.get(role, default)


def clear_team_config(uid: str) -> bool:
    """
    Clear the user's team builder configuration (reset to defaults).
    
    Args:
        uid: User identifier
    
    Returns:
        True if config was deleted, False if it didn't exist
    """
    config_path = _get_user_team_config_path(uid)
    if config_path.exists():
        config_path.unlink()
        logger.info(f"[TeamBuilder] Cleared config for user {uid}")
        return True
    return False
