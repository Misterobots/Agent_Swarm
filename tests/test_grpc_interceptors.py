"""
Tests for agents/grpc/interceptors.py — Auth + logging interceptors.

Tests TokenValidator and RequestLogger without gRPC dependency.
Authentik HTTP calls are mocked.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

# Import our module explicitly so we can patch correctly
# (the installed grpc package also has an 'interceptors' module, causing collision)
from grpc import interceptors as _our_interceptors


# Patch target for requests — use the module-level _requests attribute
_REQUESTS_PATCH = "grpc.interceptors._requests"


# ---------------------------------------------------------------------------
# AuthResult tests
# ---------------------------------------------------------------------------

class TestAuthResult:
    def test_success(self):
        from grpc.interceptors import AuthResult
        r = AuthResult(authenticated=True, user_id="u1", username="alice")
        assert r.authenticated is True
        assert r.user_id == "u1"

    def test_failure(self):
        from grpc.interceptors import AuthResult
        r = AuthResult(authenticated=False, error="bad token")
        assert r.authenticated is False
        assert r.error == "bad token"

    def test_default_groups(self):
        from grpc.interceptors import AuthResult
        r = AuthResult(authenticated=True)
        assert r.groups == []

    def test_to_dict(self):
        from grpc.interceptors import AuthResult
        r = AuthResult(authenticated=True, user_id="u1", username="alice", email="a@b.com", groups=["admin"])
        d = r.to_dict()
        assert d["authenticated"] is True
        assert d["username"] == "alice"
        assert d["email"] == "a@b.com"
        assert d["groups"] == ["admin"]

    def test_to_dict_failure(self):
        from grpc.interceptors import AuthResult
        r = AuthResult(authenticated=False, error="expired")
        d = r.to_dict()
        assert d["authenticated"] is False
        assert d["error"] == "expired"


# ---------------------------------------------------------------------------
# TokenValidator tests
# ---------------------------------------------------------------------------

class TestTokenValidatorDisabled:
    def test_disabled_returns_success(self):
        from grpc.interceptors import TokenValidator
        v = TokenValidator(enabled=False)
        result = v.validate("any-token")
        assert result.authenticated is True
        assert result.user_id == "auth-disabled"

    def test_disabled_property(self):
        from grpc.interceptors import TokenValidator
        v = TokenValidator(enabled=False)
        assert v.enabled is False


class TestTokenValidatorEnabled:
    def test_empty_token(self):
        from grpc.interceptors import TokenValidator
        v = TokenValidator(enabled=True)
        result = v.validate("")
        assert result.authenticated is False
        assert "No token" in result.error

    @patch.object(_our_interceptors, "_requests")
    def test_valid_token(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "user-123",
                "preferred_username": "alice",
                "email": "alice@example.com",
                "groups": ["users", "admin"],
            }
        )
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo")
        result = v.validate("valid-token-123")
        assert result.authenticated is True
        assert result.user_id == "user-123"
        assert result.username == "alice"
        assert result.email == "alice@example.com"
        assert "admin" in result.groups

    @patch.object(_our_interceptors, "_requests")
    def test_invalid_token(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.return_value = MagicMock(status_code=401)
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo")
        result = v.validate("bad-token")
        assert result.authenticated is False
        assert "401" in result.error

    @patch.object(_our_interceptors, "_requests")
    def test_authentik_error(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.side_effect = Exception("Connection refused")
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo")
        result = v.validate("token")
        assert result.authenticated is False
        assert "Connection refused" in result.error

    @patch.object(_our_interceptors, "_requests")
    def test_cache_hit(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"sub": "u1", "preferred_username": "alice", "email": "", "groups": []}
        )
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo", cache_ttl=300)
        # First call hits Authentik
        r1 = v.validate("token-abc")
        assert r1.authenticated is True
        call_count_1 = mock_requests.get.call_count
        # Second call should use cache
        r2 = v.validate("token-abc")
        assert r2.authenticated is True
        assert mock_requests.get.call_count == call_count_1  # No new HTTP call

    @patch.object(_our_interceptors, "_requests")
    def test_cache_expiry(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"sub": "u1", "preferred_username": "alice", "email": "", "groups": []}
        )
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo", cache_ttl=0)
        v.validate("token-abc")
        call_count_1 = mock_requests.get.call_count
        # With TTL=0, cache should always expire
        v.validate("token-abc")
        assert mock_requests.get.call_count > call_count_1

    def test_invalidate(self):
        from grpc.interceptors import TokenValidator, AuthResult
        v = TokenValidator(enabled=True)
        # Manually inject cache entry
        import hashlib
        token_hash = hashlib.sha256(b"my-token").hexdigest()[:16]
        v._cache[token_hash] = (AuthResult(authenticated=True), time.time())
        assert token_hash in v._cache
        v.invalidate("my-token")
        assert token_hash not in v._cache

    def test_clear_cache(self):
        from grpc.interceptors import TokenValidator, AuthResult
        v = TokenValidator(enabled=True)
        v._cache["a"] = (AuthResult(authenticated=True), time.time())
        v._cache["b"] = (AuthResult(authenticated=True), time.time())
        v.clear_cache()
        assert len(v._cache) == 0

    @patch.object(_our_interceptors, "_requests")
    def test_userinfo_with_name_fallback(self, mock_requests):
        from grpc.interceptors import TokenValidator
        mock_requests.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"sub": "u1", "name": "Bob"}  # No preferred_username
        )
        v = TokenValidator(enabled=True, userinfo_url="http://auth/userinfo")
        result = v.validate("tok")
        assert result.username == "Bob"


# ---------------------------------------------------------------------------
# RequestLogger tests
# ---------------------------------------------------------------------------

class TestRequestLogger:
    def test_log_success(self):
        from grpc.interceptors import RequestLogger, AuthResult
        rl = RequestLogger()
        auth = AuthResult(authenticated=True, username="alice")
        # Should not raise
        rl.log_request("/InferenceService/Infer", auth_result=auth, duration_ms=42.3)

    def test_log_anonymous(self):
        from grpc.interceptors import RequestLogger
        rl = RequestLogger()
        rl.log_request("/InferenceService/Infer", duration_ms=10.0)

    def test_log_error(self):
        from grpc.interceptors import RequestLogger, AuthResult
        rl = RequestLogger()
        auth = AuthResult(authenticated=False, error="bad token")
        rl.log_request("/InferenceService/Infer", auth_result=auth, error="bad token")


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

class TestSingletons:
    def test_validator_singleton(self):
        from grpc.interceptors import get_token_validator
        import grpc.interceptors as mod
        mod._validator_instance = None
        v1 = get_token_validator()
        v2 = get_token_validator()
        assert v1 is v2
        mod._validator_instance = None

    def test_logger_singleton(self):
        from grpc.interceptors import get_request_logger
        import grpc.interceptors as mod
        mod._logger_instance = None
        l1 = get_request_logger()
        l2 = get_request_logger()
        assert l1 is l2
        mod._logger_instance = None


# ---------------------------------------------------------------------------
# Auth exempt methods
# ---------------------------------------------------------------------------

class TestAuthExemptMethods:
    def test_exempt_methods_defined(self):
        from grpc.interceptors import AUTH_EXEMPT_METHODS
        assert "/openclaude.v1.InferenceService/HealthCheck" in AUTH_EXEMPT_METHODS
        assert "/openclaude.v1.InferenceService/ListModels" in AUTH_EXEMPT_METHODS
