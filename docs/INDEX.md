# Home AI Lab — Documentation Index

**System**: Agentic Hive v3.4 — Distributed Multi-Agent Swarm
**Last Updated**: 2026-04-16
**Architecture Status**: Production (Phase 6 complete, Phase 7 in progress)

> This index is the canonical entry point for all documentation. Every canonical document must link back here.
> Third-party auditors: start with [Compliance Status](compliance/maestro_compliance_status.md), [Security](admin/security.md), and [System Catalog](catalog/system_component_service_catalog.md).

---

## Documentation Governance

| Document | Description |
|----------|-------------|
| [Documentation Governance Standard](governance/documentation_governance_standard.md) | Canonical document classes, metadata requirements, ownership, and review SLAs |
| [Documentation Gap Register](governance/documentation_gap_register.md) | Open documentation coverage gaps with severity, owner, and target date |
| [Sprint Tracking Board](governance/sprint_tracking_board.md) | Centralized tracking of Sprint 1–3 deliverables, owners, targets, and verification gates |

---

## For Users

| Document | Description |
|----------|-------------|
| [System Overview](user/overview.md) | What the Hive is, what it can do, and how to interact with it |
| [How the Agent Swarm Works](user/framework.md) | Plain-language explanation of MarsRL, agents, and routing |
| [Training Guide](user/training_guide.md) | How to use the Training interface — run types, options, security scanning, CLI, API |
| [Art Studio Guide](user/art_studio_guide.md) | Image, 3D model, and action figure generation workspace |
| [FAQ](user/faq.md) | Common questions from day-to-day users |
| [Plan & Think Modes Guide](user/plan_and_think_modes.md) | UltraPlan structured planning, UltraThink visible reasoning, auto-feed setting |
| [Buddy Companion Guide](user/buddy_companion_guide.md) | Pixel-art buddy hatching, species, XP leveling, evolution, achievements, tips |

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
| [Feature Control Traceability Matrix](compliance/feature_control_traceability_matrix.md) | Feature-to-component-to-control-to-evidence mapping |
| [Voice Feature Control Mapping](compliance/voice_feature_control_mapping.md) | Voice feature inventory and mapping to controls and evidence |
| [IoT Feature Control Mapping](compliance/iot_feature_control_mapping.md) | IoT/home-automation feature mapping to controls and evidence |

---

## Security Standards

| Document | Description |
|----------|-------------|
| [Identity and Token Trust Standard](security/identity_token_trust_standard.md) | JWT profile separation, validation rigor, and issuer/audience trust model |
| [API Authentication and Claims Contract](security/api_authentication_contract.md) | Endpoint classes, token profile policy, claims matrix, and validation chain |
| [API Contract Validation Examples](security/api_contract_validation_examples.md) | Executable request/response examples for endpoint-class and token-profile checks |
| [Key Lifecycle and Rotation Runbook](security/key_lifecycle_rotation_runbook.md) | Key generation, custody, rotation, rollback, and compromise response |
| [Key Compromise Incident Runbook](security/key_compromise_incident_runbook.md) | SEV-1 response procedure for key compromise detection, containment, recovery, and evidence logging |
| [Key Compromise Incident Checklist](security/key_compromise_incident_checklist.md) | One-page on-call checklist for first-hour compromise response |
| [Multi-user Identity Scoping Standard](security/multi_user_identity_scoping_standard.md) | End-to-end user_id propagation, partitioning, and isolation controls |
| [Hook Security and Execution Policy](security/hook_security_execution_policy.md) | Hook lifecycle controls, scope enforcement, timeout, and failure isolation |

---

## Architecture Decisions (ADRs)

| Document | Description |
|----------|-------------|
| [ADR Index](decisions/ADR_INDEX.md) | Central index and process for Architecture Decision Records |
| [ADR-001: JWT Profile Separation](decisions/ADR-001_jwt_profile_separation.md) | Strict mutual exclusion between workload and user tokens; endpoint-class routing |
| [ADR-002: Hook Execution Model](decisions/ADR-002_hook_execution_model.md) | Sync security hooks (fail-closed) vs. async non-security hooks (best-effort) |
| [ADR-003: User-Scoped Storage](decisions/ADR-003_user_scoped_storage.md) | Composite-keyed storage with hard ownership checks; user_id propagation contract |
| [ADR-004: MarsRL Inference-Time Verification](decisions/ADR-004_marsrl_inference_verification.md) | Three-stage loop: Solver (generate) → Verifier (validate) → Corrector (fix) |

---

## System Catalog

| Document | Description |
|----------|-------------|
| [System Component and Service Catalog](catalog/system_component_service_catalog.md) | Canonical inventory of nodes, services, APIs, data stores, models, and ownership |

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

## Architecture Deep Dives

| Document | Description |
|----------|-------------|
| [Multi-user Propagation Trace](architecture/multi_user_propagation_trace.md) | Current-state ingress-to-storage identity/context path with target-state control deltas |
| [Cross-user Isolation Test Plan](architecture/cross_user_isolation_test_plan.md) | Executable T1–T5 validation plan for context, memory, preference, and endpoint isolation |
| [Router Intent and Token Flow Deep Dive](architecture/router_intent_token_flow_deep_dive.md) | Request ingress, endpoint-class policy, intent routing, and token-profile enforcement walkthrough |
| [MarsRL Inference Verification Deep Dive](architecture/marsrl_inference_verification_deep_dive.md) | Solver-verifier-corrector control loop and inference-time safety verification architecture |
| [Memory and Preferences Deep Dive](architecture/memory_preferences_subsystem_deep_dive.md) | Owner-scoped context partitioning, memory recall filtering, and preference isolation model |
| [Skills and Hooks Pipeline Deep Dive](architecture/skills_hooks_pipeline_deep_dive.md) | Skill dispatch path, hook controls, IoT-sensitive safeguards, and audit observability |
| [MemPalace Integration Deep Dive](architecture/mempalace_integration_deep_dive.md) | Official MemPalace v3.3.0 library integration, palace hierarchy, hall mapping, KnowledgeGraph |
| [JWT-ACE Card Lifecycle Deep Dive](architecture/jwt_ace_card_lifecycle_deep_dive.md) | Session cards, active scope narrowing, child card derivation, validation cache |

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

*Document Owner: Architecture + Compliance · Review Cycle: Monthly (security/compliance), Quarterly (user/admin guides) · Questions: raise a GitHub issue*

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `docs/` | Documentation | All documentation files indexed here |
| `docs/archived/` | Archive | Superseded documents |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide |
| 2026-04-15 | AI-Copilot | v3.4 — Added Plan/Think, MemPalace, Buddy, JWT-ACE deep dives |
| 2026-03-21 | AI-Copilot | v3.3 — Phase 6 training pipeline docs |

</details>

---

## Maintenance & Update Guide

- Add a link to INDEX.md whenever a new documentation file is created.
- Move superseded docs to `archived/` and update their links here.
- Review monthly to ensure all links resolve correctly.
