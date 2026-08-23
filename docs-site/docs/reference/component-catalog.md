---
title: Component Catalog
---

# Component Catalog

Canonical inventory of runtime components, services, and key dependencies with ownership, criticality, and trust boundary.

Migrated from the legacy catalog at `docs/catalog/system_component_service_catalog.md` (Document ID: CAT-SYS-001, Owner: Platform, Version 1.0, Last Updated 2026-03-31).

## Node-Level Components

| Component | Node | Type | Criticality | Owner | Trust Boundary | Data Class |
|---|---|---|---|---|---|---|
| Traefik | Gateway | Routing | High | Platform | Edge ingress | Internal metadata |
| Agent Runtime | Execution | API/Orchestration | High | Architecture | Internal compute | User interaction data |
| Ollama Primary | Execution | Inference | High | Platform | Internal compute | Prompts and completions |
| SPIRE Server | Control | Identity | High | Security | Control plane | Identity metadata |
| SPIRE Agent | Execution/Gateway | Identity | High | Security | Workload boundary | SVID metadata |
| PostgreSQL | Control | Data store | High | Platform | Control plane data | Structured operational data |
| Langfuse | Control | Observability | High | Compliance | Trace boundary | Trace and scoring data |
| Redis | Control | Cache and lock | Medium | Platform | Internal service | Runtime lock metadata |
| Grafana | Gateway | Monitoring UI | Medium | Platform | Ops UI | Metrics/log views |
| Loki | Gateway | Log store | Medium | Platform | Ops internal | Log data |
| Prometheus | Gateway | Metrics store | Medium | Platform | Ops internal | Metrics time series |
| ComfyUI | Execution | Media generation | Medium | Platform | Internal compute | Prompt and media output |
| Voice Engine | Execution | Voice service | Medium | Platform | Internal compute | Voice artifacts |

## Canonical Runtime Modules

| Module | Path | Function | Owner | Criticality |
|---|---|---|---|---|
| API Entrypoint | `agents/main.py` | API ingress and endpoint dispatch | Platform | High |
| Router | `agents/router.py` | Intent routing and orchestration | Architecture | High |
| Context Manager | `agents/context_manager.py` | Session context persistence | Platform | High |
| Preferences | `agents/preferences.py` | User preference lifecycle | Architecture | Medium |
| Token Issuer/Validator | `agents/security/token_issuer.py` | JWT issuance and validation | Security | High |
| SPIFFE Auth | `agents/security/spiffe_auth.py` | Workload identity validation | Security | High |
| Authorization Middleware | `agents/security/authorization_middleware.py` | Request auth enforcement | Security | High |

## Coverage Statement

Catalog v1 covers core runtime and control-plane components. Additional entries for detailed feature modules are tracked in the traceability matrix.
