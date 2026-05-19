# Agentic Hive: Technical Architecture & Design Specification

## 1. Executive Summary

The **Agentic Hive** is a decentralized, multi-agent orchestration system designed for autonomy, creativity, and real-world interaction. Unlike monolithic LLM applications, the Hive employs a **Swarm Intelligence** architecture where specialized agents — bound by strict identity, security, and reinforcement-learning optimization protocols — collaborate to solve complex tasks.

**Current Version:** 3.1 (Qwen 3.5 Standarization)
**Core Innovation:** The Hive now uses an inference-time **MarsRL loop** (Solver → Verifier → Corrector) for all coding tasks, with Langfuse process-reward scoring at each step. This implements the methodology published in MarsRL (Nov 2025) and MiniMax Forge (Feb 2026) using `qwen3.5:9b`.

---

## 2. Hardware & Network Topology

> [!NOTE]
> The system operates on a **three-node hybrid** architecture across dedicated hardware.

![Hive 3-Node Topology — MarsRL Architecture](assets/hive_topology_v3_drawio.svg)

### 2.1 Node Specifications

| Node                                    | Role                          | Hardware                   | Key Services                                          |
| --------------------------------------- | ----------------------------- | -------------------------- | ----------------------------------------------------- |
| **Dell Hopper** (192.168.2.102)      | Control Plane                 | x86 low-power              | SPIRE, PostgreSQL, Langfuse, ClickHouse, Redis, MinIO |
| **Lovelace** (192.168.2.101)           | Heavy Inference + App Runtime | RTX 5060 Ti 16GB, 32GB RAM | Docker Execution Plane, ComfyUI, qwen3.5:9b           |
| **Dell PowerEdge Turing** (192.168.2.103) | Routing + Offload Inference   | RTX 3070 Ti 8GB            | qwen3.5:9b, nemotron-orchestrator, llama-guard-3:8b   |

---

## 3. MarsRL Inference-Time Loop

### 3.1 Design Philosophy

The Hive rejects the "One Model Fits All" approach. It uses **role-specialized inference**:

- **Nemotron-Orchestrator**: Fast multi-agent routing and coordination.
- **Qwen 3.5 9B**: Primary coding generation and autonomous engineering (256K context).
- **llama-guard-3:8b**: Safety screening and content moderation.
- **LogicVerifier**: AST-level code correctness + coherence heuristics.

### 3.2 MarsRL Loop Flow

![MarsRL Sequence — Solver→Verifier→Corrector](assets/marsrl_sequence._drawio.svg)

### 3.3 Verifier Layers

| Layer         | Check                                   | Failure Penalty | Hard Block? |
| ------------- | --------------------------------------- | --------------- | ----------- |
| 1 — AST Parse | Python syntax valid                     | -0.40 score     | No          |
| 2 — Coherence | Non-empty, no repetition, no truncation | -0.25 score     | No          |
| 3 — Safety    | llama-guard-3:8b content check          | score = 0.0     | **Yes**     |

Pass threshold: score ≥ 0.60

---

## 4. Agent Methodology

### 4.1 Specialized Agent Breakdown

#### A. The Solver / Corrector (Qwen 3.5 9B)

- **Model**: `qwen3.5:9b`
- **Role**: Primary MarsRL Solver for first-pass code generation; Corrector for fixing failed outputs.
- **Context**: 256K tokens.

#### B. The Router / Orchestrator (Nemotron-Orchestrator-8B)

- **Model**: `nemotron-orchestrator:8b`
- **Role**: Intent classification, multi-agent coordination.

#### C. The Safety Verifier (llama-guard-3:8b)

- **Role**: Content moderation, jailbreak detection, safety hard-blocking.

---

## 5. Diagnostic Tooling

### 7.1 Text Generation WebUI (Token Inspector)

**Profile**: `diagnostic`

- Investigating why Corrector produces a specific fix.
- Tuning system prompts.

---

**Version**: 3.1.0
**Status**: Production
**Date**: 2026-03-12
