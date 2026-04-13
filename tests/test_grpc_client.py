"""
Tests for agents/grpc/client.py — OpenClaude gRPC Client.

Tests the client wrapper logic with mocked gRPC and fallback to ModelRouter.
All network calls are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


# ---------------------------------------------------------------------------
# Client initialization tests
# ---------------------------------------------------------------------------

class TestGrpcClientInit:
    def test_default_config(self):
        from grpc.client import GrpcClient
        c = GrpcClient(enabled=False)
        assert c._host == "192.168.2.103"
        assert c._port == 50051
        assert c._enabled is False

    def test_custom_config(self):
        from grpc.client import GrpcClient
        c = GrpcClient(host="10.0.0.1", port=9090, timeout=60, enabled=False)
        assert c._host == "10.0.0.1"
        assert c._port == 9090
        assert c._timeout == 60

    def test_grpc_not_available_when_disabled(self):
        from grpc.client import GrpcClient
        c = GrpcClient(enabled=False)
        assert c.grpc_available is False


# ---------------------------------------------------------------------------
# Fallback mode tests (gRPC disabled → uses local ModelRouter)
# ---------------------------------------------------------------------------

class TestGrpcClientFallback:
    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_fallback(self, mock_post, mock_get):
        from grpc.client import GrpcClient
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "Fallback response"}}
        )
        client = GrpcClient(enabled=False)
        result = client.infer(prompt="test", model="qwen3:14b")
        assert result["content"] == "Fallback response"
        assert result["model_used"] == "qwen3:14b"

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_stream_fallback(self, mock_post, mock_get):
        import json
        from grpc.client import GrpcClient
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        lines = [
            json.dumps({"message": {"content": "chunk1"}, "done": False}).encode(),
            json.dumps({"message": {"content": ""}, "done": True, "eval_count": 3}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.iter_lines.return_value = lines
        mock_post.return_value = mock_resp

        client = GrpcClient(enabled=False)
        chunks = list(client.infer_stream(prompt="test", model="qwen3:14b"))
        assert len(chunks) == 2
        assert chunks[0]["content"] == "chunk1"
        assert chunks[1]["done"] is True

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_classify_fallback(self, mock_post, mock_get):
        from grpc.client import GrpcClient
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "CODE"}
        )
        client = GrpcClient(enabled=False)
        result = client.classify(prompt="Write a function")
        assert result["intent"] == "CODE"

    @patch("grpc.model_router.requests.get")
    def test_list_models_fallback(self, mock_get):
        from grpc.client import GrpcClient
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}, {"name": "qwen3:14b"}]}
        )
        client = GrpcClient(enabled=False)
        models = client.list_models()
        assert len(models) > 0
        assert any(m["name"] == "nemotron-mini" for m in models)

    @patch("grpc.model_router.requests.get")
    def test_health_fallback(self, mock_get):
        from grpc.client import GrpcClient
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "m"}]}
        )
        client = GrpcClient(enabled=False)
        health = client.health_check()
        assert health["status"] in ("healthy", "degraded", "unhealthy")
        assert "uptime_seconds" in health


# ---------------------------------------------------------------------------
# Close / cleanup tests
# ---------------------------------------------------------------------------

class TestGrpcClientClose:
    def test_close_no_channel(self):
        from grpc.client import GrpcClient
        client = GrpcClient(enabled=False)
        # Should not raise
        client.close()

    def test_close_with_channel(self):
        from grpc.client import GrpcClient
        client = GrpcClient(enabled=False)
        mock_channel = MagicMock()
        client._channel = mock_channel
        client._stub = MagicMock()
        client.close()
        mock_channel.close.assert_called_once()
        assert client._channel is None
        assert client._stub is None


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

class TestGrpcClientSingleton:
    def test_singleton(self):
        from grpc.client import get_grpc_client
        import grpc.client as mod
        mod._client_instance = None
        c1 = get_grpc_client()
        c2 = get_grpc_client()
        assert c1 is c2
        mod._client_instance = None


# ---------------------------------------------------------------------------
# Server tests (OpenClaudeServicer — protocol-agnostic layer)
# ---------------------------------------------------------------------------

class TestOpenClaudeServicer:
    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer(self, mock_post, mock_get):
        from grpc.server import OpenClaudeServicer
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "test response"}}
        )
        svc = OpenClaudeServicer()
        result = svc.infer(prompt="hello", model="qwen3:14b")
        assert result["content"] == "test response"

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_classify(self, mock_post, mock_get):
        from grpc.server import OpenClaudeServicer
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "RESEARCH"}
        )
        svc = OpenClaudeServicer()
        result = svc.classify("Find papers about AI")
        assert result["intent"] == "RESEARCH"

    @patch("grpc.model_router.requests.get")
    def test_list_models(self, mock_get):
        from grpc.server import OpenClaudeServicer
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        svc = OpenClaudeServicer()
        models = svc.list_models()
        assert isinstance(models, list)

    @patch("grpc.model_router.requests.get")
    def test_health_check(self, mock_get):
        from grpc.server import OpenClaudeServicer
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "m"}]}
        )
        svc = OpenClaudeServicer()
        health = svc.health_check()
        assert "status" in health
        assert "nodes" in health
        assert "uptime_seconds" in health

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_stream(self, mock_post, mock_get):
        import json
        from grpc.server import OpenClaudeServicer
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        lines = [
            json.dumps({"message": {"content": "hi"}, "done": False}).encode(),
            json.dumps({"message": {"content": ""}, "done": True, "eval_count": 1}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.iter_lines.return_value = lines
        mock_post.return_value = mock_resp

        svc = OpenClaudeServicer()
        chunks = list(svc.infer_stream(prompt="hi", model="qwen3:14b"))
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# OpenClaudeServer tests
# ---------------------------------------------------------------------------

class TestOpenClaudeServer:
    def test_server_init(self):
        from grpc.server import OpenClaudeServer
        server = OpenClaudeServer(port=55555, max_workers=2)
        assert server.port == 55555
        assert server.max_workers == 2

    def test_server_servicer(self):
        from grpc.server import OpenClaudeServer
        server = OpenClaudeServer()
        assert server.servicer is not None

    def test_server_stop_no_server(self):
        from grpc.server import OpenClaudeServer
        server = OpenClaudeServer()
        # Should not raise
        server.stop()

    def test_server_singleton(self):
        from grpc.server import get_openclaude_server
        import grpc.server as mod
        mod._server_instance = None
        s1 = get_openclaude_server()
        s2 = get_openclaude_server()
        assert s1 is s2
        mod._server_instance = None
