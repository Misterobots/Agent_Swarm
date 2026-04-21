"""
server.py — OpenClaude gRPC Server

Headless gRPC inference gateway deployed on Turing.  Routes inference
requests through ModelRouter to Ollama nodes across the cluster.

Requires generated protobuf stubs (run generate.sh first).
Falls back gracefully when protobuf stubs are not available.

Usage:
    python -m agents.grpc.server          # Start gRPC server
    python -m agents.grpc.server --port 50051 --workers 4
"""

import logging
import os
import time
from concurrent import futures
from typing import Optional

logger = logging.getLogger(__name__)

# gRPC server config
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))
GRPC_MAX_WORKERS = int(os.getenv("GRPC_MAX_WORKERS", "4"))
GRPC_MAX_MESSAGE_SIZE = int(os.getenv("GRPC_MAX_MESSAGE_SIZE", str(16 * 1024 * 1024)))  # 16MB

# ---------------------------------------------------------------------------
# Try importing generated protobuf stubs
# ---------------------------------------------------------------------------
_PB2_AVAILABLE = False
try:
    from agents.grpc import openclaude_pb2 as pb2
    from agents.grpc import openclaude_pb2_grpc as pb2_grpc
    import grpc
    _PB2_AVAILABLE = True
except ImportError:
    try:
        # Try relative import (when running as __main__)
        import openclaude_pb2 as pb2       # type: ignore[no-redef]
        import openclaude_pb2_grpc as pb2_grpc  # type: ignore[no-redef]
        import grpc
        _PB2_AVAILABLE = True
    except ImportError:
        pb2 = None       # type: ignore[assignment]
        pb2_grpc = None   # type: ignore[assignment]
        grpc = None       # type: ignore[assignment]
        logger.warning("gRPC protobuf stubs not available — run generate.sh")


# ---------------------------------------------------------------------------
# Servicer implementation (protocol-agnostic logic)
# ---------------------------------------------------------------------------
class OpenClaudeServicer:
    """
    Implements the InferenceService gRPC interface.
    Core logic is delegated to ModelRouter so it can be tested independently.
    """

    def __init__(self, router=None, auth_validator=None):
        from agents.grpc.model_router import get_model_router
        self._router = router or get_model_router()
        self._auth_validator = auth_validator
        self._start_time = time.time()
        logger.info("OpenClaudeServicer initialized")

    def infer(self, prompt: str, model: str = "", intent: str = "",
              max_tokens: int = 0, temperature: float = 0.7,
              history: Optional[list] = None) -> dict:
        """Protocol-agnostic inference. Returns dict."""
        result = self._router.infer(
            prompt=prompt, model=model, intent=intent,
            max_tokens=max_tokens, temperature=temperature,
            history=history,
        )
        return result.to_dict()

    def infer_stream(self, prompt: str, model: str = "", intent: str = "",
                     max_tokens: int = 0, temperature: float = 0.7,
                     history: Optional[list] = None):
        """Protocol-agnostic streaming inference. Yields dicts."""
        yield from self._router.infer_stream(
            prompt=prompt, model=model, intent=intent,
            max_tokens=max_tokens, temperature=temperature,
            history=history,
        )

    def classify(self, prompt: str) -> dict:
        """Protocol-agnostic intent classification. Returns dict."""
        result = self._router.classify_intent(prompt)
        return result.to_dict()

    def list_models(self) -> list:
        """List available models. Returns list of dicts."""
        return [m.to_dict() for m in self._router.list_models()]

    def health_check(self) -> dict:
        """Health check. Returns dict."""
        status, nodes, model_count = self._router.health_check()
        return {
            "status": status,
            "nodes": nodes,
            "uptime_seconds": self._router.uptime_seconds,
            "models_available": model_count,
        }


