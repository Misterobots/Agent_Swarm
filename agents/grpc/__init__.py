"""
OpenClaude gRPC Server — Phase 6

Provides a gRPC inference gateway for the Hive platform.
Routes model inference requests to appropriate Ollama nodes
based on intent classification.

Components:
    - model_router: Intent → model → node routing logic
    - server: gRPC server implementation
    - client: gRPC client library
    - interceptors: Auth + logging interceptors
"""

GRPC_AVAILABLE = False
try:
    import grpc  # noqa: F401
    GRPC_AVAILABLE = True
except ImportError:
    pass
