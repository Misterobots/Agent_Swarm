# SPIFFE / SPIRE / MAESTRO Security Assessment

**Date**: 2026-02-22
**Version**: 2.0 (Post MarsRL Redesign + Gateway Node Addition)
**Assessor**: Home AI Lab Governance
**Status**: ✅ Substantially Compliant | ⚠️ Gateway Node Enrollment Pending

---

## 1. Executive Summary

This assessment evaluates the Home AI Lab Agentic Hive's implementation of SPIFFE (Secure Production Identity Framework for Everyone), SPIRE (SPIFFE Runtime Environment), and the MAESTRO governance framework following the **v3.0 architecture redesign**.

The key change since the last assessment (v1.3, 2026-02-09) is the addition of a **third inference node** — the Gateway Node (Dell PowerEdge Turing) — which introduces new identity and trust boundary considerations requiring SPIRE enrollment.

---

## 2. Topology Change Impact Analysis

### Previous Topology (v1.x)

```
Control Plane (Control Node) ──SVID──▶ Execution Plane (Execution Node)
     [spire-server]                      [spire-agent]
```

### New Topology (v3.0)

```
Control Plane (Control Node) ──SVID──▶ Execution Plane (Execution Node)
     [spire-server]         │             [spire-agent] ✅ enrolled
                            │
                            └──SVID──▶ Inference Node (Gateway Node)
                                           [spire-agent] ⚠️ NOT YET ENROLLED
```

> [!CAUTION]
> Until the Gateway Node is enrolled as a SPIRE agent, traffic between Execution Node and Gateway Node falls back to **unauthenticated HTTP** via `SECONDARY_OLLAMA_HOST`. This is an acceptable interim risk for a home lab but must be remediated before any external exposure.

---

## 3. SPIFFE Assessment

### 3.1 Current SVID Issuance

| Workload                  | SPIFFE ID                         | Status          | Trust Domain |
| ------------------------- | --------------------------------- | --------------- | ------------ |
| `agent-runtime`           | `spiffe://home-lab/agent-runtime` | ✅ Active       | `home-lab`   |
| `spire-agent` (Execution Node) | `spiffe://home-lab/spire-agent`   | ✅ Active       | `home-lab`   |
| `ollama_gpu` (Execution Node)  | `spiffe://home-lab/ollama`        | ✅ Active       | `home-lab`   |
| Gateway Node workloads       | —                                 | ⚠️ Not enrolled | —            |

### 3.2 SVID Properties

- **Type**: X.509 SVID
- **TTL**: Short-lived (auto-rotated by SPIRE agent)
- **Delivery**: Unix Domain Socket at `/var/run/spire/agent.sock`
- **mTLS**: Mutual TLS between enrolled workloads via `py-spiffe`

### 3.3 Trust Domain

- **Domain**: `spiffe://home-lab`
- **CA**: SPIRE Server on Control Node (internal CA — not publicly rooted)
- **Federation**: None (single-trust-domain deployment)

---

## 4. SPIRE Assessment

### 4.1 SPIRE Server (Control Node 5070)

| Property             | Value                    | Compliant?                 |
| -------------------- | ------------------------ | -------------------------- |
| Port                 | 8081                     | ✅                         |
| Node attestation     | Docker workload attestor | ✅                         |
| Entry management     | spire-server CLI         | ✅                         |
| Certificate rotation | Automatic                | ✅                         |
| Data store           | SQLite (local)           | ✅ (adequate for home lab) |
| Backup               | Not configured           | ⚠️ Risk                    |

### 4.2 SPIRE Agent (Execution Node)

| Property          | Value                                     | Compliant? |
| ----------------- | ----------------------------------------- | ---------- |
| Socket path       | `/var/run/spire/agent.sock`               | ✅         |
| Workload attestor | Docker                                    | ✅         |
| Node attestation  | x509pop                                   | ✅         |
| Auto-rotation     | Yes                                       | ✅         |
| Config file       | `execution_plane/config/spire/agent.conf` | ✅         |

### 4.3 SPIRE Agent (Gateway Node — PENDING)

**Required Enrollment Steps:**

```bash
# On Control Node (SPIRE Server):
# 1. Register Gateway Node as a new agent node
spire-server agent ban -spiffeID spiffe://home-lab/dell-turing  # clean start
spire-server entry create \
  -spiffeID spiffe://home-lab/dell-turing/ollama \
  -parentID spiffe://home-lab/spire-agent \
  -selector docker:image:ollama/ollama

# On Gateway Node:
# 2. Install and configure spire-agent
docker run -d --name spire-agent \
  -v /run/spire:/run/spire \
  -v /etc/spire/agent:/etc/spire/agent \
  ghcr.io/spiffe/spire-agent:latest \
  -config /etc/spire/agent/agent.conf

# 3. Verify enrollment
spire-server agent list | grep dell-turing
```

---

## 5. MAESTRO Framework Assessment (L1–L7)

### L1 — Infrastructure Security

| Control              | Implementation                       | Status |
| -------------------- | ------------------------------------ | ------ |
| Node isolation       | 3 dedicated nodes, separate hardware | ✅     |
| Network segmentation | `execution_net` bridge; Gateway Node on LAN  | ✅     |
| Container non-root   | User-namespace remapping             | ✅     |
| Firmware/OS patching | Manual (home lab)                    | ⚠️     |

