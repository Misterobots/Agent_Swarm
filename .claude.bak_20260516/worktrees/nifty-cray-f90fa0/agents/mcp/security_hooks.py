from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from security.audit_logger import get_audit_logger
from security.token_issuer import EphemeralAgentCard, get_token_validator


SECURITY_RANK = {
    "L1_PUBLIC": 1,
    "L2_USER": 2,
    "L3_ADMIN": 3,
    "L4_SYSTEM": 4,
}


@dataclass
class SecurityDecision:
    allowed: bool
    reason: str
    card: Optional[EphemeralAgentCard] = None


def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:].strip()


def enforce_capability(
    auth_header: str | None,
    required_capability: str,
    resource: str,
    min_level: str = "L2_USER",
) -> SecurityDecision:
    """Validate JWT and enforce capability + minimum security level."""
    audit = get_audit_logger()
    token = _extract_bearer_token(auth_header)
    if not token:
        audit.log_auth_failed(reason="missing_bearer_token", resource=resource)
        return SecurityDecision(False, "Missing bearer token")

    try:
        validator = get_token_validator()
        card = validator.validate_token(token)
    except Exception as e:
        audit.log_auth_failed(reason=f"invalid_token:{e}", resource=resource)
        return SecurityDecision(False, "Invalid token")

    level = str(getattr(card, "security_level", "L1_PUBLIC"))
    if SECURITY_RANK.get(level, 0) < SECURITY_RANK.get(min_level, 0):
        audit.log_capability_denied(
            agent_name=card.agent_name,
            agent_id=card.agent_instance_id,
            capability=required_capability,
            resource=resource,
            available_capabilities=card.activated_capabilities,
            security_level=level,
            reason="insufficient_security_level",
        )
        return SecurityDecision(False, "Insufficient security level", card)

    if required_capability not in (card.activated_capabilities or []):
        audit.log_capability_denied(
            agent_name=card.agent_name,
            agent_id=card.agent_instance_id,
            capability=required_capability,
            resource=resource,
            available_capabilities=card.activated_capabilities,
            security_level=level,
            reason="missing_capability",
        )
        return SecurityDecision(False, f"Missing capability: {required_capability}", card)

    audit.log_capability_granted(
        agent_name=card.agent_name,
        agent_id=card.agent_instance_id,
        capability=required_capability,
        resource=resource,
        security_level=level,
    )
    return SecurityDecision(True, "ok", card)