# ---------------------------------------------------------------------------
# gRPC Servicer (protobuf adapter — only used when pb2 available)
# ---------------------------------------------------------------------------
if _PB2_AVAILABLE:
    class GrpcInferenceServicer(pb2_grpc.InferenceServiceServicer):
        """gRPC transport adapter wrapping OpenClaudeServicer."""

        def __init__(self, servicer: OpenClaudeServicer):
            self._svc = servicer

        def Infer(self, request, context):
            history = [{"role": m.role, "content": m.content} for m in request.history]
            result = self._svc.infer(
                prompt=request.prompt, model=request.model,
                intent=request.intent, max_tokens=request.max_tokens,
                temperature=request.temperature, history=history,
            )
            return pb2.InferResponse(
                content=result["content"],
                model_used=result["model_used"],
                node=result["node"],
                tokens_used=result.get("tokens_used", 0),
                duration_ms=result.get("duration_ms", 0.0),
                intent_detected=result.get("intent_detected", ""),
            )

        def InferStream(self, request, context):
            history = [{"role": m.role, "content": m.content} for m in request.history]
            for chunk in self._svc.infer_stream(
                prompt=request.prompt, model=request.model,
                intent=request.intent, max_tokens=request.max_tokens,
                temperature=request.temperature, history=history,
            ):
                yield pb2.InferChunk(
                    content=chunk.get("content", ""),
                    done=chunk.get("done", False),
                    model_used=chunk.get("model_used", ""),
                    tokens_used=chunk.get("tokens_used", 0),
                )

        def Classify(self, request, context):
            result = self._svc.classify(request.prompt)
            return pb2.ClassifyResponse(
                intent=result["intent"],
                confidence=result["confidence"],
                suggested_model=result["suggested_model"],
                suggested_node=result["suggested_node"],
            )

        def ListModels(self, request, context):
            models = self._svc.list_models()
            return pb2.ModelList(models=[
                pb2.ModelInfo(
                    name=m["name"], role=m["role"],
                    context_window=m["context_window"],
                    available=m["available"], node=m["node"],
                ) for m in models
            ])

        def HealthCheck(self, request, context):
            result = self._svc.health_check()
            return pb2.HealthStatus(
                status=result["status"],
                nodes=result["nodes"],
                uptime_seconds=result["uptime_seconds"],
                models_available=result["models_available"],
            )


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------
class OpenClaudeServer:
    """Manages the gRPC server lifecycle."""

    def __init__(self, port: int = GRPC_PORT, max_workers: int = GRPC_MAX_WORKERS):
        self.port = port
        self.max_workers = max_workers
        self._server = None
        self._servicer = OpenClaudeServicer()

    @property
    def servicer(self) -> OpenClaudeServicer:
        return self._servicer

    def start(self) -> bool:
        """Start the gRPC server. Returns False if pb2 not available."""
        if not _PB2_AVAILABLE:
            logger.error("Cannot start gRPC server: protobuf stubs not generated")
            return False

        self._server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            options=[
                ("grpc.max_send_message_length", GRPC_MAX_MESSAGE_SIZE),
                ("grpc.max_receive_message_length", GRPC_MAX_MESSAGE_SIZE),
            ],
        )

        grpc_servicer = GrpcInferenceServicer(self._servicer)
        pb2_grpc.add_InferenceServiceServicer_to_server(grpc_servicer, self._server)

        # Add interceptors
        try:
            from agents.grpc.interceptors import get_auth_interceptor
            interceptor = get_auth_interceptor()
            if interceptor:
                logger.info("Auth interceptor enabled")
        except ImportError:
            pass

        bind_addr = f"[::]:{self.port}"
        self._server.add_insecure_port(bind_addr)
        self._server.start()
        logger.info(f"OpenClaude gRPC server started on {bind_addr}")
        return True

    def stop(self, grace: float = 5.0):
        """Stop the gRPC server."""
        if self._server:
            self._server.stop(grace)
            logger.info("OpenClaude gRPC server stopped")
            self._server = None

    def wait_for_termination(self):
        """Block until server terminates."""
        if self._server:
            self._server.wait_for_termination()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_server_instance: Optional[OpenClaudeServer] = None


def get_openclaude_server() -> OpenClaudeServer:
    global _server_instance
    if _server_instance is None:
        _server_instance = OpenClaudeServer()
    return _server_instance


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import signal

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="OpenClaude gRPC Server")
    parser.add_argument("--port", type=int, default=GRPC_PORT, help="gRPC listen port")
    parser.add_argument("--workers", type=int, default=GRPC_MAX_WORKERS, help="Max worker threads")
    args = parser.parse_args()

    server = OpenClaudeServer(port=args.port, max_workers=args.workers)

    def _shutdown(signum, frame):
        logger.info("Received shutdown signal")
        server.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if server.start():
        logger.info(f"Listening on port {args.port} with {args.workers} workers")
        server.wait_for_termination()
    else:
        logger.error("Failed to start server")
        exit(1)


