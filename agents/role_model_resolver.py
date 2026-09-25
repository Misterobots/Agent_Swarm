"""
role_model_resolver.py â Team Builder integration for church.py

Helper functions to resolve which model to use for a given role, considering:
1. User's team builder configuration (highest priority)
2. Environment variables (CODER_MODEL, DEVOPS_MODEL, etc.)
3. Default fallbacks (ARCHITECT_MODEL â PRIMARY_MODEL)

Usage in church.py:
    from role_model_resolver import get_model_for_role
    
    # Get model for a specific intent/role
    model = get_model_for_role(uid="user123", role="coder", default=ARCHITECT_MODEL)
"""

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from logger_setup import setup_logger
from config import (
    ARCHITECT_MODEL, CODER_MODEL, DEVOPS_MODEL, RESEARCHER_MODEL,
    ANALYST_MODEL, VERIFIER_MODEL, COORDINATOR_MODEL
)
from config import SWARM_ARCHITECT_MODEL

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

_SWARM_ROLE_ENV_MAP = {
    **_ROLE_ENV_MAP,
    # The swarm architect is a planning role.  Keep it separate from the
    # code-solver ARCHITECT_MODEL used by ordinary code requests.
    "architect": SWARM_ARCHITECT_MODEL,
}

_ROLE_ALIASES = {
    "technical": "researcher",
    "ethical": "researcher",
    "economic": "analyst",
    "scientific": "researcher",
    "regulatory": "researcher",
    "end_user": "analyst",
    "historical": "researcher",
    "policy": "researcher",
    "environmental": "researcher",
    "social": "researcher",
}


def canonical_role(role: str) -> str:
    role_lower = (role or "").lower()
    return _ROLE_ALIASES.get(role_lower, role_lower)


# Roles a coordination run may bind a model to. Kept as a constant because the
# single-model path must bind *every* one of them: a role left out of the map
# falls through to _SWARM_ROLE_ENV_MAP in for_role() and reloads the fan-out
# under a model the user never selected.
_SWARM_ROLES = (
    "coordinator", "architect", "coder", "devops",
    "researcher", "analyst", "verifier",
)

# How a snapshot's role map was produced. SINGLE binds every role to the model
# the user picked; TEAM_BUILDER keeps the per-role assignments.
SNAPSHOT_SOURCE_SINGLE = "single"
SNAPSHOT_SOURCE_TEAM_BUILDER = "team_builder"


