"""
JWT-ACE (Agent Card Embedded JWT) Token Issuer
=============================================

Issues JWT tokens to ephemeral agents with embedded capability claims.
Tokens are cryptographically signed by SPIRE for non-forgeable verification.

Usage:
    issuer = TokenIssuer()
    
    # Create ephemeral agent card
    card = EphemeralAgentCard(
        template_id="security_agent",
        template_version="1.3",
        agent_name="SecurityValidator_001",
        activated_capabilities=["file_read", "api_call"],
        expiry_hours=1
    )
    
    # Issue JWT token
    token = issuer.issue_token(card)
    
    # Pass to API requests
    headers = {"Authorization": f"Bearer {token}"}
"""

import jwt
import os
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
import dataclasses
from dataclasses import dataclass, asdict
from functools import lru_cache
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class EphemeralAgentCard:
    """
    Runtime identity for ephemeral agents.
    Embedded in JWT claims for capability-based access control.

    Lifecycle:
        - Session cards: issued once per session with broad capabilities.
        - Child cards: derived from a parent card for sub-agent workers.
          Capabilities are always a subset of the parent's.
    """
    template_id: str                    # Reference to ExpertiseTemplate
    template_version: str              # "1.3", "2.0", etc.
    agent_name: str                    # "SecurityValidator_001"
    agent_instance_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    activated_capabilities: List[str] = dataclasses.field(default_factory=list)  # ["file_read", "api_call"]
    security_level: str = "L2_USER"    # L1_PUBLIC, L2_USER, L3_ADMIN, L4_SYSTEM
    user_id: Optional[str] = None      # Canonical authenticated user owner (for user tokens)
    session_id: Optional[str] = None   # Link to user session
    parent_id: Optional[str] = None    # Parent card agent_instance_id (for child cards)
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)  # Custom metadata

    # Timestamps (UTC)
    issued_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    expiry_hours: int = 1  # Default 1 hour TTL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JWT encoding."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['issued_at'] = self.issued_at.isoformat()
        # Calculate expiry timestamp
        expiry_time = self.issued_at + timedelta(hours=self.expiry_hours)
        data['exp'] = expiry_time.timestamp()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EphemeralAgentCard":
        """Reconstruct from JWT payload."""
        # Remove JWT reserved claims before creating object
        jwt_claims = {k: v for k, v in data.items() if k not in ['exp', 'iat', 'sub', 'iss', 'aud']}
        if 'issued_at' in jwt_claims and isinstance(jwt_claims['issued_at'], str):
            jwt_claims['issued_at'] = datetime.fromisoformat(jwt_claims['issued_at'])
        return cls(**jwt_claims)


class EphemeralAgentCardModel(BaseModel):
    """Pydantic model for API validation."""
    template_id: str
    template_version: str
    agent_name: str
    agent_instance_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    activated_capabilities: List[str] = Field(default_factory=list)
    security_level: str = "L2_USER"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expiry_hours: int = 1


# Security-level ordering used by derive_child_card.
_SECURITY_LEVEL_ORDER = ["L1_PUBLIC", "L2_USER", "L3_ADMIN", "L4_SYSTEM"]


def derive_child_card(
    parent_card: EphemeralAgentCard,
    child_template_id: str,
    child_agent_name: str,
    child_capabilities: List[str],
    child_security_level: str = "L2_USER",
    task_description: Optional[str] = None,
    expiry_hours: Optional[int] = None,
) -> EphemeralAgentCard:
    """
    Derive a child agent card from a parent card.

    Enforces:
        - Child capabilities ⊆ parent capabilities (intersection applied).
        - Child security_level ≤ parent security_level (capped).
        - parent_id links to parent's agent_instance_id.

    Args:
        parent_card: The parent EphemeralAgentCard.
        child_template_id: Template ID for the child agent.
        child_agent_name: Display name for the child agent.
        child_capabilities: Requested capabilities (will be intersected with parent).
        child_security_level: Requested security level (will be capped).
        task_description: Optional description stored in child metadata.
        expiry_hours: TTL for child card.  Defaults to parent's remaining TTL.

    Returns:
        A new EphemeralAgentCard linked to the parent.
    """
    # Intersect capabilities — child can never exceed parent.
    parent_caps = set(parent_card.activated_capabilities or [])
    effective_caps = [c for c in child_capabilities if c in parent_caps]

    # Cap security level.
    parent_idx = _SECURITY_LEVEL_ORDER.index(parent_card.security_level) \
        if parent_card.security_level in _SECURITY_LEVEL_ORDER else 1
    child_idx = _SECURITY_LEVEL_ORDER.index(child_security_level) \
        if child_security_level in _SECURITY_LEVEL_ORDER else 1
    effective_level = _SECURITY_LEVEL_ORDER[min(parent_idx, child_idx)]

    # Build child metadata.
    child_metadata = {
        "parent_template_id": parent_card.template_id,
    }
    if task_description:
        child_metadata["task_description"] = task_description

    # Default expiry: parent's remaining hours (at least 1).
    if expiry_hours is None:
        elapsed = (datetime.now(timezone.utc) - parent_card.issued_at).total_seconds() / 3600
        remaining = max(1, parent_card.expiry_hours - int(elapsed))
        expiry_hours = remaining

    child = EphemeralAgentCard(
        template_id=child_template_id,
        template_version=parent_card.template_version,
        agent_name=child_agent_name,
        activated_capabilities=effective_caps,
        security_level=effective_level,
        user_id=parent_card.user_id,
        session_id=parent_card.session_id,
        parent_id=parent_card.agent_instance_id,
        expiry_hours=expiry_hours,
        metadata=child_metadata,
    )

    logger.info(
        f"[TokenIssuer] Derived child card {child.agent_instance_id} "
        f"from parent {parent_card.agent_instance_id} "
        f"(caps: {len(effective_caps)}/{len(child_capabilities)}, level: {effective_level})"
    )
    return child


