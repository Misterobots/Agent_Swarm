# Phase 6 Completion Report — OpenClaude gRPC Server

**Date:** 2026-04-13  
**Tests:** 74 Phase 6 + 434 prior phases = **508 total passing** (16 pre-existing failures in unrelated modules)  

---

## Changes

### New Files (8)
| File | Purpose |
|------|---------|
| `agents/grpc/__init__.py` | Package init with `GRPC_AVAILABLE` flag |
| `agents/grpc/openclaude.proto` | Protobuf service definition — InferenceService with 5 RPCs |
| `agents/grpc/generate.sh` | Proto compilation script using `grpc_tools.protoc` |
| `agents/grpc/model_router.py` | Core intent→model→node routing logic, Ollama HTTP integration |
| `agents/grpc/server.py` | gRPC server wrapping ModelRouter, protobuf adapter, CLI entrypoint |
| `agents/grpc/client.py` | gRPC client with automatic fallback to local ModelRouter |
| `agents/grpc/interceptors.py` | Auth interceptor (Authentik OAuth2 token validation) + request logger |
| `agents/grpc/Dockerfile` | Container image for Turing deployment with pb2 generation at build |

### New Test Files (3)
| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_grpc_model_router.py` | 32 | InferenceResult, ClassificationResult, ModelStatus, ModelRouter init/classify/infer/stream/health, IntentModelMap |
| `tests/test_grpc_interceptors.py` | 22 | AuthResult, TokenValidator disabled/enabled/cache, RequestLogger, singletons, exempt methods |
| `tests/test_grpc_client.py` | 20 | GrpcClient init/fallback/close/singleton, OpenClaudeServicer, OpenClaudeServer |

### Modified Files (6)
| File | Changes |
|------|---------|
| `agents/config.py` | Added Phase 6 config: GRPC_SERVER_HOST, GRPC_SERVER_PORT, GRPC_GATEWAY_ENABLED, GRPC_TIMEOUT, GRPC_MAX_WORKERS, GRPC_AUTH_ENABLED, GRPC_AUTH_CACHE_TTL |
| `agents/main.py` | Added GrpcInferRequest model, 4 REST gateway endpoints: POST /api/v1/grpc/infer, POST /api/v1/grpc/classify, GET /api/v1/grpc/models, GET /api/v1/grpc/health |
| `agents/mcp/tool_hooks.py` | Added 4 tool hooks: hive.grpc.infer, hive.grpc.classify, hive.grpc.models, hive.grpc.health (total: 19) |
| `agents/mcp/server.py` | Added 4 MCP tool descriptors (total: 20) |
| `agents/registry.py` | Code Developer + Security Agent capabilities += grpc_infer |
| `turing_gateway/docker-compose.yml` | Added `openclaude-grpc` service with Traefik routing, Authentik auth, SPIFFE ID |

---

## Features Delivered

### 1. Protobuf Service Definition (`openclaude.proto`)
- Package `openclaude.v1` with `InferenceService`
- **5 RPCs:** `Infer` (unary), `InferStream` (server streaming), `Classify`, `ListModels`, `HealthCheck`
- Messages: `InferRequest` (prompt, model, intent, max_tokens, temperature, session_id, history, auth_token), `InferResponse`, `InferChunk`, `ClassifyRequest/Response`, `ChatMessage`, `ModelInfo`, `ModelList`, `HealthStatus`

### 2. Model Router (`model_router.py`)
- **Intent classification** using nemotron-mini via Ollama `/api/generate`
- **Model routing map:** CODE→qwen2.5-coder:14b, GENERAL/DEFAULT→qwen3:14b, RESEARCH→llama3.2:3b, VISION→moondream
- **Multi-node inference** across Lovelace (2× RTX 5060 Ti, 32GB VRAM) and Turing (RTX 3070 Ti, 8GB VRAM)
- **Health monitoring** with 30s TTL cache per Ollama node
- **Streaming support** via `iter_lines()` on Ollama `/api/chat` with `stream=true`
- Context windows tracked per model (4K–40K tokens)

### 3. gRPC Server (`server.py`)
- `OpenClaudeServicer` — Protocol-agnostic wrapper around ModelRouter
- `GrpcInferenceServicer` — Protobuf adapter, only loaded when pb2 stubs available
- `OpenClaudeServer` — Server lifecycle with `ThreadPoolExecutor(max_workers=4)`
- 16MB max message size, configurable port and workers
- CLI entrypoint with `argparse` and graceful signal handling

### 4. gRPC Client (`client.py`)
- Lazy gRPC channel/stub initialization
- **Automatic fallback** to local ModelRouter on any gRPC failure
- All 5 RPCs: `infer()`, `infer_stream()`, `classify()`, `list_models()`, `health_check()`
- Configurable: host (192.168.2.103), port (50051), timeout (120s)

### 5. Auth Interceptors (`interceptors.py`)
- **TokenValidator** — Validates OAuth2 Bearer tokens against Authentik userinfo endpoint
- Hash-based token cache with configurable TTL (default 300s)
- **AuthInterceptor** (grpc.ServerInterceptor) — Extracts tokens from gRPC metadata
- Auth-exempt methods: `HealthCheck`, `ListModels`
- **RequestLogger** — Audit logging for all gRPC requests

### 6. Docker Deployment (`Dockerfile` + `docker-compose.yml`)
- Python 3.11-slim base with grpcio, grpcio-tools, protobuf, requests
- pb2 stubs generated at Docker build time
- Non-root user, health check via `grpc.channel_ready_future`
- **Traefik routing:** Internal h2c via `PathPrefix(/grpc)`, external HTTPS via `grpc.shivelymedia.com`
- **Authentik forward auth** middleware on external route
- **TLS termination** via certresolver=cfdns (Cloudflare DNS challenge)
- SPIFFE ID: `spiffe://home-ai-lab/inference/openclaude-grpc`

