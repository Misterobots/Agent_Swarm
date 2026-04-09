---
marp: true
theme: home-ai-lab
author: Home AI Lab
title: Agentic Hive Architecture v3.1
paginate: true
style: |
  section.lead {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
---

<!-- _class: lead -->

# Agentic Hive

## Qwen 3.5 Powered Multi-Agent Orchestration

**Version 3.1** | 2026-03-12 | **Restricted**: L3 Admin Eyes Only

---

# 1. Executive Summary

The **Agentic Hive** is a decentralized Swarm Intelligence system where role-specialized agents collaborate to solve complex tasks, now standardized on **Qwen 3.5 9B**.

- **Non-Monolithic**: Each inference role runs on its optimal hardware.
- **MarsRL Loop**: Solver → Verifier → Corrector pipeline for all coding tasks.
- **Distributed**: 3 dedicated nodes with hardware-matched model assignment.

---

# 2. Hardware Topology (3 Nodes)

### Control Plane — Control Node (<control-node-ip>)

- SPIRE Server, PostgreSQL, Langfuse, ClickHouse, Redis, MinIO

### Primary Inference — Execution Node (<execution-node-ip>)

- **RTX 5060 Ti (16GB)**: `qwen3.5:9b` — Secondary Solver
- Docker Execution Plane: agent-runtime, ComfyUI

### Secondary Inference — **Gateway Node** (<gateway-node-ip>)

- **RTX 3070 Ti (8GB)**: `nemotron-orchestrator:8b` — Router & Orchestrator
- **RTX 3070 Ti (8GB)**: `qwen3.5:9b` — Primary Solver
- **RTX 3070 Ti (8GB)**: `llama-guard-3:8b` — Safety Verifier

---

# 3. MarsRL Inference Loop

**Every CODE task flows through 3 agents before reaching the user.**

```
User ──▶ Nemotron [Route] ──▶ Qwen 3.5 [Solve] ──▶ LogicVerifier
                                                           │
                                               ┌───────────┴───────────┐
                                            PASS ✅               FAIL ❌
                                               │                       │
                                            ◀─User           Qwen 3.5 [Correct]
                                                                        │
                                                               LogicVerifier (2nd)
                                                                        │
                                                                    ◀─User
```

---

# 4. Model Selection

| Role                      | Model                      | Node      | Why                                                      |
| ------------------------- | -------------------------- | --------- | -------------------------------------------------------- |
| **Solver / Corrector**    | `qwen3.5:9b`               | Gateway Node / Execution Node | High efficiency coding model; SOTA performance at 9B.    |
| **Router / Orchestrator** | `nemotron-orchestrator:8b` | Gateway Node | Purpose-built by NVIDIA for multi-agent coordination.    |
| **Safety Verifier**       | `llama-guard-3:8b`         | Gateway Node | Dedicated content safety model.                          |

---

<!-- _class: lead -->

# End of Briefing

**Project Status**: Production (v3.1.0) | **Date**: 2026-03-12

_Next milestone: SPIRE enrollment completion on Gateway Node_
