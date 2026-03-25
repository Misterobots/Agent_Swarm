# Admin: Design Framework

> **Back to:** [Documentation Index](../INDEX.md)
> **See also:** [Technical Reference](technical_reference.md) · [Security](security.md)

**Version**: 3.3 · **Status**: Production · **Last Updated**: 2026-03-23

---

## 1. System Philosophy

The Agentic Hive is built around three principles:

1. **Specialization over generalization**: Different tasks use purpose-built agents with the right model for the job. A routing model is fast and cheap; a coding model is deep and large. Neither substitutes for the other.

2. **Inference-time verification**: Output quality is enforced at runtime, not post-hoc. The MarsRL loop prevents bad output from ever reaching the user.

3. **Locality and privacy**: All inference runs on-premises. No external API calls. Training improves local models continuously from real usage data.

---

## 2. Three-Tier Hardware Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  TIER 2 — OPS/GATEWAY                                               │
│  Gateway Node · <gateway-node-ip>                                   │
│  Traefik v3.6 · Prometheus · Grafana · Loki · Authentik SSO        │
│  Ollama (nemotron-8B, llama-guard-3) · OpenHands · IDEs             │
└──────────────────────────┬──────────────┬──────────────────────────┘
                           │              │
        ┌──────────────────▼──┐      ┌────▼───────────────────────┐
        │  TIER 3 — COMPUTE   │      │  TIER 1 — CONTROL          │
        │  Execution Node     │      │  Control Node              │
        │  <execution-node-ip>│      │  <control-node-ip>         │
        │                     │      │                             │
        │  RTX 5060 Ti 16GB   │      │  SPIRE Server              │
        │  Ollama (qwen3.5)   │      │  Langfuse                  │
        │  Agent Runtime      │      │  PostgreSQL                │
        │  ComfyUI            │      │  ClickHouse                │
        │  Voice Services     │      │  MinIO                     │
        │  Training Runtime   │      │  Redis (GPU mutex)         │
        └─────────────────────┘      └────────────────────────────┘
```

### Design Rationale

| Tier | Why Separate? |
|------|---------------|
| **Control** (Control Node) | Low-power always-on node. Stores data, runs identity/auth. Isolated from compute to prevent data exfiltration if compute is compromised. |
| **Compute** (Execution Node) | GPU workloads require isolation. Training, inference, and generation compete for 16GB VRAM — managed by Redis GPU mutex. |
| **Ops/Gateway** (Gateway Node) | Traffic routing and monitoring must be independent of compute. If Execution Node is down, you can still see why via Grafana. Gateway Node's large RAM handles OpenHands, IDEs, and media stacks without GPU pressure. |

---

## 3. MarsRL Inference-Time Loop

### 3.1 Overview

The MarsRL loop is the core quality enforcement mechanism. It implements the methodology from:
- **MarsRL** (November 2025): multi-agent process-reward signals for specialized agents
- **MiniMax Forge** (February 2026): process-level rewards, decoupled training/inference

```
User Task
    │
    ▼
[Solver — qwen3.5:9b]
  Generates initial response
    │
    ▼
[Verifier — LogicVerifier + llama-guard-3]
  Layer 1: AST Parse    → is Python syntax valid?            penalty: -0.40
  Layer 2: Coherence    → non-empty, no repetition/truncation penalty: -0.25
  Layer 3: Safety       → llama-guard-3 content screening    HARD BLOCK (score=0)
    │
    ├─── score ≥ 0.70 → PASS → response returned
    │
    └─── score < 0.70 → FAIL
              │
              ▼
         [Corrector — qwen3.5:9b]
           Receives: original task + failure reason
           Generates corrected response
              │
              ▼
         [Verifier again]
         Up to max_iter=2 total cycles
              │
              ├─── PASS → response returned (solver_score adjusted)
              └─── FAIL after max → best available response returned
