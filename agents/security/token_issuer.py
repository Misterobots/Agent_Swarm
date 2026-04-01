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
    """
    template_id: str                    # Reference to ExpertiseTemplate
    template_version: str              # "1.3", "2.0", etc.
    agent_name: str                    # "SecurityValidator_001"
    agent_instance_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    activated_capabilities: List[str] = dataclasses.field(default_factory=list)  # ["file_read", "api_call"]
    security_level: str = "L2_USER"    # L1_PUBLIC, L2_USER, L3_ADMIN, L4_SYSTEM
    user_id: Optional[str] = None      # Canonical authenticated user owner (for user tokens)
    session_id: Optional[str] = None   # Link to user session
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
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expiry_hours: int = 1


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
    """
    
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
    
    def validate_token(self, token: str) -> EphemeralAgentCard:
        """
        Backward-compatible default validator.
        Treats the token as a user-scoped JWT-ACE token.
        """
        return self.validate_user_token(token)

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
