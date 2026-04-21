"""
client.py — OpenClaude gRPC Client

Provides a Python client for calling the OpenClaude gRPC server.
Falls back to direct REST calls to Ollama if gRPC is unavailable.

Usage:
    from agents.grpc.client import get_grpc_client

    client = get_grpc_client()
    result = client.infer("Write a Python function to sort a list")
    print(result)

    for chunk in client.infer_stream("Explain quantum computing"):
        print(chunk["content"], end="")
"""

import logging
import os
import time
from typing import Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Configuration
GRPC_SERVER_HOST = os.getenv("GRPC_SERVER_HOST", "192.168.2.103")
GRPC_SERVER_PORT = int(os.getenv("GRPC_SERVER_PORT", "50051"))
GRPC_TIMEOUT = int(os.getenv("GRPC_TIMEOUT", "120"))
GRPC_GATEWAY_ENABLED = os.getenv("GRPC_GATEWAY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# Try importing gRPC
_PB2_AVAILABLE = False
try:
    import grpc
    from agents.grpc import openclaude_pb2 as pb2
    from agents.grpc import openclaude_pb2_grpc as pb2_grpc
    _PB2_AVAILABLE = True
except ImportError:
    try:
        import grpc  # type: ignore[no-redef]
        import openclaude_pb2 as pb2       # type: ignore[no-redef]
        import openclaude_pb2_grpc as pb2_grpc  # type: ignore[no-redef]
        _PB2_AVAILABLE = True
    except ImportError:
        grpc = None   # type: ignore[assignment]
        pb2 = None    # type: ignore[assignment]
        pb2_grpc = None  # type: ignore[assignment]


class GrpcClient:
    """
    Client for the OpenClaude gRPC inference gateway.

    When gRPC protobuf stubs are available and the gateway is enabled,
    routes requests through the gRPC server on Turing.  Otherwise falls
    back to the local ModelRouter for direct Ollama calls.
    """

    def __init__(
        self,
        host: str = GRPC_SERVER_HOST,
        port: int = GRPC_SERVER_PORT,
        timeout: int = GRPC_TIMEOUT,
        enabled: bool = GRPC_GATEWAY_ENABLED,
    ):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._enabled = enabled and _PB2_AVAILABLE
        self._channel = None
        self._stub = None
        self._fallback_router = None

    @property
    def grpc_available(self) -> bool:
        return self._enabled and _PB2_AVAILABLE

    def _get_stub(self):
        """Lazy-initialize the gRPC channel and stub."""
        if self._stub is None and self._enabled and _PB2_AVAILABLE:
            target = f"{self._host}:{self._port}"
            self._channel = grpc.insecure_channel(
                target,
                options=[
                    ("grpc.max_send_message_length", 16 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 16 * 1024 * 1024),
                ],
            )
            self._stub = pb2_grpc.InferenceServiceStub(self._channel)
            logger.info(f"gRPC client connected to {target}")
        return self._stub

    def _get_fallback(self):
        """Lazy-initialize the local ModelRouter fallback."""
        if self._fallback_router is None:
            from agents.grpc.model_router import get_model_router
            self._fallback_router = get_model_router()
        return self._fallback_router

    def infer(
        self,
        prompt: str,
        model: str = "",
        intent: str = "",
        max_tokens: int = 0,
        temperature: float = 0.7,
        session_id: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        auth_token: str = "",
    ) -> dict:
        """
        Synchronous inference via gRPC gateway.
        Falls back to local ModelRouter if gRPC unavailable.
        """
        stub = self._get_stub()
        if stub is None:
            # Fallback to local router
            router = self._get_fallback()
            result = router.infer(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                history=history,
            )
            return result.to_dict()

        try:
            chat_msgs = []
            if history:
                chat_msgs = [pb2.ChatMessage(role=m["role"], content=m["content"]) for m in history]

            request = pb2.InferRequest(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                session_id=session_id, history=chat_msgs,
                auth_token=auth_token,
            )
            response = stub.Infer(request, timeout=self._timeout)
            return {
                "content": response.content,
                "model_used": response.model_used,
                "node": response.node,
                "tokens_used": response.tokens_used,
                "duration_ms": response.duration_ms,
                "intent_detected": response.intent_detected,
            }
        except Exception as e:
            logger.error(f"gRPC infer failed, falling back to local: {e}")
            router = self._get_fallback()
            result = router.infer(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                history=history,
            )
            return result.to_dict()

    def infer_stream(
        self,
        prompt: str,
        model: str = "",
        intent: str = "",
        max_tokens: int = 0,
        temperature: float = 0.7,
        session_id: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        auth_token: str = "",
    ) -> Generator[Dict, None, None]:
        """
        Streaming inference via gRPC gateway.
        Falls back to local ModelRouter if gRPC unavailable.
        """
        stub = self._get_stub()
        if stub is None:
            router = self._get_fallback()
            yield from router.infer_stream(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                history=history,
            )
            return

        try:
            chat_msgs = []
            if history:
                chat_msgs = [pb2.ChatMessage(role=m["role"], content=m["content"]) for m in history]

            request = pb2.InferRequest(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                session_id=session_id, history=chat_msgs,
                auth_token=auth_token,
            )
            for chunk in stub.InferStream(request, timeout=self._timeout):
                yield {
                    "content": chunk.content,
                    "done": chunk.done,
                    "model_used": chunk.model_used,
                    "tokens_used": chunk.tokens_used,
                }
        except Exception as e:
            logger.error(f"gRPC stream failed, falling back to local: {e}")
            router = self._get_fallback()
            yield from router.infer_stream(
                prompt=prompt, model=model, intent=intent,
                max_tokens=max_tokens, temperature=temperature,
                history=history,
            )

    def classify(self, prompt: str, auth_token: str = "") -> dict:
        """Classify intent via gRPC gateway."""
        stub = self._get_stub()
        if stub is None:
            router = self._get_fallback()
            result = router.classify_intent(prompt)
            return result.to_dict()

        try:
            request = pb2.ClassifyRequest(prompt=prompt)
            response = stub.Classify(request, timeout=self._timeout)
            return {
                "intent": response.intent,
                "confidence": response.confidence,
                "suggested_model": response.suggested_model,
                "suggested_node": response.suggested_node,
            }
        except Exception as e:
            logger.error(f"gRPC classify failed, falling back: {e}")
            router = self._get_fallback()
            result = router.classify_intent(prompt)
            return result.to_dict()

    def list_models(self) -> list:
        """List models via gRPC gateway."""
        stub = self._get_stub()
        if stub is None:
            router = self._get_fallback()
            return [m.to_dict() for m in router.list_models()]

        try:
            response = stub.ListModels(pb2.Empty(), timeout=self._timeout)
            return [{
                "name": m.name, "role": m.role,
                "context_window": m.context_window,
                "available": m.available, "node": m.node,
            } for m in response.models]
        except Exception as e:
            logger.error(f"gRPC list_models failed: {e}")
            router = self._get_fallback()
            return [m.to_dict() for m in router.list_models()]

    def health_check(self) -> dict:
        """Health check via gRPC gateway."""
        stub = self._get_stub()
        if stub is None:
            router = self._get_fallback()
            status, nodes, count = router.health_check()
            return {"status": status, "nodes": nodes, "uptime_seconds": router.uptime_seconds, "models_available": count}

        try:
            response = stub.HealthCheck(pb2.Empty(), timeout=self._timeout)
            return {
                "status": response.status,
                "nodes": dict(response.nodes),
                "uptime_seconds": response.uptime_seconds,
                "models_available": response.models_available,
            }
        except Exception as e:
            logger.error(f"gRPC health failed: {e}")
            return {"status": "unreachable", "nodes": {}, "uptime_seconds": 0, "models_available": 0, "error": str(e)}

    def close(self):
        """Close the gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("gRPC client channel closed")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_client_instance: Optional[GrpcClient] = None


def get_grpc_client() -> GrpcClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = GrpcClient()
    return _client_instance


