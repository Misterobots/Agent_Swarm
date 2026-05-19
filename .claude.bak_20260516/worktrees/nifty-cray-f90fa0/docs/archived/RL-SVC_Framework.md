# Engineering Framework: MarsRL Inference Execution & MAESTRO-SPIFFE/SPIRE Zero-Trust Identity

**Authors**: Home AI Lab
**Date**: February 2026
**Status**: Proof of Concept (PoC) / Implementation Reference

## 1. Abstract

This document details the architectural implementation of two advanced systems within the Home AI Lab ecosystem:

1.  **MarsRL Inference-Time Loop**: A deterministic, multi-agent reinforcement learning pipeline applied at inference time (Solver → Verifier → Corrector), inspired by DeepMind's MarsRL (Nov 2025) and MiniMax Forge.
2.  **MAESTRO-SPIFFE/SPIRE**: A cryptographic zero-trust workload identity framework orchestrating secure, attested agent-to-agent communication across the swarm.

These implementations serve as a scalable proof of concept for resilient, self-correcting AI swarms operating under stringent security models.

---

## 2. MarsRL Inference-Time Execution Loop

### 2.1 Core Architectural Concept

The MarsRL implementation shifts the paradigm from purely prompt-based execution to an inference-time verification and correction loop. It decouples the generation (Solver) from the validation (Verifier) and refinement (Corrector), allowing for localized, process-level reward signals.

### 2.2 Component Breakdown

The pipeline is orchestrated primarily within `agents/mars_loop.py` and consists of three distinct agent roles.

#### 2.2.1 The Solver (`architect_agent.py`)

- **Model**: `qwen3.5:9b`.
- **Role**: Primary generator for complex coding and multi-file software engineering tasks.
- **Offloading**: Automatically routed to the Dell Turing (8GB VRAM) to prevent local thrashing.
- **Execution**: Generates the initial `RunResponse` based on the user's task and injected memory rules.

#### 2.2.2 The Verifier (`verifier_agent.py`)

The Verifier acts as a multi-layer deterministic gateway, grading the Solver's output. It assigns a continuous score (0.0 - 1.0) based on three strict criteria:

1.  **Code Structure (Layer 1)**: Performs AST (Abstract Syntax Tree) parsing on any generated Python code. Failure results in a `-0.40` penalty.
2.  **Coherence Heuristics (Layer 2)**: Checks for truncation, repetitive loops (e.g., 5+ repeated lines), and suspiciously short outputs. Failure yields a `-0.45` penalty.
3.  **Active Safety Guard (Layer 3)**: Integrates with the `Security Agent` (running `llama-guard-3:8b`). Any "UNSAFE" detection results in an immediate hard block (`score = 0.0`).

_Threshold_: The response must achieve a score $\geq 0.60$ to pass.

#### 2.2.3 The Corrector (`corrector_agent.py`)

- **Model**: `qwen3.5:9b` (Low temperature: `0.05`).
- **Role**: Targeted refinement.
- **Offloading**: Same as solver, executes on Turing side to maintain cache consistency.
- **Execution**: If the Verifier fails the response, the Corrector receives the original task, the failed response, and the exact failure reason (e.g., "SyntaxError on line 42"). It is instructed to perform _surgical_ fixes without altering working components.

### 2.3 Process-Level Rewards and Langfuse Tracing

A critical aspect of the MarsRL PoC is the generation of synthetic training data via process rewards.

- **Tracing**: Every step of the loop (Solver attempt, Verifier grading, Corrector fix) is traced via the Langfuse SDK.
- **Reward Injection**: The Verifier's score (`vr.score`) and reasoning are injected synchronously into the Langfuse trace (`_langfuse.score()`).
- **Future Application (Option C)**: This telemetry builds an ongoing dataset mapping specific failure modes to successful corrections, enabling future model fine-tuning (DPO/ORPO) directly from the swarm's own inference experiences.

### 2.4 Streaming, Stability & Heartbeats

The loop operates asynchronously relative to the UI, utilizing `mars_loop_stream` to yield real-time JSON status updates (Iterations, Solver Score, Corrections). 

To ensure stability during long inference-time compute:
- **Streaming Heartbeats**: Injects a zero-width space (`\u200B`) into the stream every 30 seconds to prevent Traefik/App-level TCP timeouts.
- **Extended Timeouts**: Phidata HTTP client timeouts are extended to **300s** to accommodate the heavy TTFT (Time-To-First-Token) and processing of massive contexts (up to 256k tokens).

### 2.5 Inference-Time Compute: Extended Research and Thinking