@dataclass(frozen=True)
class RoleModelBinding:
    """The model identity assigned to one role for one coordination run."""

    requested_model: str
    actual_model: str
    provider: str = "ollama"
    fallback: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_model": self.requested_model,
            "actual_model": self.actual_model,
            "provider": self.provider,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class RoleModelSnapshot:
    """Immutable owner-scoped role map captured once at run start.

    ``source`` records *why* the map looks the way it does, and is part of the
    checkpoint contract: a restored map must have been built under the same
    source and selected model as the run asking for it, or the user's per-run
    choice is silently overridden by the previous run's file.
    """

    owner_id: Optional[str]
    models: Mapping[str, RoleModelBinding]
    context_profile: Optional[str] = None
    source: str = SNAPSHOT_SOURCE_TEAM_BUILDER
    selected_model: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "models", MappingProxyType(dict(self.models)))

    def for_role(self, role: str, default: Optional[str] = None) -> RoleModelBinding:
        role_lower = canonical_role(role)
        binding = self.models.get(role_lower)
        if binding:
            return binding
        model = default or _SWARM_ROLE_ENV_MAP.get(role_lower) or ARCHITECT_MODEL
        return RoleModelBinding(model, model)

    def with_actual_model(
        self,
        role: str,
        actual_model: str,
        provider: str = "ollama",
        fallback: bool = False,
    ) -> "RoleModelSnapshot":
        """Return a new snapshot after a provider reports its actual model."""
        role_lower = canonical_role(role)
        current = self.for_role(role_lower)
        updated = dict(self.models)
        updated[role_lower] = RoleModelBinding(
            requested_model=current.requested_model,
            actual_model=actual_model,
            provider=provider,
            fallback=fallback,
        )
        return RoleModelSnapshot(
            self.owner_id, updated, self.context_profile,
            source=self.source, selected_model=self.selected_model,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "owner_id": self.owner_id,
            "models": {role: binding.to_dict() for role, binding in self.models.items()},
            "context_profile": self.context_profile,
            "source": self.source,
            "selected_model": self.selected_model,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RoleModelSnapshot":
        models = {}
        for role, raw in (payload.get("models") or {}).items():
            if not isinstance(raw, dict) or not raw.get("requested_model"):
                continue
            requested = str(raw["requested_model"])
            models[canonical_role(str(role))] = RoleModelBinding(
                requested_model=requested,
                actual_model=str(raw.get("actual_model") or requested),
                provider=str(raw.get("provider") or "ollama"),
                fallback=bool(raw.get("fallback", False)),
            )
        source = str(payload.get("source") or SNAPSHOT_SOURCE_TEAM_BUILDER)
        selected = payload.get("selected_model")
        return cls(
            payload.get("owner_id"), models, payload.get("context_profile"),
            source=source if source in (SNAPSHOT_SOURCE_SINGLE, SNAPSHOT_SOURCE_TEAM_BUILDER)
            else SNAPSHOT_SOURCE_TEAM_BUILDER,
            selected_model=str(selected) if selected else None,
        )


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
                logger.debug(f"[RoleResolver] User {uid} role={role_lower} â team config: {team_model}")
                return team_model
        except Exception as e:
            logger.debug(f"[RoleResolver] Failed to load team config for {uid}: {e}")
    
    # Step 2: Check environment variable for role
    env_model = _ROLE_ENV_MAP.get(role_lower)
    if env_model:
        logger.debug(f"[RoleResolver] role={role_lower} â env var: {env_model}")
        return env_model
    
    # Step 3: Use provided default
    if default:
        logger.debug(f"[RoleResolver] role={role_lower} â provided default: {default}")
        return default
    
    # Step 4: Ultimate fallback
    logger.debug(f"[RoleResolver] role={role_lower} â ultimate fallback: {ARCHITECT_MODEL}")
    return ARCHITECT_MODEL


def snapshot_role_models(
    uid: Optional[str],
    context_profile: Optional[str] = None,
    selected_model: Optional[str] = None,
    team_builder_roles: bool = False,
) -> RoleModelSnapshot:
    """Resolve all swarm roles once for a coordination run.

    Two sources, chosen by the caller (which is chosen by the user, per run):

    * **single** (the default) â every role binds to ``selected_model``, so the
      run loads one model. This is what keeps a Collective from fanning out into
      coordinator/researcher/analyst/verifier and evicting other users' resident
      models to do it.
    * **team_builder** â Team Builder values win over defaults. When no Team
      Builder value exists, the swarm architect keeps its dedicated
      SWARM_ARCHITECT_MODEL default while all other roles retain their existing
      config defaults.

    With no ``selected_model`` there is nothing to bind, so the run falls back to
    team-builder resolution rather than inventing a model â ``church.py`` passes
    ``None`` for UI tier labels like ``Home-AI-Swarm`` that are not Ollama ids.
    """
    if not team_builder_roles and selected_model:
        binding = RoleModelBinding(selected_model, selected_model)
        return RoleModelSnapshot(
            uid,
            {role: binding for role in _SWARM_ROLES},
            context_profile,
            source=SNAPSHOT_SOURCE_SINGLE,
            selected_model=selected_model,
        )

    models: dict[str, RoleModelBinding] = {}
    for role in _SWARM_ROLES:
        default = _SWARM_ROLE_ENV_MAP.get(role)
        requested = get_model_for_role(uid, role, default=default)
        models[role] = RoleModelBinding(requested, requested)
    return RoleModelSnapshot(
        uid, models, context_profile, source=SNAPSHOT_SOURCE_TEAM_BUILDER,
    )
