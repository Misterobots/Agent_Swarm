# Admin: Security Reference

> **Back to:** [Documentation Index](../INDEX.md)
> **See also:** [Design Framework](design_framework.md) · [MAESTRO Compliance Status](../compliance/maestro_compliance_status.md)

## Canonical Security Standards

Use the following canonical standards for implementation and audit decisions:

- [Identity and Token Trust Standard](../security/identity_token_trust_standard.md)
- [API Authentication and Claims Contract](../security/api_authentication_contract.md)
- [API Contract Validation Examples](../security/api_contract_validation_examples.md)
- [Key Lifecycle and Rotation Runbook](../security/key_lifecycle_rotation_runbook.md)
- [Key Compromise Incident Runbook](../security/key_compromise_incident_runbook.md)
- [Key Compromise Incident Checklist](../security/key_compromise_incident_checklist.md)
- [Multi-user Identity Scoping Standard](../security/multi_user_identity_scoping_standard.md)
- [Hook Security and Execution Policy](../security/hook_security_execution_policy.md)

**Version**: 3.3 · **Audit Status**: Production (Phase 6) · **Last Updated**: 2026-03-23

---

## 1. Security Architecture Overview

The Agentic Hive implements a **defense-in-depth** security model aligned with the **MAESTRO framework** (Machine Learning-Aware Security Threat and Risk Operations). Every request passes through multiple independent security layers before execution and before a response is returned.

```
Request Ingress
    │
    ▼  [L7] WORKLOAD IDENTITY
       SPIFFE SVID validation — agent-runtime authenticated by SPIRE
    │
    ▼  [L4] INPUT SECURITY
       llama-guard-3:8b — jailbreak and malicious intent detection
    │
    ▼  [L5] ROUTING & ORCHESTRATION
       JWT-ACE token issued — ephemeral, capability-bounded
       Nemotron-Orchestrator — intent classification, delegation
    │
    ▼  [L4] OUTPUT VERIFICATION
       MarsRL LogicVerifier — AST + coherence + safety hard-block
    │
    ▼  [L7] CAPABILITY ENFORCEMENT
       JWT-ACE thread-local context — enforces tool access per agent
    │
    ▼  [L6] GOVERNANCE & AUDIT
       Langfuse trace — full interaction log, process reward scores
    │
Response Delivered
```

**Overall MAESTRO Status**: ✅ 98% compliant (2% gap = Gateway Node not yet SPIRE-enrolled; covered by JWT-ACE at runtime).

---

## 2. SPIRE / SPIFFE — Zero-Trust Workload Identity

### What It Does

SPIRE (Secure Production Identity Runtime for Everyone) issues **short-lived X.509 SVIDs** (SPIFFE Verifiable Identity Documents) to each container workload on Execution Node. These certificates:

- Rotate automatically (no long-lived secrets)
- Are cryptographically tied to the specific Docker workload (image SHA + container labels)
- Enable **mutual TLS (mTLS)** between services — both sides authenticate each other
- Are issued by a SPIRE Server running on the Control Node (acting as the certificate authority)

### Architecture

```
Control Node (<control-node-ip>)
  └── SPIRE Server
        ├── Workload Registry (PostgreSQL)
        └── Issues SVIDs to enrolled agents

Execution Node (<execution-node-ip>)
  └── SPIRE Agent (spire-agent container)
        ├── Receives SVIDs from server
        ├── Exposes Unix socket: /var/run/spire/agent.sock
        └── Agent Runtime reads SVID via SPIFFE_ENDPOINT_SOCKET env var

Gateway Node (<gateway-node-ip>)
  └── SPIRE Agent (spire-agent-r730 container) — ⚠️ pending enrollment
```

### Workload Registration

Each workload is identified by:
```
spiffe://home-ai-lab/agent/runtime
spiffe://home-ai-lab/security/service
```

SPIRE verifies the workload against the Docker attestor (image SHA, container labels, pod UID).

### Current Status

| Node | Status | Notes |
|------|--------|-------|
| Execution Node | ✅ Enrolled | Agent runtime authenticated via SVID |
| Control Node | ✅ Enrolled | SPIRE server itself |
| Gateway Node | ⚠️ Pending | JWT-ACE covers runtime gaps; SPIRE enrollment is Phase 7 |

---

## 3. JWT-ACE — Capability-Based Access Control

### What It Does

**JWT-ACE** (JWT + Agent Capability Extension) issues an **ephemeral capability token** at the start of every agent invocation. This token:

- Embeds an `EphemeralAgentCard` listing exactly which tools the agent may call
- Propagates via thread-local execution context throughout the request lifecycle
- Expires after the request completes
- Is signed with the system's JWT secret

This means: even if an AI model tries to call a tool outside its approved set, the `capability_gate` decorator blocks the call before it executes.

### Token Schema

```json
{
  "sub": "agent_runtime",
  "iss": "home-ai-lab-security-service",
  "iat": 1742000000,
  "exp": 1742000300,
  "agent_card": {
    "agent_id": "coding-expert-v3",
    "template_id": "coding-expert",
    "capabilities": ["file_read", "file_write", "terminal_exec"],
    "security_level": "elevated",
    "session_id": "abc-123"
  }
}
```

