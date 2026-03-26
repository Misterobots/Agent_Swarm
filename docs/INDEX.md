# Home AI Lab — Documentation Index

**System**: Agentic Hive v3.3 — Distributed Multi-Agent Swarm
**Last Updated**: 2026-03-23
**Architecture Status**: Production (Phase 6 complete, Phase 7 in progress)

> This index is the single entry point for all documentation. Every document links back here.
> Third-party auditors: start with [Compliance Status](compliance/maestro_compliance_status.md) and [Security](admin/security.md).

---

## For Users

| Document | Description |
|----------|-------------|
| [System Overview](user/overview.md) | What the Hive is, what it can do, and how to interact with it |
| [How the Agent Swarm Works](user/framework.md) | Plain-language explanation of MarsRL, agents, and routing |
| [Training Guide](user/training_guide.md) | How to use the Training interface — run types, options, security scanning, CLI, API |
| [Art Studio Guide](user/art_studio_guide.md) | Image, 3D model, and action figure generation workspace |
| [FAQ](user/faq.md) | Common questions from day-to-day users |

---

## For Administrators

| Document | Description |
|----------|-------------|
| [Technical Reference](admin/technical_reference.md) | All services, IPs, ports, APIs, deployment commands |
| [Design Framework](admin/design_framework.md) | 3-tier architecture, MarsRL loop, agent topology, data flows |
| [Security](admin/security.md) | SPIRE/SPIFFE, JWT-ACE, MAESTRO framework, defensive layers |
| [Troubleshooting](admin/troubleshooting.md) | Common failure modes, SPIRE, monitoring, voice, GPU issues |
| [Agent Training Reference](admin/agent_training_reference.md) | Agent architecture, adding new agents, semantic router training, templates |

---

## Compliance & Audit

| Document | Description |
|----------|-------------|
| [MAESTRO Compliance Status](compliance/maestro_compliance_status.md) | Current compliance posture, component matrix, open items |
| [Agent Logic Evaluation](compliance/eval_agent_logic.md) | MarsRL decision-making and agent behaviour audit |
| [Identity & Security Evaluation](compliance/eval_identity_security.md) | JWT-ACE and capability access control audit |
| [Infrastructure Evaluation](compliance/eval_infrastructure.md) | Hardware reliability and resource management audit |
| [Observability Evaluation](compliance/eval_observability.md) | Langfuse, Prometheus, and Grafana stack audit |
| [Data Layer Evaluation](compliance/eval_data_layer.md) | PostgreSQL, MinIO, ClickHouse data management audit |
| [Governance Evaluation](compliance/eval_governance.md) | SPIRE, drift monitoring, output validation audit |

### Audit Evidence Trail

All point-in-time audit snapshots are in [`evidence/`](evidence/). Key milestones:

| File | Date | Scope |
|------|------|-------|
| [Phase 6 Training Pipeline Audit](evidence/phase6_training_pipeline_audit_2026_03_21.md) | 2026-03-21 | GRPO training, A/B testing, model lifecycle |
| [Phase 5 JWT-ACE Audit](evidence/phase5_jwt_ace_audit_2026_03_17.md) | 2026-03-17 | Capability gating, ExpertiseTemplate versioning |
| [MAESTRO Full Audit (Feb 22)](evidence/maestro_full_audit_2026_02_22.md) | 2026-02-22 | Post-MarsRL full system review |
| [MAESTRO Full Audit (Feb 09)](evidence/maestro_full_audit_2026_02_09.md) | 2026-02-09 | Post-Langfuse deployment |

---

## Technical Specifications

| Document | Description |
|----------|-------------|
| [Identity Layer Spec](specs/identity_layer_spec.md) | JWT-ACE token schema, capability taxonomy, revocation |
| [Langfuse Observability Spec](specs/langfuse_observability_spec.md) | Trace structure, process reward scoring schema |
| [Wokwi Integration Spec](specs/wokwi_integration_spec.md) | IoT hardware simulation integration specification |

---

## Architecture Diagrams

Located in [`architecture/`](architecture/):
- `hive_topology_v3.drawio` — 3-node topology (editable)
- `marsrl_sequence.drawio` — Solver → Verifier → Corrector sequence
- `spiffe_flow.drawio` — SPIFFE/SPIRE authentication flow
- `hive_topology_v3_drawio.svg` — Rendered topology (embedded in design_framework.md)

---

## Active Roadmap

| Document | Description |
|----------|-------------|
| [Phase Roadmap](PHASE5_PLUS_ROADMAP.md) | Current and planned phases (5–9), open items, architecture decisions |

---

## Archived Documents

Historical documents (completed phases, superseded references) are in [`archived/`](archived/).
These are **read-only reference** — do not update them. All current content lives in the sections above.

---

*Document Owner: Engineering · Review Cycle: Per major phase · Questions: raise a GitHub issue*
