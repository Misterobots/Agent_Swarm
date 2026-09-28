"""
Capability Gate Decorator
==========================

Enforces capability-based access control at the function level.
Validates JWT tokens and checks if required capability is in activated list.

Usage:
    @app.get("/api/v1/write-file")
    @CapabilityRequired(capability='file_write')
    async def write_file_endpoint(path: str, content: str, request: Request):
        # This endpoint only executes if JWT has 'file_write' capability
        return await write_file(path, content)
"""

import logging
import functools
from typing import Callable, Optional, Any
try:
    from fastapi import Request, HTTPException, status
except ImportError:
    Request = None
    HTTPException = None
    status = None
import jwt

logger = logging.getLogger(__name__)


# ============================================================================
# CAPABILITY DEFINITIONS
# ============================================================================

# Standard capabilities used in agent system
STANDARD_CAPABILITIES = {
    # File operations
    'file_read': 'Read files from filesystem',
    'file_write': 'Write files to filesystem',
    'file_delete': 'Delete files from filesystem',
    
    # Code execution
    'terminal_exec': 'Execute shell commands',
    'terminal_read': 'Read terminal output',
    
    # API operations
    'api_call': 'Make external API calls',
    'api_webhook': 'Receive webhook callbacks',
    
    # Git operations
    'git_read': 'Read git information',
    'git_write': 'Write to git (commit, push)',
    
    # Model operations
    'model_generate': 'Generate predictions with model',
    'model_finetune': 'Fine-tune model parameters',
    
    # Image generation
    'image_generate': 'Generate images (ComfyUI)',
    'image_upload': 'Upload generated images',
    
    # Database operations
    'db_read': 'Read from database',
    'db_write': 'Write to database',
    'db_admin': 'Database administrative operations',
    
    # System operations
    'resource_access': 'Access GPU/memory resources',
    'service_restart': 'Restart services',
    'audit_read': 'Read audit logs',
}


# ============================================================================
# CAPABILITY REQUIREMENT DECORATOR
# ============================================================================

def CapabilityRequired(
    capability: str,
    fallback_capability: Optional[str] = None,
    audit_log: bool = True
):
    """
    Decorator to enforce capability-based access control.
    
    Args:
        capability: Required capability name (e.g., 'file_write')
        fallback_capability: Alternative capability that satisfies requirement
                           (e.g., 'admin' might satisfy 'file_write')
        audit_log: Log denied access attempts. Default True.
        
    Returns:
        Decorated function that validates JWT before execution
        
    Example:
        @app.post("/write-file")
        @CapabilityRequired(capability='file_write', fallback_capability='admin')
        async def write_file(path: str, content: str, request: Request):
            # Only executes if JWT has 'file_write' or 'admin'
            return await write_file_impl(path, content)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract Request from kwargs or args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None and 'request' in kwargs:
                request = kwargs['request']
            
            if request is None:
                logger.error(f"[CapabilityGate] No request found for {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal error: Request object not found"
                )
            
            # Validate capability
            is_allowed, agent_card = await _validate_capability(
                request,
                capability,
                fallback_capability,
                audit_log
            )
            
            if not is_allowed:
                logger.warning(
                    f"[CapabilityGate] Access DENIED to {func.__name__} "
                    f"(required: {capability})"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient capabilities: {capability} required"
                )
            
            # Log successful access
            logger.info(
                f"[CapabilityGate] Access GRANTED to {func.__name__} "
                f"for agent {agent_card.agent_name} "
                f"(capability: {capability})"
            )
            
            # Continue to protected function
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Extract Request from kwargs or args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None and 'request' in kwargs:
                request = kwargs['request']
            
            if request is None:
                logger.error(f"[CapabilityGate] No request found for {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal error: Request object not found"
                )
            
            # Note: Sync version doesn't support async validation
            # This is a simplified synchronous version
            try:
                token = _extract_token(request)
                if not token:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing bearer token"
                    )
                
                # Validate capability (simple sync version)
                agent_card = _validate_token_sync(token)
                
                if not _check_capability(agent_card, capability, fallback_capability):
                    if audit_log:
                        _audit_denied_access(request, func.__name__, capability, agent_card)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient capabilities: {capability} required"
                    )
                
                logger.info(
                    f"[CapabilityGate] Access GRANTED to {func.__name__} "
                    f"for agent {agent_card.agent_name}"
                )
                return func(*args, **kwargs)
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[CapabilityGate] Error in capability check: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error validating capabilities"
                )
        
        # Return async or sync wrapper based on function
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_token(request: Request) -> Optional[str]:
    """Extract JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:]  # Remove "Bearer " prefix