### Capability Taxonomy

| Capability | Allowed Actions |
|------------|-----------------|
| `file_read` | Read files in approved paths |
| `file_write` | Write/create files in workspace |
| `terminal_exec` | Execute shell commands (sandboxed) |
| `iot_control` | Home Assistant API calls |
| `image_generate` | ComfyUI API calls |
| `voice_generate` | TTS / RVC API calls |
| `web_search` | External search (planned Phase 7) |

### Enforcement

```python
@capability_gate("terminal_exec")
def run_shell_command(cmd: str) -> str:
    # This function is blocked if the current JWT doesn't include "terminal_exec"
    ...
```

The `@capability_gate` decorator reads the JWT from the thread-local `ExecutionContext`. If the capability is missing, it raises `CapabilityDeniedError` before any execution occurs.

### Key Files

| File | Purpose |
|------|---------|
| `agents/security/token_issuer.py` | JWT generation, validation, EphemeralAgentCard dataclass |
| `agents/security/capability_gate.py` | `@capability_gate` decorator, capability validation |
| `agents/security/authorization_middleware.py` | FastAPI middleware for automatic JWT extraction |
| `agents/security/execution_context.py` | Thread-local context for token propagation |
| `agents/security/audit_logger.py` | Structured security event logging |

---

## 4. MarsRL Output Verification

The **LogicVerifier** enforces output quality and safety at the end of every coding response:

| Layer | Check | Penalty | Hard Block? |
|-------|-------|---------|-------------|
| 1 — AST Parse | Python syntax valid | −0.40 score | No (triggers Corrector) |
| 2 — Coherence | Non-empty, no repetition, no truncation | −0.25 score | No (triggers Corrector) |
| 3 — llama-guard | Unsafe content / harmful instructions | score = 0.0 | **YES** — response discarded |

**Pass threshold**: ≥ 0.60. Below this, the Corrector is invoked for up to 2 rounds.

The llama-guard layer runs on the Gateway Node Ollama instance (`llama-guard-3:8b`) and is isolated from the primary inference workload.

---

## 5. Drift Governance

The `drift` tool monitors the codebase continuously for **policy violations and code pattern deviations**:

### Approved Patterns (Required)

| Pattern | Reason |
|---------|--------|
| `try/except` with specific exception types | Prevents silent failures |
| `os.getenv()` for all secrets | No hardcoded credentials |
| Structured logging via `setup_logger()` | Consistent audit trail |
| Docker user-namespace remapping | Non-root container execution |

### Blocked Patterns (Fail-on-Detection)

| Pattern | Reason Blocked |
|---------|----------------|
| `eval(...)` | Arbitrary code execution |
| `exec(...)` | Arbitrary code execution |
| Hardcoded IP/password strings in source | Secrets exfiltration risk |
| Bare `except:` (no exception type) | Masks security errors |
| `subprocess.shell=True` without review | Shell injection risk |

Every agent-generated code commit is drift-checked before merge. Violations are logged to the audit trail.

---

## 6. Docker Security Isolation

| Control | Configuration |
|---------|---------------|
| User namespace remapping | Non-root containers (`userns-remap: default`) |
| Network segmentation | Each tier has its own Docker network; cross-tier only via declared ports |
| Volume permissions | Minimal read-only mounts; write access only where required |
| No privileged mode | Exception: cAdvisor (requires host access for metrics) |
| Secrets injection | All secrets via `.env` file, never in compose YAML or source |
| Container restart policy | `always` for core services; `no` for training/diagnostic profiles |

---

## 7. Secret Management

All secrets are managed via `.env` files, **never** committed to git.

| Secret | File | Used By |
|--------|------|---------|
| `LANGFUSE_SECRET_KEY` | `execution_plane/.env` | Agent runtime Langfuse auth |
| `LANGFUSE_PUBLIC_KEY` | `execution_plane/.env` | Agent runtime Langfuse auth |
| `REDIS_PASSWORD` | `execution_plane/.env` | GPU mutex authentication |
| `TEMPLATE_DB_URL` | `execution_plane/.env` | PostgreSQL swarm schema connection |
| `AGNO_DB_URL` | `execution_plane/.env` | Agno session store |
| `HOME_ASSISTANT_TOKEN` | `execution_plane/.env` | Home Assistant API auth |
| `SPIRE_JOIN_TOKEN` | `execution_plane/.env` | SPIRE agent enrollment |
| `JWT_SECRET_KEY` | `execution_plane/.env` | JWT-ACE token signing |
| `GRAFANA_ADMIN_PASSWORD` | `r730_gateway/.env` | Grafana admin account |

**Default credential audit**: Review the following on every deployment:
- Grafana: `admin/admin` — **change immediately**
- PostgreSQL: `langfuse/langfuse` — change in both control_plane and r730_gateway `.env`
- Authentik: set via first-run wizard

---