### 7. REST Gateway (4 endpoints in `main.py`)
- `POST /api/v1/grpc/infer` — REST proxy to gRPC inference (prompt, model, intent, max_tokens, temperature)
- `POST /api/v1/grpc/classify` — REST proxy to gRPC classification
- `GET /api/v1/grpc/models` — List available models via gRPC gateway
- `GET /api/v1/grpc/health` — Gateway health check with node status
- **Pattern:** UI → REST → FastAPI → GrpcClient → OpenClaude gRPC → Ollama

---

## Architecture

```
┌───────────────────────────────────────────────────┐
│                   Hive UI (Next.js)               │
│               hive.shivelymedia.com               │
└──────────────────────┬────────────────────────────┘
                       │ REST API
                       ▼
┌───────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)             │
│            /api/v1/grpc/* REST Gateway            │
└──────────────────────┬────────────────────────────┘
                       │ GrpcClient
                       ▼
┌───────────────────────────────────────────────────┐
│         OpenClaude gRPC Server (port 50051)        │
│   ┌─────────────┐  ┌──────────────┐               │
│   │AuthInterceptor│  │RequestLogger│               │
│   └──────┬──────┘  └──────────────┘               │
│          ▼                                         │
│   ┌─────────────────────┐                          │
│   │  OpenClaudeServicer │                          │
│   └──────────┬──────────┘                          │
│              ▼                                     │
│   ┌─────────────────────┐                          │
│   │    ModelRouter       │                          │
│   │  classify → route    │                          │
│   └───────┬──────┬──────┘                          │
└───────────┼──────┼────────────────────────────────┘
            │      │
     ┌──────┘      └──────┐
     ▼                     ▼
┌──────────┐        ┌──────────┐
│Lovelace │        │  Turing    │
│2×5060 Ti │        │3070 Ti   │
│Ollama    │        │Ollama    │
│:11434    │        │:11434    │
└──────────┘        └──────────┘
```

## Model Routing Table

| Intent | Model | Node Preference | Context Window |
|--------|-------|----------------|----------------|
| CODE | qwen2.5-coder:14b-instruct-q4_k_m | Any healthy | 32,768 |
| GENERAL/DEFAULT | qwen3:14b | Any healthy | 40,960 |
| RESEARCH | llama3.2:3b | Any healthy | 8,192 |
| VISION/IMAGE | moondream:latest | Any healthy | 2,048 |
| *Router/Classifier* | nemotron-mini | Any healthy | 4,096 |

---

## Test Results

```
74 passed in 0.90s

test_grpc_model_router.py  — 32 passed
test_grpc_interceptors.py  — 22 passed
test_grpc_client.py        — 20 passed
```

Full regression: **508 passed**, 16 failed (all pre-existing in test_mars_loop, test_training_pipeline, test_voice_cloning, test_openai_compat, test_authorization_middleware — none in Phase 6).

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `agents/grpc/openclaude.proto` | Definition | gRPC protobuf service definition |
| `agents/grpc/model_router.py` | Implementation | Intent-based model routing |
| `agents/grpc/server.py` | Implementation | gRPC inference server |
| `agents/grpc/client.py` | Implementation | gRPC client library |
| `agents/grpc/interceptors.py` | Implementation | OAuth2 auth interceptors |
| `agents/grpc/Dockerfile` | Infrastructure | gRPC server container |
| `turing_gateway/docker-compose.yml` | Infrastructure | Traefik + gRPC deployment |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-15 | AI-Copilot | Initial Phase 6 report — OpenClaude gRPC |

</details>

---

## Maintenance & Update Guide

This is a **historical phase report**. Update only if:

- gRPC proto schema changes (regenerate stubs).
- Model routing logic is updated.
- A rollback to this phase is executed.

---

## Verification

| Claim | How to Verify |
|-------|---------------|
| gRPC server healthy | `grpcurl -plaintext localhost:50051 grpc.health.v1.Health/Check` |
| Traefik routes gRPC | `curl https://grpc.shivelymedia.com` → verify TLS + routing |
| 508 tests pass | `pytest tests/ -q` → verify pass count |
