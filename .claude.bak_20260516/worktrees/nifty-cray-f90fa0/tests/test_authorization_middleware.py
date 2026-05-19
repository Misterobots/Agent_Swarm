from dataclasses import dataclass, field

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agents.security.authorization_middleware import AuthorizationMiddleware
from agents.security.token_issuer import EphemeralAgentCard, TokenIssuer


TEST_JWT_SECRET = "test-secret-32-bytes-minimum-length!!"


@dataclass
class DummyCard:
    agent_name: str = "test-agent"
    agent_instance_id: str = "agent-1"
    activated_capabilities: list[str] = field(default_factory=list)
    security_level: str = "L2_USER"


def build_app(enforcement_mode: str) -> FastAPI:
    app = FastAPI()

    @app.get("/v1/models")
    async def list_models():
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat_completions():
        return {"ok": True}

    @app.post("/v1/voice/chat")
    async def voice_chat():
        return {"ok": True}

    @app.post("/api/v1/request")
    async def create_request():
        return {"ok": True}

    @app.post("/api/v1/request/{req_id}/status")
    async def update_request_status(req_id: str):
        return {"ok": True, "req_id": req_id}

    @app.get("/api/v1/identity")
    async def get_identity():
        return {"ok": True}

    @app.get("/v1/whoami")
    async def whoami(request: Request):
        return {
            "owner_id": getattr(request.state, "owner_id", None),
            "agent_name": getattr(request.state, "agent_name", None),
        }

    app.add_middleware(AuthorizationMiddleware, enforcement_mode=enforcement_mode)
    return app


def build_user_token(user_id: str | None = None) -> str:
    issuer = TokenIssuer(spire_enabled=False, jwt_secret=TEST_JWT_SECRET)
    card = EphemeralAgentCard(
        template_id="code_developer",
        template_version="1.0",
        agent_name="UserAgent",
        activated_capabilities=["file_read", "admin"],
        security_level="L3_ADMIN",
        user_id=user_id,
        session_id="user-session",
        expiry_hours=1,
    )
    return issuer.issue_token(card)


def build_workload_token() -> str:
    payload = {
        "iss": "spiffe://home-ai-lab/spire/server",
        "sub": "spiffe://home-ai-lab/agent/runtime",
        "aud": "home-ai-lab-agents",
        "exp": 4102444800,
        "iat": 1700000000,
        "nbf": 1700000000,
        "spiffe_id": "spiffe://home-ai-lab/agent/runtime",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def test_public_route_bypasses_auth_hard_mode():
    app = build_app("hard")
    client = TestClient(app)

    response = client.get("/v1/models")

    assert response.status_code == 200


def test_parse_mode_allows_missing_bearer_for_user_route():
    app = build_app("parse")
    client = TestClient(app)

    response = client.post("/v1/chat/completions")

    assert response.status_code == 200


def test_hard_mode_requires_bearer_for_user_route():
    app = build_app("hard")
    client = TestClient(app)

    response = client.post("/v1/chat/completions")

    assert response.status_code == 401
    assert "request_id" in response.json()


def test_hard_mode_requires_bearer_for_voice_route():
    app = build_app("hard")
    client = TestClient(app)

    response = client.post("/v1/voice/chat")

    assert response.status_code == 401
    assert "request_id" in response.json()


def test_api_key_route_bypasses_bearer_requirement_hard_mode():
    app = build_app("hard")
    client = TestClient(app)

    response = client.post("/api/v1/request")

    assert response.status_code == 200


def test_admin_endpoint_requires_admin_capability(monkeypatch):
    async def fake_validate(self, request, request_id, endpoint_class):
        return DummyCard(activated_capabilities=["file_read"], security_level="L2_USER")

    monkeypatch.setattr(AuthorizationMiddleware, "_validate_request", fake_validate)

    app = build_app("hard")
    client = TestClient(app)

    response = client.post(
        "/api/v1/request/REQ-1/status",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == 403
    assert "Insufficient role/scope" in response.text


def test_user_endpoint_rejects_workload_profile_in_hard_mode():
    app = build_app("hard")
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {build_workload_token()}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token profile not allowed for endpoint class"


def test_voice_endpoint_rejects_workload_profile_in_hard_mode():
    app = build_app("hard")
    client = TestClient(app)

    response = client.post(
        "/v1/voice/chat",
        headers={"Authorization": f"Bearer {build_workload_token()}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token profile not allowed for endpoint class"


def test_internal_endpoint_rejects_user_profile_in_hard_mode():
    app = build_app("hard")
    client = TestClient(app)

    response = client.get(
        "/api/v1/identity",
        headers={"Authorization": f"Bearer {build_user_token()}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token profile not allowed for endpoint class"


def test_user_owner_id_attached_to_request_state_from_token_claim():
    async def fake_validate(self, request, request_id, endpoint_class):
        return EphemeralAgentCard(
            template_id="code_developer",
            template_version="1.0",
            agent_name="UserAgent",
            activated_capabilities=["file_read"],
            security_level="L2_USER",
            user_id="user_123",
            session_id="user-session",
            expiry_hours=1,
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(AuthorizationMiddleware, "_validate_request", fake_validate)
    app = build_app("hard")
    client = TestClient(app)
    try:
        response = client.get(
            "/v1/whoami",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["owner_id"] == "user_123"
        assert payload["agent_name"] == "UserAgent"
    finally:
        monkeypatch.undo()
