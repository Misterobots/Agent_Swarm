# How the Agent Swarm Works

> **Back to:** [Documentation Index](../INDEX.md)

---

## The Big Picture

When you send a message to the Hive, it doesn't go to a single AI model. It passes through a **pipeline of specialized agents** — each with a defined job — before you get a response.

Think of it like a skilled team: a dispatcher routes your request to the right specialist, the specialist does the work, a quality reviewer checks the output, and only verified results reach you.

---

## The Three-Node Architecture

The Hive runs across three physical machines, each with a distinct role:

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR BROWSER / APP                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────────────────┐
                    │  Gateway Node    │  ← Reverse Proxy & Monitoring
                    │  Traefik         │    Routes all traffic
                    │  Grafana         │    Monitoring dashboards
                    │  Prometheus      │    Metrics collection
                    └──────┬───────────┘
                           │
          ┌────────────────┼────────────────┐
          │                                 │
   ┌──────▼──────────┐            ┌─────────▼─────────┐
   │ Execution Node  │            │  Control Node      │
   │ (GPU Compute)   │            │  (Identity & Data) │
   │                 │            │                    │
   │  Agent Runtime  │            │  SPIRE (Identity)  │
   │  Ollama GPU     │            │  Langfuse (Traces) │
   │  ComfyUI        │            │  PostgreSQL        │
   │  Training       │            │  MinIO (Storage)   │
   └─────────────────┘            └────────────────────┘
```

- **Gateway Node**: Your entry point. Routes all traffic, hosts monitoring.
- **Execution Node**: Runs the AI models and agent logic (GPU compute).
- **Control Node**: Stores data, manages identity, tracks all AI interactions.

---

## The MarsRL Quality Loop

The most important concept in the Hive is the **MarsRL loop** — the mechanism that ensures the AI's output is actually correct before you see it.

```
Your Request
     │
     ▼
[ Router / Nemotron-8B ]
  Classifies your intent: CODE, RESEARCH, IMAGE, IOT, etc.
     │
     ▼ (for coding tasks)
[ Solver / Qwen 3.5 9B ]
  Generates the initial response
     │
     ▼
[ Verifier / LogicVerifier ]
  Checks 3 things:
  1. Syntax: Is the code valid Python?
  2. Coherence: Is it complete and non-repetitive?
  3. Safety: llama-guard-3:8b content check (hard block)
     │
     ├──── PASS (score ≥ 0.60) ────► Response sent to you
     │
     └──── FAIL ──────────────────► [ Corrector / Qwen 3.5 9B ]
                                      Fixes the identified problem
                                           │
                                           ▼
                                      [ Verifier again ]
                                      Up to 2 correction cycles
