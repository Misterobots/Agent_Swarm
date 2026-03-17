"""
Audit Logger
============

Comprehensive security event logging for authorization system.
Tracks authentication, capability checks, and sensitive operations
with full context for compliance and forensics.

Audit Trail Categories:
- AUTH_SUCCESS: Token validated successfully
- AUTH_FAILED: Failed authentication attempt
- CAPABILITY_GRANTED: Capability check passed
- CAPABILITY_DENIED: Capability check failed
- OPERATION_EXECUTED: Sensitive operation performed
- TOKEN_ISSUED: New token created
- TOKEN_REVOKED: Token revoked
- CONFIG_CHANGED: Security configuration changed
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime
from enum import Enum
import os


class AuditEventType(Enum):
    """Audit event classification."""
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILED = "AUTH_FAILED"
    AUTH_DENIED = "AUTH_DENIED"
    CAPABILITY_GRANTED = "CAPABILITY_GRANTED"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    OPERATION_EXECUTED = "OPERATION_EXECUTED"
    TOKEN_ISSUED = "TOKEN_ISSUED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    ERROR = "ERROR"


class AuditLogger:
    """
    Centralized audit logging for security events.
    
    Features:
    - Structured JSON logging
    - Event classification
    - Context enrichment
    - Compliance-ready formatting
    - File-based audit trail
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file. If None, uses default.
        """
        self.log_file = log_file or self._get_default_log_file()
        self.logger = logging.getLogger("AUDIT")
        
        # Configure audit logger
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure audit logger with file handler."""
        # Create file handler for audit log
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def _get_default_log_file(self) -> str:
        """Get default audit log file path."""
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "logs",
            "audit"
        )
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "audit.log")
    
    def _build_event(
        self,
        event_type: AuditEventType,
        agent_name: str,
        agent_id: str,
        success: bool,
        details: Dict[str, Any],
        **kwargs
    ) -> str:
        """
        Build structured audit event.
        
        Args:
            event_type: Type of audit event
            agent_name: Name of agent performing action
            agent_id: Instance ID of agent
            success: Whether action succeeded
            details: Additional details about event
            **kwargs: Additional context
            
        Returns:
            JSON string of audit event
        """
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type.value,
            'success': success,
            'agent': {
                'name': agent_name,
                'id': agent_id,
            },
            'details': details,
        }
        
        # Add optional context
        if 'request_id' in kwargs:
            event['request_id'] = kwargs['request_id']
        if 'client_ip' in kwargs:
            event['client_ip'] = kwargs['client_ip']
        if 'severity' in kwargs:
            event['severity'] = kwargs['severity']
        
        return json.dumps(event)
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def log_auth_success(
        self,
        agent_name: str,
        agent_id: str,
        token_jti: Optional[str] = None,
        **context
    ):
        """
        Log successful authentication.
        
        Args:
            agent_name: Name of authenticated agent
            agent_id: Instance ID of agent
            token_jti: JWT jti (unique token ID)
            **context: Additional context (request_id, client_ip, etc)
        """
        details = {}
        if token_jti:
            details['token_jti'] = token_jti
        
        event = self._build_event(
            AuditEventType.AUTH_SUCCESS,
            agent_name,
            agent_id,
            True,
            details,
            **context
        )
        
        self.logger.info(event)
    
    def log_auth_failed(
        self,
        reason: str,
        token_jti: Optional[str] = None,
        **context
    ):
        """
        Log failed authentication attempt.
        
        Args:
            reason: Reason for failure (invalid_token, expired, etc)
            token_jti: JWT jti if available
            **context: Additional context (request_id, client_ip, etc)
        """
        details = {
            'reason': reason,
        }
        if token_jti:
            details['token_jti'] = token_jti
        
        event = self._build_event(
            AuditEventType.AUTH_FAILED,
            'unknown',
            'unknown',
            False,
            details,
            severity='medium',
            **context
        )
        
        self.logger.warning(event)
    
    def log_capability_granted(
        self,
        agent_name: str,
        agent_id: str,
        capability: str,
        resource: str,
        **context
    ):
        """
        Log successful capability check.
        
        Args:
            agent_name: Agent name
            agent_id: Agent instance ID
            capability: Capability that was checked
            resource: Resource being accessed
            **context: Additional context (request_id, endpoint, etc)
        """
        details = {
            'capability': capability,
            'resource': resource,
        }
        
        event = self._build_event(
            AuditEventType.CAPABILITY_GRANTED,
            agent_name,
            agent_id,
            True,
            details,
            **context
        )
        
        self.logger.info(event)
    
    def log_capability_denied(
        self,
        agent_name: str,
        agent_id: str,
        capability: str,
        resource: str,
        **context
    ):
        """
        Log denied capability check.
        
        Args:
            agent_name: Agent name
            agent_id: Agent instance ID
            capability: Capability that was required but denied
            resource: Resource being accessed
            **context: Additional context (request_id, endpoint, etc)
        """
        details = {
            'capability': capability,
            'resource': resource,
            'available_capabilities': context.pop('available_capabilities', []),
        }
        
        event = self._build_event(
            AuditEventType.CAPABILITY_DENIED,
            agent_name,
            agent_id,
            False,
            details,
            severity='medium',
            **context
        )
        
        self.logger.warning(event)
    
    def log_operation_executed(
        self,
        agent_name: str,
        agent_id: str,
        operation: str,
        resource: str,
        success: bool = True,
        **context
    ):
        """
        Log sensitive operation execution.
        
        Args:
            agent_name: Agent performing operation
            agent_id: Agent instance ID
            operation: Type of operation (create, delete, modify, etc)
            resource: Resource affected
            success: Whether operation succeeded
            **context: Additional context (old_value, new_value, etc)
        """
        details = {
            'operation': operation,
            'resource': resource,
        }
        details.update(context.get('details', {}))
        
        event = self._build_event(
            AuditEventType.OPERATION_EXECUTED,
            agent_name,
            agent_id,
            success,
            details,
            severity='high' if operation in ['delete', 'revoke'] else 'medium',
            **{k: v for k, v in context.items() if k != 'details'}
        )
        
        self.logger.info(event)
    
    def log_token_issued(
        self,
        agent_name: str,
        agent_id: str,
        token_jti: str,
        capabilities: list,
        expires_at: str,
        **context
    ):
        """
        Log token issuance.
        
        Args:
            agent_name: Agent receiving token
            agent_id: Agent instance ID
            token_jti: Unique token ID
            capabilities: List of capabilities granted
            expires_at: Token expiration time
            **context: Additional context
        """
        details = {
            'token_jti': token_jti,
            'capabilities': capabilities,
            'expires_at': expires_at,
        }
        
        event = self._build_event(
            AuditEventType.TOKEN_ISSUED,
            agent_name,
            agent_id,
            True,
            details,
            **context
        )
        
        self.logger.info(event)
    
    def log_token_revoked(
        self,
        agent_name: str,
        agent_id: str,
        token_jti: str,
        reason: str,
        **context
    ):
        """
        Log token revocation.
        
        Args:
            agent_name: Agent whose token was revoked
            agent_id: Agent instance ID
            token_jti: Unique token ID
            reason: Reason for revocation
            **context: Additional context
        """
        details = {
            'token_jti': token_jti,
            'reason': reason,
        }
        
        event = self._build_event(
            AuditEventType.TOKEN_REVOKED,
            agent_name,
            agent_id,
            True,
            details,
            severity='high',
            **context
        )
        
        self.logger.warning(event)
    
    def log_config_changed(
        self,
        agent_name: str,
        agent_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        **context
    ):
        """
        Log security configuration change.
        
        Args:
            agent_name: Agent making change
            agent_id: Agent instance ID
            config_key: Configuration key that changed
            old_value: Previous value
            new_value: New value
            **context: Additional context
        """
        details = {
            'config_key': config_key,
            'old_value': str(old_value),
            'new_value': str(new_value),
        }
        
        event = self._build_event(
            AuditEventType.CONFIG_CHANGED,
            agent_name,
            agent_id,
            True,
            details,
            severity='high',
            **context
        )
        
        self.logger.warning(event)
    
    def log_error(
        self,
        agent_name: str,
        agent_id: str,
        error_type: str,
        error_message: str,
        **context
    ):
        """
        Log security-related error.
        
        Args:
            agent_name: Agent where error occurred
            agent_id: Agent instance ID
            error_type: Type of error
            error_message: Error message
            **context: Additional context (stack_trace, etc)
        """
        details = {
            'error_type': error_type,
            'error_message': error_message,
        }
        
        event = self._build_event(
            AuditEventType.ERROR,
            agent_name,
            agent_id,
            False,
            details,
            severity='high',
            **context
        )
        
        self.logger.error(event)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_audit_logger_instance: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance (singleton)."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


def reset_audit_logger():
    """Reset audit logger (for testing)."""
    global _audit_logger_instance
    _audit_logger_instance = None
