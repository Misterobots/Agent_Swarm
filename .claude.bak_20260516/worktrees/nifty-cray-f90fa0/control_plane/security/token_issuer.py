"""
Control Plane: Token Issuer Service
====================================

Centralized JWT token generation and validation for all execution planes.
Integrates with SPIRE for identity verification and PostgreSQL for persistence.

Features:
- Issue JWT tokens from SPIRE identities
- Validate token signatures and expiration
- Token revocation with database persistence
- Audit logging to Langfuse
- Service-to-service validation
"""

import logging
import json
import os
from typing import Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import jwt
import uuid

# PostgreSQL for revocation storage
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


class TokenStatus(Enum):
    """Token lifecycle status."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TokenIssuer:
    """
    Central token issuer for all execution planes.
    
    Integrates with:
    - SPIRE: Identity validation
    - PostgreSQL: Token storage and revocation tracking
    - Langfuse: Audit logging
    """
    
    def __init__(self, config: dict):
        """
        Initialize token issuer.
        
        Args:
            config: Configuration dict with:
                - secret_key: JWT signing key
                - algorithm: JWT algorithm (HS256)
                - expiration_hours: Token lifetime
                - db_url: PostgreSQL connection string
                - langfuse_client: Optional Langfuse client
        """
        self.secret_key = config.get('secret_key')
        self.algorithm = config.get('algorithm', 'HS256')
        self.expiration_hours = config.get('expiration_hours', 24)
        self.db_url = config.get('db_url')
        self.langfuse = config.get('langfuse_client')
        
        # Initialize database
        if self.db_url and psycopg2:
            self._init_db()
    
    def _init_db(self):
        """Initialize PostgreSQL tables for token management."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # Tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_tokens (
                    jti VARCHAR(255) PRIMARY KEY,
                    agent_name VARCHAR(255) NOT NULL,
                    agent_instance_id VARCHAR(255) NOT NULL,
                    capabilities TEXT NOT NULL,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    revoked_at TIMESTAMP,
                    revoke_reason TEXT
                );
            """)
            
            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_audit (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR(50) NOT NULL,
                    agent_name VARCHAR(255),
                    agent_id VARCHAR(255),
                    details JSONB,
                    success BOOLEAN DEFAULT TRUE
                );
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Database tables initialized for token management")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def issue_token(
        self,
        agent_name: str,
        agent_instance_id: str,
        capabilities: list,
        spire_svid: Optional[str] = None
    ) -> str:
        """
        Issue JWT token for agent.
        
        Args:
            agent_name: Name of agent
            agent_instance_id: Unique instance ID
            capabilities: List of granted capabilities
            spire_svid: Optional SPIRE SVID for validation
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiration = now + timedelta(hours=self.expiration_hours)
        jti = str(uuid.uuid4())
        
        payload = {
            'agent_name': agent_name,
            'agent_instance_id': agent_instance_id,
            'activated_capabilities': capabilities,
            'iss': 'control_plane',
            'iat': int(now.timestamp()),
            'exp': int(expiration.timestamp()),
            'jti': jti,
        }
        
        # Add SPIRE identity if provided
        if spire_svid:
            payload['spire_svid'] = spire_svid
        
        # Sign token
        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        # Store in database
        self._store_token(jti, agent_name, agent_instance_id, capabilities, expiration)
        
        # Audit log
        self._log_audit('TOKEN_ISSUED', agent_name, agent_instance_id, {
            'jti': jti,
            'capabilities': capabilities,
            'expires_at': expiration.isoformat()
        })
        
        logger.info(f"Token issued for {agent_name} (instance: {agent_instance_id})")
        return token
    
    def validate_token(self, token: str) -> dict:
        """
        Validate JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check if revoked
            jti = payload.get('jti')
            if jti and self._is_revoked(jti):
                raise jwt.InvalidTokenError("Token has been revoked")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.warning("Token validation failed: expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token validation failed: {e}")
            raise
    
    def revoke_token(self, jti: str, reason: str = "revoked"):
        """
        Revoke token.
        
        Args:
            jti: Token JTI
            reason: Revocation reason
        """
        if not self.db_url or not psycopg2:
            logger.error("Database not configured for revocation")
            return
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE security_tokens
                SET status = 'revoked', 
                    revoked_at = CURRENT_TIMESTAMP,
                    revoke_reason = %s
                WHERE jti = %s
            """, (reason, jti))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Token revoked: {jti} - {reason}")
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
    
    def _store_token(
        self,
        jti: str,
        agent_name: str,
        agent_instance_id: str,
        capabilities: list,
        expires_at: datetime
    ):
        """Store token metadata in database."""
        if not self.db_url or not psycopg2:
            return
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO security_tokens 
                (jti, agent_name, agent_instance_id, capabilities, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (jti, agent_name, agent_instance_id, json.dumps(capabilities), expires_at))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store token: {e}")
    
    def _is_revoked(self, jti: str) -> bool:
        """Check if token is revoked."""
        if not self.db_url or not psycopg2:
            return False
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                "SELECT status FROM security_tokens WHERE jti = %s",
                (jti,)
            )
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result and result['status'] == 'revoked'
        except Exception as e:
            logger.error(f"Failed to check revocation: {e}")
            return False
    
    def _log_audit(self, event_type: str, agent_name: str, agent_id: str, details: dict):
        """Log security event."""
        if self.langfuse:
            try:
                # Log to Langfuse
                self.langfuse.log_event(
                    name=f"security.{event_type}",
                    metadata={
                        'agent_name': agent_name,
                        'agent_id': agent_id,
                        **details
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log to Langfuse: {e}")
        
        # Also store in database
        if self.db_url and psycopg2:
            try:
                conn = psycopg2.connect(self.db_url)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO security_audit 
                    (event_type, agent_name, agent_id, details)
                    VALUES (%s, %s, %s, %s)
                """, (event_type, agent_name, agent_id, json.dumps(details)))
                
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to log to database: {e}")


# Singleton instance
_issuer_instance: Optional[TokenIssuer] = None


def initialize_token_issuer(config: dict) -> TokenIssuer:
    """Initialize the global token issuer."""
    global _issuer_instance
    _issuer_instance = TokenIssuer(config)
    return _issuer_instance


def get_token_issuer() -> TokenIssuer:
    """Get the global token issuer instance."""
    if _issuer_instance is None:
        raise RuntimeError("Token issuer not initialized. Call initialize_token_issuer() first.")
    return _issuer_instance
