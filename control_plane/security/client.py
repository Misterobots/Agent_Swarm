"""
Control Plane Security Client
==============================

Client library for execution planes to interact with the Control Plane
Security Service for token issuance, validation, and management.

Usage:

    from control_plane_security import SecurityClient
    
    client = SecurityClient("http://192.168.2.102:8001")
    
    # Get token
    token = client.issue_token(
        agent_name="worker-1",
        capabilities=["file_read", "file_write"]
    )
    
    # Validate token
    is_valid = client.validate_token(token)
    
    # Use in requests
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(endpoint, headers=headers)
"""

import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SecurityClientError(Exception):
    """Security client exception."""
    pass


class SecurityClient:
    """
    Client for interacting with Control Plane Security Service.
    
    Handles token issuance, validation, revocation, and caching.
    """
    
    def __init__(
        self,
        security_service_url: str,
        timeout: int = 5,
        verify_ssl: bool = True
    ):
        """
        Initialize security client.
        
        Args:
            security_service_url: Base URL of security service (e.g., http://192.168.2.102:8001)
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates (False in dev, True in prod)
        """
        self.base_url = security_service_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._token_cache: Dict[str, Dict[str, Any]] = {}
    
    def issue_token(
        self,
        agent_name: str,
        capabilities: List[str],
        agent_instance_id: Optional[str] = None,
        spire_svid: Optional[str] = None
    ) -> str:
        """
        Issue JWT token from Control Plane.
        
        Args:
            agent_name: Name of agent requesting token
            capabilities: List of capabilities to grant
            agent_instance_id: Optional custom instance ID
            spire_svid: Optional SPIRE certificate
            
        Returns:
            JWT token string
            
        Raises:
            SecurityClientError: If token issuance fails
        """
        try:
            url = f"{self.base_url}/api/security/v1/token"
            
            payload = {
                "agent_name": agent_name,
                "capabilities": capabilities,
            }
            
            if agent_instance_id:
                payload["agent_instance_id"] = agent_instance_id
            
            if spire_svid:
                payload["spire_svid"] = spire_svid
            
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = response.json()
            token = data["access_token"]
            
            # Cache token info
            self._token_cache[token] = {
                "agent_name": agent_name,
                "expires_in": data.get("expires_in"),
                "issued_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Token issued for {agent_name}")
            return token
        
        except requests.RequestException as e:
            logger.error(f"Failed to issue token: {e}")
            raise SecurityClientError(f"Token issuance failed: {e}")
    
    def validate_token(self, token: str) -> bool:
        """
        Validate token with Control Plane.
        
        Args:
            token: JWT token to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            url = f"{self.base_url}/api/security/v1/validate"
            
            response = requests.post(
                url,
                json={"token": token},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("valid", False)
            else:
                return False
        
        except requests.RequestException as e:
            logger.warning(f"Token validation failed: {e}")
            return False
    
    def validate_token_detailed(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate token and get detailed information.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Token details dict or None if invalid
        """
        try:
            url = f"{self.base_url}/api/security/v1/validate"
            
            response = requests.post(
                url,
                json={"token": token},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
        
        except requests.RequestException as e:
            logger.warning(f"Token validation failed: {e}")
            return None
    
    def revoke_token(self, token: str, reason: str = "revoked") -> bool:
        """
        Revoke token (for deactivated agents).
        
        Args:
            token: JWT token to revoke
            reason: Reason for revocation
            
        Returns:
            True if revoked successfully
        """
        try:
            url = f"{self.base_url}/api/security/v1/revoke"
            
            response = requests.post(
                url,
                json={"token": token, "reason": reason},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            logger.info(f"Token revoked: {reason}")
            
            # Remove from cache
            if token in self._token_cache:
                del self._token_cache[token]
            
            return True
        
        except requests.RequestException as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    def health_check(self) -> bool:
        """
        Check if security service is healthy.
        
        Returns:
            True if service is UP
        """
        try:
            url = f"{self.base_url}/health"
            response = requests.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def get_authorization_header(self, token: str) -> Dict[str, str]:
        """
        Get formatted Authorization header for requests.
        
        Args:
            token: JWT token
            
        Returns:
            Dict with Authorization header
        """
        return {"Authorization": f"Bearer {token}"}
    
    def clear_cache(self):
        """Clear token cache."""
        self._token_cache.clear()
        logger.info("Token cache cleared")


# Convenience functions for common use cases

def get_default_client(security_host: str = "192.168.2.102", port: int = 8001) -> SecurityClient:
    """
    Get default security client.
    
    Args:
        security_host: Security service host (default: 192.168.2.102)
        port: Security service port (default: 8001)
        
    Returns:
        SecurityClient instance
    """
    url = f"http://{security_host}:{port}"
    return SecurityClient(url)


class AuthenticatedRequest:
    """Helper for making authenticated requests with automatic token refresh."""
    
    def __init__(
        self,
        client: SecurityClient,
        agent_name: str,
        capabilities: List[str]
    ):
        """
        Initialize authenticated request helper.
        
        Args:
            client: SecurityClient instance
            agent_name: Name of agent
            capabilities: Required capabilities
        """
        self.client = client
        self.agent_name = agent_name
        self.capabilities = capabilities
        self.token: Optional[str] = None
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get headers with valid token.
        
        Automatically refreshes token if needed.
        
        Returns:
            Dict with Authorization header
        """
        # Get token if not already have one
        if not self.token:
            self.token = self.client.issue_token(
                self.agent_name,
                self.capabilities
            )
        
        # Validate token
        if not self.client.validate_token(self.token):
            # Refresh token if invalid
            self.token = self.client.issue_token(
                self.agent_name,
                self.capabilities
            )
        
        return self.client.get_authorization_header(self.token)
    
    def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """
        Make authenticated HTTP request.
        
        Args:
            method: HTTP method (GET, POST, etc)
            endpoint: Full endpoint URL
            **kwargs: Additional requests arguments
            
        Returns:
            Response object
        """
        headers = kwargs.pop("headers", {})
        headers.update(self.get_headers())
        
        response = requests.request(
            method,
            endpoint,
            headers=headers,
            **kwargs
        )
        
        return response
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """GET request with authentication."""
        return self.request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """POST request with authentication."""
        return self.request("POST", endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """PUT request with authentication."""
        return self.request("PUT", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """DELETE request with authentication."""
        return self.request("DELETE", endpoint, **kwargs)


# Example usage
if __name__ == "__main__":
    import sys
    
    # Get security service URL from environment or command line
    security_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.2.102:8001"
    
    print(f"Connecting to security service at {security_url}")
    
    client = SecurityClient(security_url)
    
    # Test health check
    print("Health check...", end=" ")
    if client.health_check():
        print("✅ OK")
    else:
        print("❌ FAILED")
        sys.exit(1)
    
    # Test token issuance
    print("Issuing token...", end=" ")
    try:
        token = client.issue_token(
            agent_name="test-agent",
            capabilities=["file_read", "file_write"]
        )
        print("✅ OK")
        print(f"  Token: {token[:50]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)
    
    # Test token validation
    print("Validating token...", end=" ")
    if client.validate_token(token):
        print("✅ OK")
    else:
        print("❌ FAILED")
        sys.exit(1)
    
    # Get detailed token info
    print("Getting token details...", end=" ")
    details = client.validate_token_detailed(token)
    if details:
        print("✅ OK")
        print(f"  Agent: {details.get('agent_name')}")
        print(f"  Capabilities: {details.get('capabilities')}")
    else:
        print("❌ FAILED")
    
    print("\n✅ All tests passed!")