# ============================================================================
# TOKEN ISSUER
# ============================================================================

class TokenIssuer:
    """
    Issues JWT tokens signed by SPIRE for ephemeral agents.
    
    Token Structure:
    {
        "iss": "home-ai-lab-token-issuer",
        "sub": "agent_instance_id", 
        "aud": "home-ai-lab-agents",
        "exp": <timestamp>,
        "iat": <timestamp>,
        "template_id": "security_agent",
        "template_version": "1.3",
        "agent_name": "SecurityValidator_001",
        "activated_capabilities": ["file_read", "api_call"],
        "security_level": "L2_USER",
        "user_id": "user123",
        "session_id": "user123",
        "metadata": {...}
    }
    """
    
    def __init__(self, spire_enabled: bool = True, jwt_secret: Optional[str] = None):
        """
        Initialize token issuer.
        
        Args:
            spire_enabled: Use SPIRE for signing (production). Default True.
            jwt_secret: Fallback secret key (for non-SPIRE env). 
                       Defaults to env var EPHEMERAL_AGENT_JWT_SECRET.
        """
        self.spire_enabled = spire_enabled
        self.jwt_secret = jwt_secret or os.getenv(
            "EPHEMERAL_AGENT_JWT_SECRET",
            "dev-insecure-secret-key-change-in-production"
        )
        
        # Initialize SPIRE client if available
        self.spire_client = None
        if spire_enabled:
            try:
                from security.spiffe_auth import SpiffeAuth
                self.spire_client = SpiffeAuth()
                if self.spire_client.is_available:
                    logger.info("[TokenIssuer] SPIRE signing enabled")
                else:
                    logger.warning("[TokenIssuer] SPIRE not available, falling back to JWT secret")
            except ImportError as e:
                logger.warning(f"[TokenIssuer] SPIRE client not available: {e}")
    
    def issue_token(self, card: EphemeralAgentCard) -> str:
        """
        Issue JWT token for ephemeral agent.
        
        Args:
            card: EphemeralAgentCard with agent identity and capabilities
            
        Returns:
            JWT token (string)
            
        Raises:
            ValueError: If signing fails
        """
        # Build JWT payload
        payload = card.to_dict()
        
        # Add standard JWT claims
        payload['iss'] = 'home-ai-lab-token-issuer'
        payload['aud'] = 'home-ai-lab-agents'
        payload['sub'] = card.agent_instance_id
        payload['iat'] = datetime.now(timezone.utc).timestamp()

        # Standardized owner field for user-scoped tokens.
        if not payload.get('user_id'):
            metadata_owner = (payload.get('metadata') or {}).get('user_id')
            if metadata_owner:
                payload['user_id'] = metadata_owner
        
        # Calculate expiry
        expiry = datetime.now(timezone.utc) + timedelta(hours=card.expiry_hours)
        payload['exp'] = expiry.timestamp()
        
        logger.info(
            f"[TokenIssuer] Issuing token for {card.agent_name} "
            f"(ID: {card.agent_instance_id}) with capabilities: {card.activated_capabilities}"
        )
        
        try:
            # Sign with SPIRE if available, otherwise use JWT secret
            if self.spire_client and self.spire_client.is_available:
                return self._sign_with_spire(payload)
            else:
                return self._sign_with_secret(payload)
        except Exception as e:
            logger.error(f"[TokenIssuer] Failed to issue token: {e}")
            raise ValueError(f"Token issuance failed: {e}")
    
    def _sign_with_secret(self, payload: Dict[str, Any]) -> str:
        """Sign JWT with secret key (fallback for dev/testing)."""
        try:
            token = jwt.encode(
                payload,
                self.jwt_secret,
                algorithm='HS256'
            )
            logger.debug("[TokenIssuer] Token signed with JWT secret")
            return token
        except Exception as e:
            logger.error(f"[TokenIssuer] JWT encoding failed: {e}")
            raise
    
    def _sign_with_spire(self, payload: Dict[str, Any]) -> str:
        """Sign JWT with SPIRE identity (production)."""
        try:
            # Get JWT-SVID from SPIRE
            jwt_svid = self.spire_client.get_jwt_token(
                audience="home-ai-lab-agents"
            )
            
            if not jwt_svid:
                logger.warning("[TokenIssuer] SPIRE JWT unavailable, falling back to secret")
                return self._sign_with_secret(payload)
            
            # SPIRE signs the JWT with workload's private key
            # The returned jwt_svid is already a valid JWT
            # We need to create our own JWT with SPIRE signing
            
            token = jwt.encode(
                payload,
                self.spire_client._client._identity.private_key,  # SPIRE workload private key
                algorithm='RS256'  # SPIRE uses RSA
            )
            logger.debug("[TokenIssuer] Token signed with SPIRE key")
            return token
        except Exception as e:
            logger.warning(f"[TokenIssuer] SPIRE signing failed: {e}, using fallback")
            return self._sign_with_secret(payload)