async def _validate_capability(
    request: Request,
    required_capability: str,
    fallback_capability: Optional[str],
    audit_log: bool
) -> tuple[bool, Any]:
    """
    Validate JWT token and check capability.
    
    Returns:
        (is_allowed, agent_card) tuple
    """
    try:
        token = _extract_token(request)
        if not token:
            logger.warning("[CapabilityGate] No bearer token in request")
            return False, None
        
        # Import token validator
        from security.token_issuer import get_token_validator
        validator = get_token_validator()
        
        try:
            agent_card = validator.validate_token(token)
        except jwt.ExpiredSignatureError:
            logger.warning("[CapabilityGate] Token has expired")
            return False, None
        except jwt.InvalidTokenError as e:
            logger.warning(f"[CapabilityGate] Invalid token: {e}")
            return False, None
        except Exception as e:
            logger.error(f"[CapabilityGate] Token validation error: {e}")
            return False, None
        
        # Check capability
        is_allowed = _check_capability(
            agent_card,
            required_capability,
            fallback_capability
        )
        
        if not is_allowed and audit_log:
            _audit_denied_access(request, "unknown_endpoint", required_capability, agent_card)
        
        return is_allowed, agent_card
    
    except Exception as e:
        logger.error(f"[CapabilityGate] Validation error: {e}")
        return False, None


def _validate_token_sync(token: str) -> Any:
    """Synchronous token validation (simplified)."""
    from security.token_issuer import get_token_validator
    validator = get_token_validator()
    return validator.validate_token(token)


def _check_capability(agent_card: Any, required: str, fallback: Optional[str]) -> bool:
    """
    Check if agent has required capability.
    
    Validates against both the card's activated_capabilities AND the
    active scope from execution context (if set).  The active scope
    narrows what the card is allowed to do on this specific intent.
    
    Args:
        agent_card: EphemeralAgentCard instance
        required: Required capability name
        fallback: Alternative capability that satisfies requirement
        
    Returns:
        True if agent has capability, False otherwise
    """
    if not hasattr(agent_card, 'activated_capabilities'):
        logger.error(f"[CapabilityGate] Agent card missing activated_capabilities")
        return False
    
    capabilities = agent_card.activated_capabilities or []
    
    # Check card-level capability
    card_ok = required in capabilities or (fallback is not None and fallback in capabilities)
    if not card_ok:
        return False

    # Check against active scope (if set).
    try:
        from security.execution_context import get_active_scope
        scope = get_active_scope()
    except ImportError:
        scope = None

    if scope is not None:
        scope_ok = required in scope or (fallback is not None and fallback in scope)
        if not scope_ok:
            logger.debug(
                f"[CapabilityGate] Capability '{required}' present in card but "
                f"not in active scope {scope}"
            )
            return False

    return True


def _audit_denied_access(
    request: Request,
    endpoint: str,
    capability: str,
    agent_card: Any
):
    """
    Log denied access attempt for audit trail.
    
    In production, would write to audit database.
    """
    agent_name = getattr(agent_card, 'agent_name', 'unknown')
    agent_id = getattr(agent_card, 'agent_instance_id', 'unknown')
    
    audit_entry = {
        'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
        'event_type': 'DENIED_ACCESS',
        'endpoint': endpoint,
        'required_capability': capability,
        'agent_name': agent_name,
        'agent_id': agent_id,
        'client_ip': request.client.host if request.client else 'unknown',
        'method': request.method,
        'path': request.url.path
    }
    
    logger.warning(f"[CapabilityGate] AUDIT: {audit_entry}")


# ============================================================================
# CAPABILITY VALIDATOR CLASS (For service-to-service)
# ============================================================================

class CapabilityValidator:
    """
    Validates capabilities for service-to-service calls (not just HTTP).
    Useful for internal orchestration without FastAPI.
    """
    
    def __init__(self):
        from security.token_issuer import get_token_validator
        self.validator = get_token_validator()
    
    def check_capability(
        self,
        token: str,
        required_capability: str,
        fallback_capability: Optional[str] = None
    ) -> bool:
        """
        Check if JWT token grants required capability.
        
        Args:
            token: JWT token string
            required_capability: Capability name to check
            fallback_capability: Alternative capability
            
        Returns:
            True if token grants capability, False otherwise
        """
        try:
            agent_card = self.validator.validate_token(token)
            return _check_capability(agent_card, required_capability, fallback_capability)
        except Exception as e:
            logger.error(f"[CapabilityValidator] Error checking capability: {e}")
            return False
    
    def get_agent_card(self, token: str) -> Optional[Any]:
        """Get agent card from token (for introspection)."""
        try:
            return self.validator.validate_token(token)
        except Exception as e:
            logger.error(f"[CapabilityValidator] Error getting agent card: {e}")
            return None
