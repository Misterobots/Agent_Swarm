# Home AI Lab: Agentic Hive

**Version**: 3.4 (Phase 6 complete) · **Status**: Production · **Updated**: 2026-03-31

A self-hosted, distributed multi-agent AI system for home automation, coding, creative media, and voice interaction. All inference runs on-premises — no external AI services.

---

## Documentation

> **Start here**: [docs/INDEX.md](docs/INDEX.md)

| Audience | Entry Point |
|----------|-------------|
| **Users** | [System Overview](docs/user/overview.md) · [How It Works](docs/user/framework.md) · [FAQ](docs/user/faq.md) |
| **Admins** | [Technical Reference](docs/admin/technical_reference.md) · [Design Framework](docs/admin/design_framework.md) · [Security](docs/admin/security.md) · [Troubleshooting](docs/admin/troubleshooting.md) |
| **Auditors** | [MAESTRO Compliance](docs/compliance/maestro_compliance_status.md) · [System Catalog](docs/catalog/system_component_service_catalog.md) · [Feature Traceability](docs/compliance/feature_control_traceability_matrix.md) · [Evidence Trail](docs/evidence/) |

### Canonical Security Standards

- [Identity and Token Trust Standard](docs/security/identity_token_trust_standard.md)
- [Key Lifecycle and Rotation Runbook](docs/security/key_lifecycle_rotation_runbook.md)
- [Multi-user Identity Scoping Standard](docs/security/multi_user_identity_scoping_standard.md)
- [Hook Security and Execution Policy](docs/security/hook_security_execution_policy.md)

---

## Architecture at a Glance

```
                Gateway Node — Reverse Proxy & Monitoring
                Traefik · Grafana · Prometheus · Loki
                           │              │
         Execution Node (GPU)         Control Node
         RTX 5060 Ti 16GB             SPIRE · Langfuse · PostgreSQL
         Ollama · Agent Runtime       ClickHouse · MinIO · Redis
         ComfyUI · Voice · Training
```

### MarsRL Quality Loop

Every coding request runs through an inference-time verification loop:

```
User → Router (Nemotron-8B) → Solver (Qwen 3.5 9B)
         └→ Verifier (AST + Coherence + llama-guard-3)
               ├── PASS (score ≥ 0.60) → Response
               └── FAIL → Corrector → Verifier (repeat ×2)
```

Bad code is **fixed before it reaches you**. High-quality traces (score ≥ 0.80) automatically seed the GRPO fine-tuning pipeline, improving local models over time.

---

## Security Posture

- **SPIFFE/SPIRE**: Zero-trust X.509 workload identity (Execution Node enrolled; Gateway Node pending)
- **JWT-ACE**: Ephemeral per-request capability tokens — agents can only call their approved tools
- **MAESTRO**: L1–L7 security framework audit (98% compliant — see [compliance status](docs/compliance/maestro_compliance_status.md))
- **Output validation**: 3-layer LogicVerifier (AST + coherence + llama-guard-3:8b hard-block)
- **Full observability**: Langfuse traces with process-reward scores for every interaction

---

## Current Phase

| Phase | Status | Key Capability |
|-------|--------|----------------|
| 1–3 | ✅ Complete | Infrastructure, MarsRL loop, 3-node topology |
| 4 | ✅ Complete | Gateway node migration, distributed monitoring |
| 5 | ✅ Complete | JWT-ACE capability gating, ExpertiseTemplate versioning |
| 6 | ✅ Complete | GRPO fine-tuning pipeline, A/B testing, model conversion & deployment |
| 7 | 🔜 Next | HA, Gateway Node SPIRE enrollment, k3s migration |

See [Phase Roadmap](docs/PHASE5_PLUS_ROADMAP.md) for Phase 7–9 plans.

---

## MCP Smoke Test

After restarting `agent_runtime`, run:

```bash
python scripts/smoke_mcp_bridge.py --base-url http://127.0.0.1:8008
```

Optional authenticated check:

```bash
python scripts/smoke_mcp_bridge.py --base-url http://127.0.0.1:8008 --bearer <JWT_TOKEN>
```

Strict authenticated validation (fails if bearer call is rejected):

```bash
python scripts/smoke_mcp_bridge.py --base-url http://127.0.0.1:8008 --bearer <JWT_TOKEN> --strict-bearer
```

---

_Agentic Hive v3.4 · Self-hosted · Private inference · No cloud dependencies_
