"""
SPIFFE/SPIRE Authentication Module

Provides cryptographic workload identity for agent-to-agent communication.
Uses py-spiffe to interact with the SPIRE Agent workload API.

Features:
- X.509 SVID fetching for mTLS
- JWT-SVID generation for API authentication  
- Peer identity verification
- Automatic credential rotation
"""

from __future__ import annotations
import os
import logging
from typing import Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Check if py-spiffe is available
try:
    from spiffe import WorkloadApiClient, X509Svid, JwtSvid, X509Bundle
    SPIFFE_AVAILABLE = True
except ImportError as e:
    SPIFFE_AVAILABLE = False
    logger.warning(f"py-spiffe not installed or import error: {e}")
    # print to stderr to ensure visibility in docker logs if logger is not configured
    import sys
    print(f"[ERROR] spiffe_auth.py import failed: {e}", file=sys.stderr)
    # Define dummy types for runtime type checking if library is missing
    WorkloadApiClient = None
    X509Svid = None
    JwtSvid = None
    X509Bundle = None



class SpiffeAuth:
    """
    SPIFFE-based authentication for zero-trust agent-to-agent communication.
    
    Usage:
        auth = SpiffeAuth()
        
        # Get JWT for API calls
        token = auth.get_jwt_token("spiffe://home-ai-lab/agent/router")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Verify incoming JWT
        claims = auth.verify_jwt_token(incoming_token, expected_audience)
    """
    
    def __init__(self, socket_path: Optional[str] = None):
        """
        Initialize SPIFFE authentication client.
        
        Args:
            socket_path: Path to SPIRE Agent socket. 
                        Defaults to SPIFFE_ENDPOINT_SOCKET env var.
        """
        if not SPIFFE_AVAILABLE:
            logger.warning("SpiffeAuth initialized but py-spiffe not available")
            self._client = None
            return
            
        self._socket_path = socket_path or os.environ.get(
            "SPIFFE_ENDPOINT_SOCKET", 
            "unix:///var/run/spire/agent.sock"
        )
        
        try:
            self._client = WorkloadApiClient(self._socket_path)
            logger.info(f"SPIFFE client connected to {self._socket_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SPIRE Agent: {e}")
            self._client = None
    
    @property
    def is_available(self) -> bool:
        """Check if SPIFFE authentication is available."""
        return self._client is not None
    
    def get_identity(self) -> Optional["X509Svid"]:
        """
        Fetch current workload's X.509 SVID.
        
        Returns:
            X509Svid containing certificate chain and private key,
            or None if unavailable.
        """
        if not self._client:
            return None
            
        try:
            svid = self._client.fetch_x509_svid()
            logger.debug(f"Fetched X.509 SVID: {svid.spiffe_id}")
            return svid
        except Exception as e:
            logger.error(f"Failed to fetch X.509 SVID: {e}")
            return None
    
    def get_spiffe_id(self) -> Optional[str]:
        """Get this workload's SPIFFE ID as a string."""
        svid = self.get_identity()
        return str(svid.spiffe_id) if svid else None
    
    def get_jwt_token(self, audience: str) -> Optional[str]:
        """
        Get JWT-SVID for authenticating to a specific service.
        
        Args:
            audience: SPIFFE ID of the target service (e.g., "spiffe://home-ai-lab/agent/router")
        
        Returns:
            JWT token string, or None if unavailable.
        """
        if not self._client:
            return None
            
        try:
            jwt_svid = self._client.fetch_jwt_svid(audience={audience})
            logger.debug(f"Fetched JWT-SVID for audience: {audience}")
            return jwt_svid.token
        except Exception as e:
            logger.error(f"Failed to fetch JWT-SVID: {e}")
            return None
    
    def verify_jwt_token(self, token: str, expected_audience: str) -> Optional[dict]:
        """
        Verify an incoming JWT-SVID and extract claims.
        
        Args:
            token: JWT token to verify
            expected_audience: Expected audience claim
        
        Returns:
            Dict of claims if valid, None if verification fails.
        """
        if not self._client:
            return None
            
        try:
            # Fetch trust bundle for verification
            bundles = self._client.fetch_jwt_bundles()
            
            # Validate and parse the JWT
            jwt_svid = JwtSvid.parse_insecure(token, {expected_audience})
            
            claims = {
                "spiffe_id": str(jwt_svid.spiffe_id),
                "audience": jwt_svid.audience,
                "expiry": jwt_svid.expiry,
            }
            
            logger.debug(f"Verified JWT from: {claims['spiffe_id']}")
            return claims
            
        except Exception as e:
            logger.error(f"JWT verification failed: {e}")
            return None
    
    def get_mtls_config(self) -> Optional[Tuple[bytes, bytes, bytes]]:
        """
        Get mTLS configuration for secure connections.
        
        Returns:
            Tuple of (cert_chain_pem, private_key_pem, ca_bundle_pem),
            or None if unavailable.
        """
        if not self._client:
            return None
            
        try:
            svid = self._client.fetch_x509_svid()
            bundles = self._client.fetch_x509_bundles()
            
            # Get trust domain bundle
            trust_domain = svid.spiffe_id.trust_domain
            bundle = bundles.get_bundle_for_trust_domain(trust_domain)
            
            return (
                svid.cert_chain_pem,
                svid.private_key_pem,
                bundle.x509_authorities_pem
            )
        except Exception as e:
            logger.error(f"Failed to get mTLS config: {e}")
            return None


# Global singleton instance
_auth_instance: Optional[SpiffeAuth] = None


def get_spiffe_auth() -> SpiffeAuth:
    """Get global SpiffeAuth instance (lazy initialization)."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = SpiffeAuth()
    return _auth_instance


# Convenience functions
def get_auth_headers(target_spiffe_id: str) -> dict:
    """
    Get authentication headers for calling another agent.
    
    Args:
        target_spiffe_id: SPIFFE ID of the target service
    
    Returns:
        Dict with Authorization header, or empty dict if unavailable.
    """
    auth = get_spiffe_auth()
    token = auth.get_jwt_token(target_spiffe_id)
    
    if token:
        return {"Authorization": f"Bearer {token}"}
    
    logger.warning(f"Could not get auth token for {target_spiffe_id}")
    return {}


def verify_request_identity(token: str, expected_id: Optional[str] = None) -> Optional[str]:
    """
    Verify an incoming request's identity from its JWT token.
    
    Args:
        token: JWT token from Authorization header
        expected_id: Optional specific SPIFFE ID to require
    
    Returns:
        Verified SPIFFE ID, or None if verification fails.
    """
    auth = get_spiffe_auth()
    
    # Use our own SPIFFE ID as the expected audience
    our_id = auth.get_spiffe_id()
    if not our_id:
        return None
    
    claims = auth.verify_jwt_token(token, our_id)
    if not claims:
        return None
    
    caller_id = claims.get("spiffe_id")
    
    if expected_id and caller_id != expected_id:
        logger.warning(f"Caller ID mismatch: expected {expected_id}, got {caller_id}")
        return None
    
    return caller_id
