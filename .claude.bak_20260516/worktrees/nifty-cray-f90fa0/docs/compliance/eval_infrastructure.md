# MAESTRO Evaluation: Infrastructure & Deployment

**Component**: Docker Swarm (Execution & Control Planes)
**Date**: 2026-02-02
**Status**: ✅ COMPLIANT

## 1. Component Description

The physical and virtual foundation of the Agentic Hive. It manages container orchestration, hardware resource allocation (GPU/NPU), and network isolation.

## 2. MAESTRO Layer Alignment

- **Layer 1 (Physical)**: Hardware abstraction and resource mapping.
- **Layer 5 (Deployment)**: Container security, isolation, and immutability.

## 3. Compliance Evidence

### L1: Hardware sovereignty

- **Requirement**: "AI Compute must operate on local silicon; no black-box cloud."
- **Implementation**:
  - `ollama` service maps local GPU via `nvidia` runtime driver.
  - No external API dependencies for core inference.
- **Verification**: Verified in `docker-compose.yml` (`devices: driver: nvidia`).

### L5: Least Privilege

- **Requirement**: "Processes must run with minimum necessary permissions."
- **Implementation**:
  - `agent-runtime` uses custom `Dockerfile` with non-root user `app` (UID/GID 1000).
  - `Dockerfile` includes `USER app` instruction.
- **Verification**: `execution_plane/Dockerfile` audit.

### L5: Network Isolation

- **Requirement**: "Sensitive traffic must be segmented."
- **Implementation**:
  - `execution_net`: Isolated bridge for Agents <-> Ollama.
  - `swarm_net`: Isolated bridge for Control Plane services.
- **Verification**: `docker inspect agent-runtime` confirms `execution_net` bridge.
- **Evidence (2026-02-08)**: [infrastructure_status_2026-02-08.txt](../evidence/infrastructure_status_2026-02-08.txt)

### L1/L5: Smart Host Routing
- **Requirement**: "Large models must not cause system-level instability or thrashing."
- **Implementation**:
  - `gpu_queue.py` implements a 10GB+ VRAM threshold.
  - Heavy models (Expert) stay on **Execution Node (16GB)**.
  - Light models (Primary Agents) offload to **Gateway Node (8GB)**.
- **Verification**: Verified via `agent-runtime` routing logs on March 12.

## 4. Residual Risks

- **VRAM Overdraw**: Host-level apps (AnythingLLM) occupy ~9GB of Execution Node VRAM. Loading the 15GB Expert Solver simultaneously will still result in CPU swapping.
- **Docker Socket**: `openhands` requires `/var/run/docker.sock` mount. This is an accepted operational risk for the Sandbox feature.
