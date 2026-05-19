# MarsRL Hive Redesign: Implementation Walkthrough

_Date: 2026-03-12 | Version: 3.1 (Qwen 3.5 9B Standard)_

## Overview

This walkthrough documents the complete redesign of the Home AI Lab "Agentic Hive" to implement the **MarsRL inference-time loop** — a Solver → Verifier → Corrector multi-agent pipeline inspired by the MarsRL framework (Nov 2025) and the MiniMax Forge agent-native RL methodology.

The hive now runs on a **three-node distributed topology** with dedicated hardware for each inference role, standardized on `qwen3.5:9b` for all coding tasks.

---

## Model Stack

| Role                         | Model                      | Node      | Hardware         | Notes                         |
| ---------------------------- | -------------------------- | --------- | ---------------- | ----------------------------- |
| **Solver** (code generation) | `qwen3.5:9b`               | Dell Turing | RTX 3070 Ti 8GB  | Primary solver; low VRAM      |
| **Corrector** (fix failures) | `qwen3.5:9b`               | Dell Turing | RTX 3070 Ti 8GB  | Primary corrector             |
| **Router / Orchestrator**    | `nemotron-orchestrator:8b` | Dell Turing | RTX 3070 Ti 8GB  | Intent classification         |
| **Safety Verifier**          | `llama-guard-3:8b`         | Dell Turing | RTX 3070 Ti 8GB  | Existing security layer       |

### Why These Models?

| Candidate                    | Size                | Local?               | Decision                          |
| ---------------------------- | ------------------- | -------------------- | --------------------------------- |
| Qwen3.5 397B                 | 397B                | ❌ Too large         | Use distilled 9B instead          |
| **Qwen3.5 9B**               | 9B dense            | ✅ ~5.5GB VRAM       | **Selected: Solver/Corrector**    |
| **Nemotron-Orchestrator**    | 8B dense            | ✅ ~5.5GB VRAM       | **Selected: Router/Orchestrator** |

---

## Infrastructure: 3-Node Topology

> **Visual diagram**: Open [`docs/architecture/hive_topology_v3.drawio`](architecture/hive_topology_v3.drawio) in VS Code with the **Draw.io Integration** extension (`hediet.vscode-drawio`) for the full interactive diagram.

```
┌─────────────────────────────────┐
│  Control Plane — Dell Hopper │
│  IP: 192.168.2.102              │
│  ┌───────────────────────────┐  │
│  │ SPIRE Server :8081        │  │
│  │ PostgreSQL :5432          │  │
│  │ Langfuse :3000            │  │
│  │ ClickHouse, Redis, MinIO  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Primary Inference — Lovelace  │
│  OLLAMA_HOST=localhost:11434    │
│  ┌───────────────────────────┐  │
│  │ RTX 5060 Ti (16GB)        │  │
│  │  qwen3.5:9b               │  │
│  │  (Secondary Solver)       │  │
│  │                           │  │
│  │ Docker Execution Plane:   │  │
│  │  agent-runtime :8000      │  │
│  │  agent-ui :8501           │  │
│  │  openhands :3000          │  │
│  │  comfyui :8188            │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘

┌──────────────────────────────────────┐
│  Secondary Inference — Dell Turing     │
│  SECONDARY_OLLAMA_HOST=192.168.2.103 │
│  ┌────────────────────────────────┐  │
│  │ RTX 3070 Ti (8GB)             │  │
│  │  qwen3.5:9b (Primary Solver)  │  │
│  │  nemotron-orchestrator (Router)│  │
│  │  llama-guard-3:8b (Safety)     │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## MarsRL Loop Architecture

Every `CODE` intent task flows through the full loop:

```
User Request
    │
    ▼
Nemotron-Orchestrator (Dell Turing) ── classifies intent ──▶ IMAGE/3D/IoT routes (unchanged)
    │
    │ CODE intent
    ▼
Qwen 3.5 9B [SOLVER] (Dell Turing / Lovelace)
    │ response
    ▼
LogicVerifier [VERIFIER]
    ├── Layer 1: Python AST parse
    ├── Layer 2: Coherence (length, repetition, truncation)
    └── Layer 3: llama-guard-3 safety check (Dell Turing)
    │
    ├── PASS ──▶ Langfuse score(solver_score=1.0) ──▶ User
    │
    └── FAIL ──▶ Qwen 3.5 9B [CORRECTOR] (Dell Turing / Lovelace)
                    │ corrected response
                    ▼
                LogicVerifier (2nd pass)
                    │
                    └── PASS/FAIL ──▶ Langfuse score ──▶ User