## 8. Security Agent (Runtime)

The `SecurityAgent` provides a **second input screening layer** (complements llama-guard):

- **Regex-based blocking**: Patterns for shell injection, directory traversal, credential theft
- **Dependency gating**: Validates package names before `pip install` execution
- **Command allowlist**: Terminal commands are checked against approved patterns
- **Audit logging**: All blocked requests logged with reason and request context

Source: `agents/security_agent.py`

---

## 9. Authentik SSO

**Authentik** provides Single Sign-On authentication for all gateway-exposed services:

- Provider: `http://<gateway-node-ip>:9000`
- Integration: Traefik forward-auth (`authentik@docker` middleware)
- Protected services: ComfyUI, VS Code IDEs, OpenHands, and any future services tagged with the Authentik middleware
- Authentication flows: Local username/password + optional MFA

Services with **no** Authentik protection (internal only, not exposed via Traefik): Prometheus, Loki, internal compose networks.

---

## 10. Audit Trail

Every request generates a **Langfuse trace** that serves as the authoritative audit record:

| Field | Content |
|-------|---------|
| `trace_id` | UUID, referenced in `swarm.performance_history` |
| `name` | `mars_loop` |
| `session_id` | Per-user session identifier |
| `input` | First 4,000 chars of user request |
| `output` | Final response (first 4,000 chars) |
| `metadata.intent` | Classified intent (CODE, RESEARCH, etc.) |
| `metadata.template_id` | Which ExpertiseTemplate was used |
| `metadata.token_capabilities` | JWT-ACE capabilities granted |

**Spans** per request: `solver_generation`, `verifier_round_1..N`, `corrector_generation`

**Scores** per request: `verifier_round_1..N`, `solver_score`, `final_quality`, `training_candidate`

Evidence files: see [`docs/evidence/`](../evidence/) for all point-in-time audit snapshots.

---

## 11. Open Security Items

| Item | Risk | Mitigation | Phase |
|------|------|-----------|-------|
| Gateway Node not SPIRE-enrolled | Medium — no mTLS from Gateway Node workloads | JWT-ACE covers runtime identity | Phase 7 |
| Grafana anonymous viewer | Low — read-only, internal only | Restrict to Authentik auth when public | Phase 7 |
| Redis port not exposed (Control Node) | Low — GPU mutex fail-open | Manual sudo on Control Node console | Next session |
| Traefik TLS (HTTPS) | Medium — HTTP only on LAN | Add TLS certs (Let's Encrypt / self-signed) | Phase 7 |

---

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `docs/security/identity_token_trust_standard.md` | Standard | JWT-ACE token format and trust chain |
| `docs/security/api_authentication_contract.md` | Standard | API key validation and claims |
| `docs/security/key_lifecycle_rotation_runbook.md` | Runbook | Key rotation procedures |
| `docs/security/hook_security_execution_policy.md` | Policy | Hook execution sandboxing rules |
| `agents/main.py` | Implementation | JWT-ACE middleware, API key validation |
| `agents/security_scanner.py` | Implementation | llama-guard safety screening |
| `agents/governance.py` | Implementation | Drift detection and governance checks |
| [SPIFFE/SPIRE](https://spiffe.io/) | Standard | Zero-trust workload identity |
| [RFC 7519 — JWT](https://tools.ietf.org/html/rfc7519) | Standard | JSON Web Token specification |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-23 | AI-Copilot | Updated to v3.3 with Authentik SSO and open security items |
| 2026-03-10 | AI-Copilot | Added JWT-ACE and MarsRL security sections |
| 2026-02-20 | AI-Copilot | Initial security reference created |

</details>

---

## Maintenance & Update Guide

### When to Update This Document

- After any security-related code change (JWT issuance, key rotation, SPIRE enrollment).
- After closing an Open Security Item — move it from the open items table to a "Resolved" section.
- After adding new security layers or changing the trust model.

### Key Rotation Procedure

Refer to [`key_lifecycle_rotation_runbook.md`](../security/key_lifecycle_rotation_runbook.md) for step-by-step instructions.

### Incident Response

Refer to [`key_compromise_incident_runbook.md`](../security/key_compromise_incident_runbook.md) and the [`checklist`](../security/key_compromise_incident_checklist.md).

---

## Functionality Testing

### Automated Tests

| Test File | What It Covers |
|-----------|---------------|
| `tests/test_security.py` | JWT-ACE issuance, API key validation, capability gating |
| `tests/test_governance.py` | Drift detection, safety screening |

### Manual Verification

1. **JWT-ACE**: Issue a request → check Agent Trace → verify JWT was issued with correct capabilities.
2. **SPIRE**: Run `docker exec spire-agent spire-agent api fetch x509` → verify valid SVID returned.
3. **Safety screening**: Send a borderline prompt → verify llama-guard verdict appears in trace.
4. **Open items audit**: Review each open security item and confirm mitigation status is accurate.

---

*For compliance evidence, see [MAESTRO Status](../compliance/maestro_compliance_status.md) · [Back to Index](../INDEX.md)*
