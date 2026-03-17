"""
JWT-ACE Lifecycle Tests
=========================

Tests for the ephemeral agent token issuance, validation,
capability checking, and router integration.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestTokenIssueAndValidate:
    """Test JWT token issue/validate cycle."""

    def test_issue_and_validate_roundtrip(self):
        """Issue a token, then validate it — claims should match."""
        from security.token_issuer import TokenIssuer, TokenValidator, EphemeralAgentCard

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")
        validator = TokenValidator(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="code_developer",
            template_version="1.0",
            agent_name="TestAgent_001",
            activated_capabilities=["file_read", "file_write", "terminal_exec"],
            security_level="L3_ADMIN",
            session_id="test-session-123",
            expiry_hours=1,
        )

        token = issuer.issue_token(card)
        assert isinstance(token, str)
        assert len(token) > 0

        validated_card = validator.validate_token(token)
        assert validated_card.template_id == "code_developer"
        assert validated_card.template_version == "1.0"
        assert validated_card.agent_name == "TestAgent_001"
        assert "file_read" in validated_card.activated_capabilities
        assert "file_write" in validated_card.activated_capabilities
        assert validated_card.security_level == "L3_ADMIN"

    def test_token_with_no_capabilities(self):
        """Token with empty capabilities should validate successfully."""
        from security.token_issuer import TokenIssuer, TokenValidator, EphemeralAgentCard

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")
        validator = TokenValidator(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="default",
            template_version="1.0",
            agent_name="MinimalAgent",
            activated_capabilities=[],
            expiry_hours=1,
        )

        token = issuer.issue_token(card)
        validated = validator.validate_token(token)
        assert validated.activated_capabilities == []

    def test_token_expiry(self):
        """Token with 0-hour TTL should be expired immediately."""
        import jwt as pyjwt
        from security.token_issuer import TokenIssuer, TokenValidator, EphemeralAgentCard

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")
        validator = TokenValidator(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="expired_test",
            template_version="1.0",
            agent_name="ExpiredAgent",
            activated_capabilities=["file_read"],
            expiry_hours=0,  # Expires immediately
        )

        token = issuer.issue_token(card)

        # Should raise ExpiredSignatureError
        with pytest.raises(pyjwt.ExpiredSignatureError):
            validator.validate_token(token)

    def test_invalid_token_rejected(self):
        """Garbage token should be rejected."""
        import jwt as pyjwt
        from security.token_issuer import TokenValidator

        validator = TokenValidator(spire_enabled=False, jwt_secret="test-secret")

        with pytest.raises((pyjwt.InvalidTokenError, ValueError)):
            validator.validate_token("this-is-not-a-valid-jwt-token")

    def test_wrong_secret_rejected(self):
        """Token signed with different secret should be rejected."""
        import jwt as pyjwt
        from security.token_issuer import TokenIssuer, TokenValidator, EphemeralAgentCard

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="secret-A")
        validator = TokenValidator(spire_enabled=False, jwt_secret="secret-B")

        card = EphemeralAgentCard(
            template_id="test",
            template_version="1.0",
            agent_name="TestAgent",
            activated_capabilities=["file_read"],
            expiry_hours=1,
        )

        token = issuer.issue_token(card)

        with pytest.raises((pyjwt.InvalidTokenError, pyjwt.InvalidSignatureError)):
            validator.validate_token(token)


class TestCapabilityCheck:
    """Test capability validation logic."""

    def test_capability_allowed(self):
        """Token with required capability should pass check."""
        from security.token_issuer import TokenIssuer, EphemeralAgentCard
        from security.capability_gate import CapabilityValidator

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="test",
            template_version="1.0",
            agent_name="TestAgent",
            activated_capabilities=["file_read", "file_write"],
            expiry_hours=1,
        )

        token = issuer.issue_token(card)

        # Patch the validator to use our test secret
        with patch.dict(os.environ, {"EPHEMERAL_AGENT_JWT_SECRET": "test-secret"}):
            validator = CapabilityValidator()
            assert validator.check_capability(token, "file_read") is True
            assert validator.check_capability(token, "file_write") is True

    def test_capability_denied(self):
        """Token without required capability should fail check."""
        from security.token_issuer import TokenIssuer, EphemeralAgentCard
        from security.capability_gate import CapabilityValidator

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="test",
            template_version="1.0",
            agent_name="ReadOnlyAgent",
            activated_capabilities=["file_read"],  # No file_write
            expiry_hours=1,
        )

        token = issuer.issue_token(card)

        with patch.dict(os.environ, {"EPHEMERAL_AGENT_JWT_SECRET": "test-secret"}):
            validator = CapabilityValidator()
            assert validator.check_capability(token, "file_write") is False
            assert validator.check_capability(token, "terminal_exec") is False

    def test_capability_fallback(self):
        """Fallback capability should satisfy requirement."""
        from security.token_issuer import TokenIssuer, EphemeralAgentCard
        from security.capability_gate import CapabilityValidator

        issuer = TokenIssuer(spire_enabled=False, jwt_secret="test-secret")

        card = EphemeralAgentCard(
            template_id="test",
            template_version="1.0",
            agent_name="AdminAgent",
            activated_capabilities=["db_admin"],  # Has admin, not db_write
            expiry_hours=1,
        )

        token = issuer.issue_token(card)

        with patch.dict(os.environ, {"EPHEMERAL_AGENT_JWT_SECRET": "test-secret"}):
            validator = CapabilityValidator()
            # db_write required, but db_admin is fallback
            assert validator.check_capability(token, "db_write", fallback_capability="db_admin") is True


class TestIntentCapabilities:
    """Test the intent-to-capability mapping."""

    def test_known_intents(self):
        """All standard intents should return valid mappings."""
        from intent_capabilities import get_capabilities_for_intent

        for intent in ["CODE", "IMAGE", "3D", "RESEARCH", "DOCUMENTATION", "TRAIN", "IOT_CONTROL", "IOT_DEV"]:
            caps = get_capabilities_for_intent(intent)
            assert "agent_name" in caps
            assert "template_id" in caps
            assert "capabilities" in caps
            assert isinstance(caps["capabilities"], list)
            assert len(caps["capabilities"]) > 0
            assert "security_level" in caps
            assert "expiry_hours" in caps

    def test_unknown_intent_returns_default(self):
        """Unknown intent should return safe defaults."""
        from intent_capabilities import get_capabilities_for_intent

        caps = get_capabilities_for_intent("UNKNOWN_INTENT")
        assert caps["agent_name"] == "Router"
        assert caps["template_id"] == "default"
        assert caps["security_level"] == "L1_PUBLIC"

    def test_code_intent_has_write_capabilities(self):
        """CODE intent should have file_write and terminal_exec."""
        from intent_capabilities import get_capabilities_for_intent

        caps = get_capabilities_for_intent("CODE")
        assert "file_write" in caps["capabilities"]
        assert "terminal_exec" in caps["capabilities"]
        assert caps["security_level"] == "L3_ADMIN"

    def test_research_intent_is_read_only(self):
        """RESEARCH intent should not have write capabilities."""
        from intent_capabilities import get_capabilities_for_intent

        caps = get_capabilities_for_intent("RESEARCH")
        assert "file_write" not in caps["capabilities"]
        assert "terminal_exec" not in caps["capabilities"]
        assert caps["security_level"] == "L1_PUBLIC"


class TestExecutionContext:
    """Test thread-local execution context."""

    def test_set_and_get_token(self):
        """Set token, get it back."""
        from security.execution_context import set_current_token, get_current_token, clear_current_token

        set_current_token("test-jwt-token")
        assert get_current_token() == "test-jwt-token"
        clear_current_token()
        assert get_current_token() is None

    def test_no_token_returns_none(self):
        """No token set should return None."""
        from security.execution_context import get_current_token, clear_current_token

        clear_current_token()
        assert get_current_token() is None

    def test_thread_isolation(self):
        """Tokens should be isolated between threads."""
        import threading
        from security.execution_context import set_current_token, get_current_token, clear_current_token

        results = {}

        def thread_fn(name, token):
            set_current_token(token)
            time.sleep(0.05)  # Give other thread time to set its token
            results[name] = get_current_token()
            clear_current_token()

        t1 = threading.Thread(target=thread_fn, args=("t1", "token-A"))
        t2 = threading.Thread(target=thread_fn, args=("t2", "token-B"))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see only its own token
        assert results["t1"] == "token-A"
        assert results["t2"] == "token-B"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