```

### 3.2 Quality Scoring

| Score | Meaning | Action |
|-------|---------|--------|
| `≥ 0.90` | High quality | Tagged as `training_candidate=1.0` in Langfuse |
| `0.70–0.89` | Acceptable | Returned to user as-is |
| `< 0.60` | Unacceptable | Corrector invoked |
| `0.0` | Safety block | Hard-blocked, Corrector not invoked |

### 3.3 Solver Score Decay

`solver_score` penalizes multiple correction rounds:
- First-try pass: `solver_score = 1.0`
- After 1 correction: `solver_score = 0.7`
- After 2 corrections: `solver_score = 0.4`

This ensures that traces requiring heavy correction are weighted lower in the training dataset.

### 3.4 Non-Code Intent Paths

The Router dispatches non-code intents directly (no MarsRL loop):

| Intent | Path |
|--------|------|
| `IMAGE` / `3D` | ComfyUI → cv2 check → Moondream VLM validation |
| `IOT` | Home Assistant API (safe_mode guard) |
| `VOICE` | Voice pipeline (Qwen-TTS → RVC) |
| `RESEARCH` | Direct Qwen 3.5 9B response (no verification) |

---

## 4. Agent Architecture

### 4.1 Agent Catalog

| Agent | Class | Model | Capabilities |
|-------|-------|-------|-------------|
| Router | `SemanticRouter` | `nemotron-orchestrator:8b` | Intent classification, delegation |
| Solver / Architect | `ArchitectAgent` | `qwen3.5:9b` | Code generation, system design |
| Corrector | `CorrectorAgent` | `qwen3.5:9b` | Response repair given failure reason |
| Verifier | `VerifierAgent` | LogicVerifier + `llama-guard-3:8b` | Output validation |
| IoT Agent | `IoTAgent` | `qwen3.5:9b` | Home Assistant tool calls |
| BMO Agent | `BMOAgent` | `qwen2.5:3b` | Conversational voice (small model for VRAM efficiency) |
| Forge Agent | `ForgeAgent` | ComfyUI | Image/3D generation |
| Security Agent | `SecurityAgent` | Regex + `llama-guard-3:8b` | Threat screening |

### 4.2 Health-Aware Routing

The `NodeHealthMonitor` checks both Ollama nodes every 30 seconds (cached TTL):

```python
get_best_host_for_model(model_name):
  1. Check Execution Node VRAM headroom (via /api/ps)
  2. If Execution Node VRAM hot → route to Gateway Node
  3. If Gateway Node doesn't have the model → static fallback to Execution Node
```

This ensures large-context tasks (`qwen3.5:9b` 256K) go to the node with available VRAM.

### 4.3 ExpertiseTemplate System

Every agent is backed by a versioned **ExpertiseTemplate** stored in `swarm.expertise_templates`:

```
ExpertiseTemplate {
  id:              string          # e.g., "coding-expert"
  intent:          string          # routes: CODE, RESEARCH, etc.
  current_version: int             # auto-incremented on promotion
  system_prompt:   text            # the agent's persona prompt
  capabilities:    string[]        # allowed tools: ["file_ops", "terminal"]
  default_model:   string          # e.g., "qwen3.5:9b"
  security_level:  string          # "standard" | "elevated" | "restricted"
}
```

**Template evolution**: When `avg_score` in `expertise_template_versions` exceeds the previous version by a configurable threshold, the version is auto-promoted and the template's `current_version` is bumped. This propagates to all new agent instances automatically.

---

## 5. Data Flows

### 5.1 Request Lifecycle

```
Browser/App
  → Gateway Node Traefik (L7 routing, Authentik forward-auth)
  → Execution Node:8008 (Agent Runtime FastAPI)
    → SPIFFE SVID validation (workload identity check)
    → JWT-ACE token issuance (capability gating)
    → Security Agent (llama-guard input screen)
    → SemanticRouter (intent classification)
    → Specialist Agent (MarsRL loop or direct)
    → Langfuse trace creation (process reward injection)
    → Performance history write (swarm.performance_history)
  → Response streamed back to user
```

### 5.2 Training Data Flow

```
MarsRL execution
  → Langfuse trace (spans: solver, verifier_round_N, corrector)
  → Langfuse score (solver_score, verifier_round_N, final_quality, training_candidate)