### L2 — Data Security

| Control           | Implementation                            | Status |
| ----------------- | ----------------------------------------- | ------ |
| Secrets at rest   | `.env` file injection, no hardcoded creds | ✅     |
| DB encryption     | PostgreSQL TLS (internal)                 | ✅     |
| Model weights     | Local storage, no cloud sync              | ✅     |
| Context isolation | Per-session context managers              | ✅     |

### L3 — API Security

| Control              | Implementation        | Status    |
| -------------------- | --------------------- | --------- |
| API key auth         | `VALID_API_KEYS` dict | ✅        |
| Rate limiting        | Not implemented       | ⚠️ Future |
| TLS on Ollama (Gateway Node) | Not yet configured    | ⚠️ Open   |
| Input validation     | llama-guard-3 + regex | ✅        |

### L4 — Agent Logic Security

| Control                  | Implementation                  | Status     |
| ------------------------ | ------------------------------- | ---------- |
| Output verification      | MarsRL LogicVerifier (3 layers) | ✅ **NEW** |
| Tool gating              | Security Agent reviews all deps | ✅         |
| Memory isolation         | Per-agent PostgreSQL sessions   | ✅         |
| Prompt injection defense | llama-guard-3 on all inputs     | ✅         |
| Code execution sandbox   | OpenHands isolated container    | ✅         |

### L5 — Orchestration Security

| Control                        | Implementation                            | Status          |
| ------------------------------ | ----------------------------------------- | --------------- |
| Intent routing                 | Nemotron-Orchestrator-8B                  | ✅ **UPGRADED** |
| Multi-agent coordination       | MarsRL loop (max 2 iterations)            | ✅ **NEW**      |
| Agent impersonation prevention | AgentCard registry + SPIFFE SVIDs         | ✅              |
| Dispatch authorization         | Semantic router with confidence threshold | ✅              |

### L6 — Governance & Compliance

| Control                | Implementation                                 | Status     |
| ---------------------- | ---------------------------------------------- | ---------- |
| Code drift detection   | `drift` tool — approved patterns               | ✅         |
| Audit trail            | Langfuse traces + Grafana                      | ✅         |
| Process reward logging | Langfuse scores per MarsRL step                | ✅ **NEW** |
| Human override         | `safe_mode` flag in governance.json            | ✅         |
| Compliance docs        | This assessment + maestro_compliance_status.md | ✅         |

### L7 — Identity & Trust

| Control                     | Implementation                | Status  |
| --------------------------- | ----------------------------- | ------- |
| Workload identity           | SPIFFE SVIDs via SPIRE        | ✅      |
| mTLS between enrolled nodes | Active on Execution Node workloads | ✅      |
| Gateway Node identity          | **Not enrolled**              | ⚠️ Open |
| SVID rotation               | Automatic (SPIRE agent)       | ✅      |
| Trust domain federation     | N/A — single domain           | ✅      |

---

## 6. Risk Register

| Risk                                 | Likelihood | Impact | Mitigation                              |
| ------------------------------------ | ---------- | ------ | --------------------------------------- |
| Gateway Node↔Execution Node traffic unencrypted   | Medium     | Medium | Enroll Gateway Node in SPIRE; add nginx TLS     |
| SPIRE server single point of failure | Low        | High   | Backup SQLite DB regularly              |
| Ollama API exposed on LAN (Gateway Node)     | Medium     | Medium | Firewall to Execution Node only; add API key |
| No rate limiting on agent API        | Low        | Low    | Future: add rate limiter middleware     |
| OS/firmware not auto-patched         | Low        | Medium | Enable unattended-upgrades on Gateway Node      |

---

## 7. Remediation Roadmap

| Priority | Item                                   | Due                      | Owner       |
| -------- | -------------------------------------- | ------------------------ | ----------- |
| **P1**   | Enroll Gateway Node in SPIRE              | On hardware installation | Home AI Lab |
| **P1**   | Pull models on Gateway Node + verify Ollama    | On Gateway Node setup            | Home AI Lab |
| **P2**   | Set `SECONDARY_OLLAMA_HOST` in `.env`  | After Gateway Node setup         | Home AI Lab |
| **P2**   | Add nginx TLS proxy on Gateway Node Ollama     | Sprint 2                 | Home AI Lab |
| **P3**   | Firewall Gateway Node Ollama to Execution Node only | Sprint 2                 | Home AI Lab |
| **P3**   | Backup SPIRE SQLite DB                 | Sprint 3                 | Home AI Lab |
| **P4**   | Rate limiting on agent-runtime API     | Future                   | Home AI Lab |

---

## 8. Certification

> [!IMPORTANT]
> This assessment reflects the state of the system as of **2026-02-22**. The Agentic Hive is assessed as **SUBSTANTIALLY COMPLIANT** with MAESTRO L1–L7 at the home lab operational level. The single open critical item (Gateway Node SPIRE enrollment) does not block production operation but must be remediated before any external or multi-tenant exposure.

**Signed**: Home AI Lab Governance Automation
**Next Assessment Due**: Post Gateway Node Commissioning