# ============================================================================
# TOKEN VALIDATOR
# ============================================================================

class TokenValidator:
    """
    Validates JWT tokens and extracts ephemeral agent capability claims.
    Verifies token signature and expiry.

    Includes an in-memory validation cache (LRU, 60 s TTL) to avoid
    repeated cryptographic verification of the same token on rapid requests.
    """

    _CACHE_MAX = 128
    _CACHE_TTL_S = 60
    
    def __init__(self, spire_enabled: bool = True, jwt_secret: Optional[str] = None):
        """
        Initialize token validator.
        
        Args:
            spire_enabled: Verify SPIRE signatures. Default True.
            jwt_secret: Fallback secret key for validation.
                       Defaults to env var EPHEMERAL_AGENT_JWT_SECRET.
        """
        self.spire_enabled = spire_enabled
        self.jwt_secret = jwt_secret or os.getenv(
            "EPHEMERAL_AGENT_JWT_SECRET",
            "dev-insecure-secret-key-change-in-production"
        )

        # Validation cache: token_hash → (EphemeralAgentCard, cached_at)
        self._cache: Dict[str, tuple] = {}
        
        # Initialize SPIRE client
        self.spire_client = None
        if spire_enabled:
            try:
                from security.spiffe_auth import SpiffeAuth
                self.spire_client = SpiffeAuth()
                if self.spire_client.is_available:
                    logger.info("[TokenValidator] SPIRE verification enabled")
            except ImportError as e:
                logger.warning(f"[TokenValidator] SPIRE client not available: {e}")
    
    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, token: str) -> str:
        """Derive a cache key from token (first+last 16 chars + length)."""
        return f"{token[:16]}:{token[-16:]}:{len(token)}"

    def _cache_get(self, token: str) -> Optional[EphemeralAgentCard]:
        key = self._cache_key(token)
        entry = self._cache.get(key)
        if entry is None:
            return None
        card, cached_at = entry
        if (time.time() - cached_at) > self._CACHE_TTL_S:
            del self._cache[key]
            return None
        return card

    def _cache_put(self, token: str, card: EphemeralAgentCard) -> None:
        key = self._cache_key(token)
        # Evict oldest entries if over capacity.
        if len(self._cache) >= self._CACHE_MAX:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (card, time.time())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_token(self, token: str) -> EphemeralAgentCard:
        """
        Backward-compatible default validator.
        Treats the token as a user-scoped JWT-ACE token.
        Uses validation cache to avoid repeated signature verification.
        """
        cached = self._cache_get(token)
        if cached is not None:
            logger.debug("[TokenValidator] Cache hit")
            return cached
        card = self.validate_user_token(token)
        self._cache_put(token, card)
        return card

    def validate_user_token(self, token: str) -> EphemeralAgentCard:
        """Validate a user-scoped JWT-ACE token."""
        logger.debug("[TokenValidator] Validating user token...")

        try:
            claims = self._verify_with_secret(token)
            self._validate_user_claims(claims)

            card = EphemeralAgentCard.from_dict(claims)
            logger.info(
                f"[TokenValidator] Valid user token for {card.agent_name} "
                f"(capabilities: {card.activated_capabilities})"
            )
            return card

        except jwt.ExpiredSignatureError:
            logger.warning("[TokenValidator] User token has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.error(f"[TokenValidator] Invalid user token: {e}")
            raise
        except Exception as e:
            logger.error(f"[TokenValidator] User token validation failed: {e}")
            raise ValueError(f"User token validation failed: {e}")

    def validate_workload_token(self, token: str) -> EphemeralAgentCard:
        """Validate a workload identity token and normalize it into an ephemeral card."""
        logger.debug("[TokenValidator] Validating workload token...")

        try:
            claims = None
            if self.spire_client and self.spire_client.is_available:
                try:
                    claims = self.spire_client.verify_jwt_token(token, "home-ai-lab-agents")
                    if claims:
                        logger.info("[TokenValidator] Workload token verified with SPIFFE client")
                except Exception as e:
                    logger.warning(f"[TokenValidator] SPIFFE workload verification failed: {e}, trying fallback")

            if claims is None:
                claims = self._verify_workload_fallback(token)

            self._validate_workload_claims(claims)
            card = self._build_workload_card(claims)
            logger.info(
                f"[TokenValidator] Valid workload token for {card.agent_name} "
                f"(security_level: {card.security_level})"
            )
            return card

        except jwt.ExpiredSignatureError:
            logger.warning("[TokenValidator] Workload token has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.error(f"[TokenValidator] Invalid workload token: {e}")
            raise
        except Exception as e:
            logger.error(f"[TokenValidator] Workload token validation failed: {e}")
            raise ValueError(f"Workload token validation failed: {e}")

    def _validate_user_claims(self, claims: Dict[str, Any]) -> None:
        """Enforce user-token-specific claim requirements."""
        if claims.get("iss") != "home-ai-lab-token-issuer":
            raise jwt.InvalidIssuerError("Unexpected issuer for user token")

        if not claims.get("sub"):
            raise jwt.InvalidTokenError("User token missing sub claim")

        if not claims.get("user_id") and not (claims.get("metadata") or {}).get("user_id"):
            logger.warning("[TokenValidator] User token missing explicit user_id claim; using fallback owner derivation")

    def _validate_workload_claims(self, claims: Dict[str, Any]) -> None:
        """Enforce workload-token-specific claim requirements."""
        subject = str(claims.get("sub", ""))
        spiffe_id = str(claims.get("spiffe_id", ""))
        issuer = str(claims.get("iss", ""))

        if not (subject.startswith("spiffe://") or spiffe_id.startswith("spiffe://")):
            if "spiffe" not in issuer.lower() and "spire" not in issuer.lower():
                raise jwt.InvalidTokenError("Workload token missing SPIFFE identity claims")

    def _build_workload_card(self, claims: Dict[str, Any]) -> EphemeralAgentCard:
        """Normalize workload claims into EphemeralAgentCard for middleware consumers."""
        workload_id = str(claims.get("spiffe_id") or claims.get("sub") or "unknown-workload")
        return EphemeralAgentCard(
            template_id="spiffe_workload",
            template_version="1.0",
            agent_name=workload_id,
            agent_instance_id=workload_id,
            activated_capabilities=["internal_service"],
            security_level="L4_SYSTEM",
            user_id=None,
            session_id=None,
            metadata={"token_type": "workload", "claims": claims},
            expiry_hours=1,
        )

    def _verify_workload_fallback(self, token: str) -> Dict[str, Any]:
        """Fallback workload verification path for environments without active SPIFFE verification."""
        try:
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=['HS256', 'RS256'],
                audience='home-ai-lab-agents'
            )
            logger.debug("[TokenValidator] Workload token verified via fallback JWT path")
            return claims
        except jwt.InvalidTokenError as e:
            logger.error(f"[TokenValidator] Workload fallback verification failed: {e}")
            raise
    
    def _verify_with_secret(self, token: str) -> Dict[str, Any]:
        """Verify JWT with secret key."""
        try:
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=['HS256'],
                audience='home-ai-lab-agents'
            )
            logger.debug("[TokenValidator] JWT verified with secret")
            return claims
        except jwt.InvalidTokenError as e:
            logger.error(f"[TokenValidator] JWT verification failed: {e}")
            raise
    
    def _verify_with_spire(self, token: str) -> Dict[str, Any]:
        """Verify JWT with SPIRE public key."""
        try:
            # In production, SPIRE public key would be fetched from SPIRE Server
            # For now, use JWT library with SPIRE verification
            claims = jwt.decode(
                token,
                self.spire_client._client._identity.public_key if self.spire_client._client else self.jwt_secret,
                algorithms=['RS256', 'HS256'],
                audience='home-ai-lab-agents'
            )
            logger.debug("[TokenValidator] JWT verified with SPIRE")
            return claims
        except jwt.InvalidTokenError as e:
            logger.error(f"[TokenValidator] SPIRE verification failed: {e}")
            raise


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

@lru_cache(maxsize=1)
def get_token_issuer() -> TokenIssuer:
    """Get singleton token issuer instance."""
    return TokenIssuer(spire_enabled=True)


@lru_cache(maxsize=1)
def get_token_validator() -> TokenValidator:
    """Get singleton token validator instance."""
    return TokenValidator(spire_enabled=True)