```

**Key insight**: Bad code never reaches you. The loop fixes it or the Corrector runs until the score passes. If it can't be fixed, you get a clear error rather than broken output.

### Scoring

Every response gets a **quality score from 0.0 to 1.0**:
- `≥ 0.80` → Tagged as a training candidate (used to improve future models)
- `0.60–0.79` → Acceptable
- `< 0.60` → Triggers correction cycle

---

## The Agents

Each agent is a specialized AI persona with its own model, tools, and security capabilities:

| Agent | Model | Role |
|-------|-------|------|
| **Router** | Nemotron-Orchestrator 8B | Classifies intent, delegates to specialist |
| **Solver / Corrector** | Qwen 3.5 9B (256K ctx) | Primary code generation and repair |
| **Verifier** | LogicVerifier + llama-guard-3 | Code validation, safety screening |
| **Architect** | Qwen 3.5 9B | System design, technical planning |
| **IoT Agent** | Qwen 3.5 9B | Home Assistant integration |
| **BMO Voice** | Qwen 2.5 3B + RVC + Qwen-TTS | Voice interaction pipeline |
| **Forge Agent** | ComfyUI | Image and 3D generation |

### ExpertiseTemplates

Each agent follows an **ExpertiseTemplate** — a versioned configuration that defines:
- The system prompt and persona
- Which tools it can call (capability gating)
- Which AI model it uses
- A performance history (average quality scores)

Templates evolve automatically: when quality scores improve, the template is promoted to a new version. This is how the Hive gets better over time without manual tuning.

---

## Security at Every Step

Every request passes through multiple security checkpoints before a response is returned:

```
L7 — Identity     SPIFFE SVID validates the agent-runtime workload
L4 — Input        llama-guard-3:8b screens for jailbreaks / harmful intent
L5 — Routing      Nemotron classifies and delegates (no cross-domain execution)
L4 — Output       MarsRL LogicVerifier (AST + coherence + llama-guard)
L7 — Capability   JWT-ACE token enforces which tools the agent can call
L6 — Governance   Langfuse trace records the full interaction for audit
```

A **JWT-ACE token** (ephemeral — expires after the request) is issued for each agent invocation. This token specifies exactly which tools the agent is permitted to use. An agent cannot call a tool outside its approved capability set, even if the model tries to.

---

## How Your Conversations Improve the System

Every successful interaction (score ≥ 0.80) is a **training candidate**:

1. The Langfuse trace records the full Solver → Verifier → Corrector interaction
2. Periodically, `export_traces.py` exports high-quality traces to a JSONL dataset
3. `grpo_trainer.py` fine-tunes the Solver model using QLoRA (12.5GB VRAM)
4. The fine-tuned model is converted to GGUF and loaded into Ollama
5. An **A/B test** runs automatically: new model vs. previous baseline
6. If the new model scores >5% better (p < 0.05, min 100 invocations), it auto-promotes

You can watch this pipeline live in the **Grafana Training Pipeline dashboard**.

---

## Observability

Every AI call generates a **Langfuse trace** you can inspect at `http://<control-node-ip>:3000`:

- See exactly which model ran, what it was given, and what it returned
- See the verifier score at each step
- See whether the Corrector was invoked and why
- Export the trace timeline for debugging

The **Grafana Agent Activity dashboard** (`http://<gateway-node-ip>:3001`) shows:
- Live agent states (Idle / Working / Error)
- Conversation volume and quality scores over time
- Corrector invocation rate
- Training pipeline status

---

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|-----------|
| `agents/router.py` | Implementation | MarsRL loop, Solver/Verifier/Corrector pipeline |
| `agents/main.py` | Implementation | FastAPI entry point, JWT-ACE middleware |
| `agents/mars_loop.py` | Implementation | MarsRL scoring and iteration logic |
| `agents/governance.py` | Implementation | Governance checks and Langfuse integration |
| `agents/metrics.py` | Implementation | Prometheus metrics export |
| `agents/security_scanner.py` | Implementation | llama-guard safety screening |
| `training/grpo_trainer.py` | Implementation | GRPO fine-tuning pipeline |
| `training/export_traces.py` | Implementation | Langfuse trace export for training |
| [MarsRL paper concept](https://arxiv.org/abs/2501.14492) | Research | Inference-time verification loop design |
| [SPIFFE/SPIRE](https://spiffe.io/) | Standard | Zero-trust workload identity |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|---------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-10 | AI-Copilot | Initial framework document created |

</details>

---

## Maintenance & Update Guide

### Updating Agent Table

When agents are added or models are swapped, update the agents table in the "The Agents" section. Cross-reference `agents/router.py` for the current model assignments.

### Updating Security Layer Diagram

The 6-layer security stack (`L4–L7`) is defined inline. When new security layers are added (e.g., rate limiting, WAF), add a new `L` entry to the ASCII diagram.

### Updating Training Pipeline Description

The training flow is described in "How Your Conversations Improve the System." When training parameters or thresholds change, update:
- The score threshold (currently `≥ 0.80`)
- The A/B test criteria (currently `>5%` improvement, `p < 0.05`, `min 100 invocations`)

---

## Functionality Testing

### Manual Verification

1. **MarsRL loop**: Send a coding request → verify the trace in Langfuse shows Solver → Verifier → (optional Corrector) stages.
2. **Capability gating**: Verify in the Agent Trace that a JWT-ACE token is issued with specific capabilities.
3. **Safety screening**: Send a borderline request → verify llama-guard blocks it with a SAFE/UNSAFE verdict in the trace.
4. **Quality scoring**: Check Grafana Agent Activity dashboard for live quality score distribution.

---

*For security details, see [Admin: Security](../admin/security.md) · [Back to Index](../INDEX.md)*