```

### Process Rewards (Forge-Inspired)

Each step injects a score into Langfuse:

| Score Name         | Value           | Meaning                        |
| ------------------ | --------------- | ------------------------------ |
| `verifier_round_1` | 0.0–1.0         | First-pass verifier score      |
| `verifier_round_2` | 0.0–1.0         | After corrector (if invoked)   |
| `solver_score`     | 1.0 / 0.7 / 0.0 | Did solver pass on first try?  |
| `final_quality`    | 0.0–1.0         | Final verifier score delivered |

These scores build a **training dataset** for future fine-tuning.

---

## Files Changed

### New Files

| File                                                        | Purpose                                 |
| ----------------------------------------------------------- | --------------------------------------- |
| [`agents/mars_loop.py`](../agents/mars_loop.py)             | `MarsRLLoop` class + `mars_loop_stream` |
| [`agents/verifier_agent.py`](../agents/verifier_agent.py)   | 3-layer `LogicVerifier`                 |
| [`agents/corrector_agent.py`](../agents/corrector_agent.py) | `CorrectorAgent` (correction prompt)    |
| [`tests/test_mars_loop.py`](../tests/test_mars_loop.py)     | mock-based pytest cases                 |

### Modified Files

| File                                                              | Change                                                                                 |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [`agents/architect_agent.py`](../agents/architect_agent.py)       | Standardized on `qwen3.5:9b`                                                           |
| [`agents/semantic_router.py`](../agents/semantic_router.py)       | `nemotron-orchestrator:8b` via `SECONDARY_OLLAMA_HOST`                                 |
| [`agents/teams.py`](../agents/teams.py)                           | Orchestrator → Nemotron on Turing; removed Devstral accessors                            |
| [`agents/router.py`](../agents/router.py)                         | CODE route → MarsRL loop; removed Devstral references                                  |
| [`execution_plane/.env.example`](../execution_plane/.env.example) | Added `SOLVER_MODEL`, `SECONDARY_OLLAMA_HOST`, `ROUTER_MODEL`, `ORCHESTRATOR_MODEL`    |

---

## Deployment Steps

### 5060ti PC / Turing (Inference Nodes)

```bash
# Pull Solver model
ollama pull qwen3.5:9b
ollama pull nemotron-orchestrator:8b
ollama pull llama-guard-3:8b

# Copy new env vars to .env
echo 'SOLVER_MODEL=qwen3.5:9b' >> execution_plane/.env
echo 'SECONDARY_OLLAMA_HOST=http://<turing-ip>:11434' >> execution_plane/.env
echo 'ROUTER_MODEL=nemotron-orchestrator:8b' >> execution_plane/.env
echo 'ORCHESTRATOR_MODEL=nemotron-orchestrator:8b' >> execution_plane/.env

# Restart agents
docker compose -f execution_plane/docker-compose.yml up -d agent-runtime
```

---

## Test Suite

```bash
# Run all MarsRL tests (no Ollama needed — uses mocks)
pytest tests/test_mars_loop.py -v
```

---

## Observability

After deploying, verify in **Langfuse** (http://192.168.2.102:3000):

1. Navigate to **Traces** → filter by `mars_loop`
2. Each trace should show spans: `solver` → `verifier_round_1` → (optionally `corrector` → `verifier_round_2`)
3. Scores panel should show `solver_score` and `final_quality` values

---

_Version 3.1 | 2026-03-12 | Qwen 3.5 9B Loop + Dell Turing Topology_

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `agents/mars_loop.py` | Implementation | MarsRL Solver → Verifier → Corrector pipeline |
| `agents/config.py` | Configuration | Model routing to qwen3.5:9b |
| `control_plane/docker-compose.yml` | Infrastructure | Langfuse for trace observability |
| `turing_gateway/docker-compose.yml` | Infrastructure | Gateway and Traefik routing |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-12 | AI-Copilot | v3.1 — MarsRL Hive redesign walkthrough |

</details>

---

## Maintenance & Update Guide

- Update when the primary model changes from Qwen 3.5 9B.
- Update when node topology or Langfuse trace names change.

---

## Functionality Testing

| Claim | How to Verify |
|-------|---------------|
| MarsRL pipeline works | Send complex prompt → check Langfuse for `mars_loop` trace with 3 spans |
| Qwen 3.5 9B active | `curl http://<ollama>:11434/api/tags` → confirm `qwen3.5:9b` |