The most significant capability unlocked by the MarsRL loop is the simulation of **extended research and thinking time** (often referred to as "inference-time compute"). Unlike standard naive prompting, where a model generates a single pass of tokens and stops, the MarsRL framework naturally forces the swarm to "think longer" about complex problems.

- **Iterative Deepening**: If the Solver's initial approach is flawed or incomplete, the Verifier halts the output. The Corrector is then invoked, providing an opportunity for the swarm to re-evaluate its logic, effectively spending more compute to arrive at the correct answer.
- **Contextual Self-Correction**: This mimics human-like extended thinking. The swarm takes the time to read its own errors, parse syntax trees, and refine its approach before ever presenting a final response to the user.
- **Transparent Deliberation**: The streaming UI exposes this "thinking time" to the user, moving away from a black-box response model to a deliberate, auditable reasoning pipeline where the user can actively see the swarm catching and fixing its own mistakes.

---

## 3. MAESTRO-SPIFFE/SPIRE Identity Framework

### 3.1 Zero-Trust Workload Identity

The legacy Home AI Lab relied on static API keys (`SWARM_API_KEY`) for internal authentication. The MAESTRO-SPIFFE (Secure Production Identity Framework for Everyone) implementation replaces this with ephemeral, cryptographically verifiable identities.

### 3.2 Architectural Topology

The SPIFFE implementation utilizes a Server-Agent architecture deployed via Docker Compose.

#### 3.2.1 SPIRE Server (`control_plane/docker-compose.yml`)

- **Role**: The central Certificate Authority (CA) and registration authority for the Trust Domain.
- **Configuration**: Maintains the node and workload registration entries. Exposes port `8081` for agent communication over the internal Docker network (`swarm_net`).

#### 3.2.2 SPIRE Agent (`execution_plane/docker-compose.yml`)

- **Role**: Deployed as a daemon-set equivalent within the execution plane.
- **Attestation**: Joins the server using a configured join token.
- **Workload API**: Exposes a Unix Domain Socket (`/var/run/spire/agent.sock`) to workloads running on the same host/node.

#### 3.2.3 Agent Runtime Environment

The primary python runtime (`agent_runtime`) mounts the SPIRE Agent socket `spire_socket:/var/run/spire:ro`.

- **Environment Variable**: `SPIFFE_ENDPOINT_SOCKET=unix:///var/run/spire/agent.sock` directs the `py-spiffe` library to the local Workload API.
- **Labeling**: The container is labeled with its intended SPIFFE ID for attestation (`spiffe.io/spiffe-id=spiffe://home-ai-lab/agent/runtime`).

### 3.3 Cryptographic Implementation (`agents/security/spiffe_auth.py`)

The `SpiffeAuth` class encapsulates the complexity of the Workload API.

1.  **Identity Fetching (X.509 SVID)**: The runtime connects to the socket and fetches its X.509 SVID (`fetch_x509_svid()`). This provides the certificate chain and private key needed for potential mTLS connections.
2.  **Service-to-Service Auth (JWT-SVID)**: For API-level requests, the agent generates a JWT-SVID scoped to a specific target audience (e.g., `spiffe://home-ai-lab/agent/router`).
3.  **Automatic Rotation**: The SPIRE infrastructure handles the automatic rotation of these short-lived certificates and tokens without application-level intervention.
4.  **Verification**: Incoming JWTs are verified against the SPIRE trust bundle (`verify_jwt_token`), ensuring the caller is cryptographically authenticated and extracting their specific `spiffe_id`.

### 3.4 Verification Tooling

A standalone diagnostic script, `agents/verify_spiffe.py`, provides a health check for the integration. It connects to the Workload API, authenticates, fetches the X.509 SVID (printing the Trust Domain and SPIFFE ID), and exercises JWT generation.

---

## 4. Synthesis and Future Scaling

The combination of MarsRL and MAESTRO-SPIFFE lays the foundation for "Phase 3" scaling:

1.  **Resilience**: The MarsRL loop ensures that as the swarm scales and takes on more complex automation tasks across the home, it can self-correct logic and syntax errors autonomously.
2.  **Security boundaries**: As specialized agents (like the IoT Controller or DevOps IDE) execute high-privilege actions, SPIFFE authentication ensures that only cryptographically attested components can trigger them. A compromised container cannot simply extract a static API key to escalate privileges.
3.  **Data Flywheel**: The Langfuse process rewards linked to specific SPIFFE identities allow for nuanced auditing and targeted fine-tuning of the models running within the swarm.