Periodically (or on-demand):
  export_traces.py
  → SELECT traces WHERE score 'training_candidate' = 1.0
  → Export to JSONL: execution_plane/training_data/traces.jsonl
  → Write swarm.training_runs record (run_type='export')

grpo_trainer.py (profile: training)
  → QLoRA fine-tuning on JSONL (GRPO reward: correctness×0.5 + efficiency×0.3 + safety×0.2)
  → GPU mutex: Redis lock (context="training") evicts Ollama + ComfyUI
  → Output: execution_plane/training_output/grpo_<TIMESTAMP>/adapter/

convert_gguf.py
  → LoRA adapter → GGUF → ollama import
  → Write swarm.model_versions record (status='candidate')
  → A/B test auto-starts if template has an active version
```

### 5.3 Observability Data Flow

```
Agent Runtime → Prometheus metrics endpoint (:8008/metrics/)
  ↑ scraped by Prometheus (Gateway Node) every 15s

Agent Runtime → Langfuse API (Control Node:3210)
  → traces, spans, scores written per request

Docker containers → Promtail (Docker socket)
  → Loki (Gateway Node:3100) indexed by {container, service, logstream}

cAdvisor (Gateway Node) + cAdvisor Proxy (Execution Node:8081)
  → Prometheus ← container CPU/memory/network/disk
```

---

## 6. GPU Resource Management

### VRAM Budget (Execution Node — RTX 5060 Ti 16GB)

| State | Allocations | Available |
|-------|-------------|-----------|
| Inference only | Ollama (qwen3.5:9b ~8–9GB) | ~6–7GB headroom |
| Inference + ComfyUI | Ollama + ComfyUI loaded | ~2–3GB headroom |
| Training | Training runtime (~12.5GB) | ~3GB |

### GPU Mutex

A Redis-based lock (`redis.lock("gpu_request", context="training")`) prevents concurrent GPU use during training:

- Training acquires the lock → sends `EVICT` signal to Ollama and ComfyUI
- Inference requests during training: mutex is **fail-open** (returns lock immediately) if Redis is unavailable — safe for single-user usage

**Redis host**: `<control-node-ip>:6379` (Control Node)
**Password**: set in `execution_plane/.env` as `REDIS_PASSWORD`

> ⚠️ Redis port 6379 must be exposed in `control_plane/docker-compose.yml`. If the GPU mutex is not working, check this first.

---

## 7. Model Stack

| Model | Size | VRAM | Location | Role |
|-------|------|------|----------|------|
| `qwen3.5:9b` | ~5.5GB GGUF | ~9GB loaded | Both nodes | Solver, Corrector, Architect |
| `nemotron-orchestrator:8b` | ~5GB | ~8GB | Gateway Node | Router/Orchestrator |
| `llama-guard-3:8b` | ~5GB | ~8GB | Gateway Node | Safety screening |
| `qwen2.5:3b` | ~2GB | ~3GB | Execution Node | BMO conversational voice |
| Local fine-tuned models | varies | varies | Execution Node | Promoted GRPO adapters |

---

## 8. Versioning & Phase History

| Version | Phase | Key Changes |
|---------|-------|-------------|
| 1.0 (Feb 2026) | Phase 1 | Initial deployment, single-node |
| 1.2 (Feb 2026) | Phase 2 | SPIFFE enrollment, Langfuse |
| 3.0 (Feb 2026) | Phase 3 | MarsRL loop, 3-node topology, Qwen + Nemotron |
| 3.1 (Mar 2026) | Phase 4 | Gateway Node migration, Traefik consolidation, distributed monitoring |
| 3.2 (Mar 2026) | Phase 5 | JWT-ACE, ExpertiseTemplate, capability gating |
| **3.3 (Mar 2026)** | **Phase 6** | **GRPO training pipeline, A/B testing, model lifecycle, health-aware routing** |
| 3.x (planned) | Phase 7 | HA, Gateway Node SPIRE enrollment, k3s migration |

---

*See the [Phase Roadmap](../PHASE5_PLUS_ROADMAP.md) for Phase 7–9 plans · [Back to Index](../INDEX.md)*
