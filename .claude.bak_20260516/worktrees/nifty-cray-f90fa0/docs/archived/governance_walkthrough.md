# Governance Walkthrough: Agentic Hive

**Version**: 3.0 (MarsRL + SPIFFE + 3-Node Topology)
**Date**: 2026-02-22

## Overview

This walkthrough demonstrates the **active governance mechanisms** of the Agentic Hive. The system is not merely compliant on paper — every request passes through multiple automated security, verification, and audit layers before a response is returned.

---

## 1. Request Lifecycle (Per MAESTRO Layers)

```
User Request
    │
    ▼  L7: Identity
[SPIFFE SVID validation — agent-runtime authenticated]
    │
    ▼  L4: Input Security
[llama-guard-3:8b — jailbreak/malicious intent check]
    │
    ▼  L5: Orchestration
[Nemotron-Orchestrator-8B — intent classification]
    │
    ├─▶ CODE ──▶ MarsRL Loop (L4 Output Verification)
    │               Solver → Verifier → Corrector
    │
    ├─▶ IMAGE/3D ──▶ ComfyUI → cv2 check → Moondream VLM
    │
    └─▶ IoT ──▶ Home Assistant API (safe_mode guard)
    │
    ▼  L6: Governance
[Langfuse trace — full audit trail with process reward scores]
    │
    ▼
User Response
```

---

## 2. MarsRL Output Verification (New in v3.0)

The most significant governance improvement in v3.0 is the **MarsRL LogicVerifier** — a 3-layer output verification that runs on every coding response before it reaches the user.

| Layer       | What It Catches              | Hard Block?              |
| ----------- | ---------------------------- | ------------------------ |
| AST Parse   | Broken Python syntax         | No (triggers Corrector)  |
| Coherence   | Empty, repetitive, truncated | No (triggers Corrector)  |
| llama-guard | Unsafe/harmful content       | **Yes — zero tolerance** |

**Result**: Bad code never reaches the user. The Corrector fixes it first.

---

## 3. SPIFFE / SPIRE Zero-Trust

All workloads on Lovelace hold a **short-lived X.509 SVID** issued by the SPIRE server on the Dell Wyse. These certificates:

- Rotate automatically (no long-lived secrets)
- Are tied to the specific Docker workload (image SHA + labels)
- Enable mutual TLS (mTLS) between authenticated services

**Current status**: Lovelace fully enrolled. Dell Turing pending enrollment.

---

## 4. Drift Governance

The `drift` tool continuously monitors the codebase for pattern deviations:

- ✅ **Approved patterns**: `try/except`, structured logging, `os.getenv()` for secrets
- ❌ **Blocked patterns**: `eval()`, hardcoded credentials, bare `except:` clauses

Every agent-generated code commit is checked against the drift baseline before being accepted.

---

## 5. Observability Evidence

Every request generates a Langfuse trace with:

- **Span**: `mars_loop` → sub-spans per agent step
- **Scores**: `solver_score`, `verifier_round_N`, `final_quality`
- **Metadata**: intent, model names, iteration count

These scores double as a **training dataset** for future GRPO fine-tuning of local models.

**Langfuse**: http://192.168.2.102:3000

---

## 6. Audit History

| Date       | Version  | Key Event                                         |
| ---------- | -------- | ------------------------------------------------- |
| 2026-02-02 | v1.0     | Initial deployment                                |
| 2026-02-08 | v1.2     | SPIFFE enrollment + Langfuse                      |
| 2026-02-09 | v1.3     | Langfuse observability deployed                   |
| 2026-02-22 | **v3.0** | MarsRL loop, 3-node topology, Qwen + Nemotron |

Full audit evidence: [`docs/evidence/`](evidence/)
