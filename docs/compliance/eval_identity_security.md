# MAESTRO Evaluation: Identity & Trust

**Component**: Agent Registry, RBAC & SPIFFE/SPIRE Workload Identity
**Date**: 2026-02-22
**Status**: ✅ Substantially Compliant — R730 SPIRE enrollment pending

## 1. Component Description

The "Passport Control" of the Hive. It defines WHO agents are and WHAT they can do.

## 2. MAESTRO Layer Alignment

- **Layer 7 (Identity & Trust)**: Authentication, RBAC, and Reputation.

## 3. Compliance Evidence

### L7: Immutable Identity

- **Requirement**: "Every agent must have a verifiable ID."
- **Implementation**:
  - `AgentCard` class enforces `name`, `role`, `id`, and `capabilities`.
  - Registry is a global singleton loaded at startup (`agents/registry.py`).
  - Dynamically created/spawned agents are not supported (reducing risk).
- **Verification**: `agents/registry.py` architecture.

### L7: Role-Based Access Control (RBAC)

- **Requirement**: "Agents operate within specific capability boundaries."
- **Implementation**:
  - The `SecurityAgent` calls `validate_permission(agent, capability)`.
  - Example: `Art Director` has `image_gen.generate` but _not_ `file_ops.write`.
  - Example: `Architect` has `file_ops.write`.
- **Verification**: `agents/security_agent.py` permission check.

### L7: API Authentication (Identity Enforcement)

- **Requirement**: "External requests must have authenticated origin."
- **Implementation**:
  - `agent-runtime` checks `X-Swarm-Source` header against `VALID_API_KEYS`.
  - Requests without valid keys are rejected (HTTP 401).
  - Identity (`user` field) is overwritten by the system based on the key, preventing spoofing.
- **Verification**: `agents/main.py` middleware logic.

### L7: Workload Identity (SPIFFE)

> **Interactive diagram**: Open [`docs/architecture/spiffe_flow.drawio`](../architecture/spiffe_flow.drawio) for the full identity flow.
> Export as SVG → save as `docs/assets/spiffe_flow.drawio.svg`.

![SPIFFE/SPIRE Identity Flow](../assets/spiffe_flow.drawio.svg)

- **Requirement**: "Workloads must have cryptographically verifiable identity independent of the network."
- **Implementation**:
  - **SPIRE Server** (Dell Wyse 5070): Issues short-lived X.509 SVIDs to attested workloads.
  - **SPIRE Agent** (Hive PC): ✅ Enrolled — validates Docker labels + image SHA before delivering SVIDs.
  - **SPIRE Agent** (Dell R730): ⚠️ Pending — must be enrolled after hardware commissioning.
  - **py-spiffe**: Agents fetch SVIDs from `unix:///var/run/spire/agent.sock`, enabling mTLS.
  - **SVIDs**: Short-lived (1 hour), auto-rotated. Trust domain: `spiffe://home-lab`.
- **Verification**: [identity_verification_2026-02-08.txt](../evidence/identity_verification_2026-02-08.txt)

## 4. Residual Risks

- **Identity Spoofing (Internal)**: Since the Registry is in-memory Python, a compromised `main.py` could overwrite it. This is mitigated by L5 Container Isolation (immutable code volume in production), though currently we mount code for dev.
