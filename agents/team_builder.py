"""
team_builder.py — Role-based model configuration storage.

Stores per-user team builder configurations (which model each agent role uses).
Stored in JSON files at: /workspace/user_projects/{uid}/team_config.json

Each config maps role names to model names:
{
  "coordinator": "gemma4:31b",
  "coder": "qwen2.5-coder:14b",
  ...
}

Validation uses model_registry to enforce:
- Model must exist in the registry and be available locally
- Model must support the assigned role
- Soft warnings for sub-optimal assignments (e.g. small model as coordinator)
- VRAM budget advisory for the combined team configuration
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def get_available_models_for_role(role: str) -> List[dict]:
    """
    Return all available models suitable for a given role, formatted for the UI.
    Each entry includes name, description, tier, vram_gb, and recommended flag.
    """
    try:
        from model_registry import get_models_for_role
        specs = get_models_for_role(role)
        return [
            {
                **s.to_dict(),
                "recommended": role in s.recommended_for_roles,
            }
            for s in specs
        ]
    except Exception as e:
        logger.warning(f"[TeamBuilder] Could not load model registry: {e}")
        return []


def get_all_models_by_role() -> Dict[str, List[dict]]:
    """Return available models grouped by role — used by the team builder UI."""
    return {role: get_available_models_for_role(role) for role in sorted(VALID_ROLES)}


def validate_team_config(config: Dict[str, str]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a full team configuration before saving.

    Returns:
        (is_valid, errors, warnings)
        - errors:   hard failures that must be fixed (block save)
        - warnings: soft advisories shown to the user but don't block save

    Checks:
        1. Role name validity
        2. Model is in registry and available
        3. Model supports the assigned role
        4. VRAM advisory: warn if total large-model VRAM > 28 GB
           (leaves ~4 GB headroom on dual 5060 Ti)
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        from model_registry import validate_role_model, get_model, LARGE_MODEL_VRAM_THRESHOLD_GB
    except ImportError as e:
        warnings.append(f"Model registry unavailable — skipping validation: {e}")
        return True, errors, warnings

    # 1. Role validity
    invalid_roles = [r for r in config.keys() if r not in VALID_ROLES]
    for r in invalid_roles:
        errors.append(f"'{r}' is not a valid role. Valid roles: {', '.join(sorted(VALID_ROLES))}.")

    # 2 & 3. Per-role model validation
    large_vram_total = 0.0
    for role, model_name in config.items():
        if role in invalid_roles:
            continue
        if not model_name:
            continue

        is_valid, msg = validate_role_model(role, model_name)
        if not is_valid:
            errors.append(f"[{role}] {msg}")
        elif msg:
            warnings.append(f"[{role}] {msg}")

        spec = get_model(model_name)
        if spec and spec.vram_gb > LARGE_MODEL_VRAM_THRESHOLD_GB:
            large_vram_total += spec.vram_gb

    # 4. VRAM budget advisory (Lovelace has 32 GB total)
    # Two different large models can't be loaded simultaneously if their combined
    # VRAM > 28 GB. We warn rather than block — the queue system handles runtime
    # contention, but this helps users understand why they may see queuing.
    if large_vram_total > 28.0:
        unique_large = {
            m for r, m in config.items()
            if r not in invalid_roles
            and get_model(m) is not None
            and get_model(m).vram_gb > LARGE_MODEL_VRAM_THRESHOLD_GB
        }
        if len(unique_large) > 1:
            warnings.append(
                f"Your team uses multiple large models that can't all fit in VRAM "
                f"simultaneously ({', '.join(unique_large)}). "
                "The queue system will manage loading automatically, but expect "
                "model-swap delays (~15–20 s) when roles switch."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


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


def save_team_config(uid: str, config: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Validate and save the user's team builder configuration.

    Args:
        uid: User identifier
        config: Dict mapping role → model name

    Returns:
        Dict with keys 'errors' and 'warnings' (both are lists of strings).
        Raises ValueError on hard validation failures (errors non-empty).
    """
    is_valid, errors, warnings = validate_team_config(config)

    if not is_valid:
        raise ValueError(
            f"Team configuration has {len(errors)} error(s): "
            + "; ".join(errors)
        )

    # Filter empty values after validation
    filtered_config = {k: v for k, v in config.items() if v and k in VALID_ROLES}

    config_path = _get_user_team_config_path(uid)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(filtered_config, f, indent=2)
        logger.info(f"[TeamBuilder] Saved config for user {uid}: {list(filtered_config.keys())}")
    except Exception as e:
        logger.error(f"[TeamBuilder] Error saving config for {uid}: {e}")
        raise

    return {"errors": errors, "warnings": warnings}


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
