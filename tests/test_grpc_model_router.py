"""
Tests for agents/grpc/model_router.py — Intent → Model → Node routing.

Tests the core routing logic without any gRPC dependency.
All Ollama HTTP calls are mocked.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


# ---------------------------------------------------------------------------
# Data class tests
# ---------------------------------------------------------------------------

class TestInferenceResult:
    def test_success_property(self):
        from grpc.model_router import InferenceResult
        r = InferenceResult(content="hello", model_used="m", node="n")
        assert r.success is True

    def test_failure_property(self):
        from grpc.model_router import InferenceResult
        r = InferenceResult(content="", model_used="m", node="n", error="fail")
        assert r.success is False

    def test_to_dict(self):
        from grpc.model_router import InferenceResult
        r = InferenceResult(content="x", model_used="m", node="n", tokens_used=10, duration_ms=42.5)
        d = r.to_dict()
        assert d["content"] == "x"
        assert d["model_used"] == "m"
        assert d["tokens_used"] == 10
        assert d["duration_ms"] == 42.5
        assert d["error"] is None

    def test_to_dict_with_error(self):
        from grpc.model_router import InferenceResult
        r = InferenceResult(content="", model_used="m", node="n", error="boom")
        d = r.to_dict()
        assert d["error"] == "boom"


class TestClassificationResult:
    def test_to_dict(self):
        from grpc.model_router import ClassificationResult
        c = ClassificationResult(intent="CODE", confidence=0.9, suggested_model="qwen", suggested_node="host1")
        d = c.to_dict()
        assert d["intent"] == "CODE"
        assert d["confidence"] == 0.9
        assert d["suggested_model"] == "qwen"

    def test_fields(self):
        from grpc.model_router import ClassificationResult
        c = ClassificationResult(intent="GENERAL", confidence=0.5, suggested_model="m", suggested_node="n")
        assert c.intent == "GENERAL"


class TestModelStatus:
    def test_to_dict(self):
        from grpc.model_router import ModelStatus
        m = ModelStatus(name="qwen3:14b", role="general", context_window=40960, available=True, node="host1")
        d = m.to_dict()
        assert d["name"] == "qwen3:14b"
        assert d["role"] == "general"
        assert d["available"] is True


# ---------------------------------------------------------------------------
# ModelRouter tests
# ---------------------------------------------------------------------------

class TestModelRouterInit:
    def test_default_hosts(self):
        from grpc.model_router import ModelRouter
        router = ModelRouter()
        assert len(router._hosts) >= 1

    def test_custom_hosts(self):
        from grpc.model_router import ModelRouter
        router = ModelRouter(ollama_hosts=["http://a:11434", "http://b:11434"])
        assert router._hosts == ["http://a:11434", "http://b:11434"]

    def test_deduplicates_hosts(self):
        from grpc.model_router import ModelRouter
        router = ModelRouter(ollama_hosts=["http://a:11434", "http://a:11434"])
        assert len(router._hosts) == 1

    def test_filters_empty_hosts(self):
        from grpc.model_router import ModelRouter
        router = ModelRouter(ollama_hosts=["http://a:11434", "", None])
        assert router._hosts == ["http://a:11434"]

    def test_custom_intent_map(self):
        from grpc.model_router import ModelRouter
        m = {"CODE": "my-model"}
        router = ModelRouter(intent_model_map=m)
        assert router._intent_map["CODE"] == "my-model"

    def test_uptime(self):
        from grpc.model_router import ModelRouter
        router = ModelRouter()
        assert router.uptime_seconds >= 0


class TestModelRouterClassify:
    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_classify_code(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        # Mock health check
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        # Mock classification call
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "CODE"}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.classify_intent("Write a Python function")
        assert result.intent == "CODE"
        assert result.confidence > 0.5

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_classify_general(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "GENERAL"}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.classify_intent("What is the meaning of life?")
        assert result.intent == "GENERAL"

    @patch("grpc.model_router.requests.get")
    def test_classify_no_router_model(self, mock_get):
        from grpc.model_router import ModelRouter
        # No models available
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": []}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.classify_intent("anything")
        assert result.intent == "GENERAL"
        assert result.confidence == 0.5

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_classify_error(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}]}
        )
        mock_post.side_effect = Exception("Connection refused")
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.classify_intent("fail")
        assert result.intent == "GENERAL"
        assert result.confidence == 0.3


class TestModelRouterInfer:
    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_explicit_model(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "Hello world"}}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.infer("Say hi", model="qwen3:14b")
        assert result.success
        assert result.content == "Hello world"
        assert result.model_used == "qwen3:14b"

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_with_intent(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter, CODE_MODEL
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": CODE_MODEL}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "def sort(lst): return sorted(lst)"}}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.infer("Write sort", intent="CODE")
        assert result.success
        assert result.intent_detected == "CODE"

    @patch("grpc.model_router.requests.get")
    def test_infer_no_healthy_nodes(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.side_effect = Exception("unreachable")
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.infer("test", model="qwen3:14b")
        assert not result.success
        assert "No healthy" in result.error

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_with_history(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "Continued conversation"}}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        result = router.infer("continue", model="qwen3:14b", history=history)
        # Verify chat was called with history + new message
        call_args = mock_post.call_args
        messages = call_args[1]["json"]["messages"]
        assert len(messages) == 3  # 2 history + 1 new

    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_infer_ollama_error(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        mock_post.side_effect = Exception("Ollama timeout")
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        result = router.infer("test", model="qwen3:14b")
        assert not result.success
        assert "Ollama timeout" in result.error
        assert result.duration_ms > 0


class TestModelRouterStream:
    @patch("grpc.model_router.requests.get")
    @patch("grpc.model_router.requests.post")
    def test_stream_success(self, mock_post, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3:14b"}]}
        )
        # Mock streaming response
        lines = [
            json.dumps({"message": {"content": "Hello"}, "done": False}).encode(),
            json.dumps({"message": {"content": " world"}, "done": False}).encode(),
            json.dumps({"message": {"content": ""}, "done": True, "eval_count": 5}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.iter_lines.return_value = lines
        mock_post.return_value = mock_resp

        router = ModelRouter(ollama_hosts=["http://test:11434"])
        chunks = list(router.infer_stream("test", model="qwen3:14b"))
        assert len(chunks) == 3
        assert chunks[0]["content"] == "Hello"
        assert chunks[1]["content"] == " world"
        assert chunks[2]["done"] is True

    @patch("grpc.model_router.requests.get")
    def test_stream_no_nodes(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.side_effect = Exception("down")
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        chunks = list(router.infer_stream("test", model="qwen3:14b"))
        assert len(chunks) == 1
        assert "Error" in chunks[0]["content"]
        assert chunks[0]["done"] is True


class TestModelRouterModels:
    @patch("grpc.model_router.requests.get")
    def test_list_models(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "nemotron-mini"}, {"name": "qwen3:14b"}]}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        models = router.list_models()
        assert len(models) > 0
        names = [m.name for m in models]
        assert "nemotron-mini" in names


class TestModelRouterHealth:
    @patch("grpc.model_router.requests.get")
    def test_health_all_healthy(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "m"}]}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        status, nodes, count = router.health_check()
        assert status == "healthy"
        assert nodes["http://test:11434"] is True

    @patch("grpc.model_router.requests.get")
    def test_health_all_down(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.side_effect = Exception("down")
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        status, nodes, count = router.health_check()
        assert status == "unhealthy"
        assert count == 0

    @patch("grpc.model_router.requests.get")
    def test_health_degraded(self, mock_get):
        from grpc.model_router import ModelRouter
        def side_effect(url, timeout=3):
            if "a:" in url:
                return MagicMock(status_code=200, json=lambda: {"models": [{"name": "m"}]})
            raise Exception("down")
        mock_get.side_effect = side_effect
        router = ModelRouter(ollama_hosts=["http://a:11434", "http://b:11434"])
        status, nodes, count = router.health_check()
        assert status == "degraded"

    @patch("grpc.model_router.requests.get")
    def test_health_cache(self, mock_get):
        from grpc.model_router import ModelRouter
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "m"}]}
        )
        router = ModelRouter(ollama_hosts=["http://test:11434"])
        # First call
        router.health_check()
        call_count_1 = mock_get.call_count
        # Second call (cached)
        router._check_node("http://test:11434")
        assert mock_get.call_count == call_count_1  # No new HTTP call


class TestModelRouterSingleton:
    def test_singleton(self):
        from grpc.model_router import get_model_router, _router_instance
        import grpc.model_router as mod
        mod._router_instance = None
        r1 = get_model_router()
        r2 = get_model_router()
        assert r1 is r2
        mod._router_instance = None


class TestIntentModelMap:
    def test_all_intents_mapped(self):
        from grpc.model_router import INTENT_MODEL_MAP
        expected = {"CODE", "GENERAL", "DEFAULT", "RESEARCH", "VISION", "IMAGE", "3D", "COORDINATE"}
        assert set(INTENT_MODEL_MAP.keys()) == expected

    def test_context_windows(self):
        from grpc.model_router import CONTEXT_WINDOWS
        assert CONTEXT_WINDOWS["nemotron-mini"] == 4096
        assert CONTEXT_WINDOWS["qwen3:14b"] == 40960
        assert "default" in CONTEXT_WINDOWS
