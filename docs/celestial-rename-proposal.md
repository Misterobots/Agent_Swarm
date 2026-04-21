# Hive — Celestial Naming Scheme Proposal
**Date:** April 20, 2026  
**Status:** Pending team review  
**Scope:** Full ecosystem — nodes, services, agent components, env vars, Python files, documentation

---

## Overview

This proposal replaces all informal/hardware-derived names (Turing, Lovelace, Hopper, BMO)
with a consistent celestial naming scheme. The top-level brand **Hive** is unchanged.

- **Turing** (the sun) — illuminates and monitors everything — edge/gateway
- **Lovelace** (Saturn's largest moon) — heavy gravitational body — GPU compute
- **Hopper** (the north star) — fixed reference point — control/identity
- **Shannon** (the ambient fifth element) — pervasive and invisible — voice/periphery

---

## Node Renames

| Current Name | New Name | Role | IP |
|---|---|---|---|
| Turing | **Turing** | Gateway, monitoring, edge ingress | 192.168.2.103 |
| Lovelace | **Lovelace** | GPU compute, AI inference, ComfyUI | 192.168.2.101 |
| Hopper / Hopper | **Hopper** | Control plane, identity (SPIRE), observability | 192.168.2.102 |
| Pi / BMO | **Shannon** | Voice interface, ambient periphery | 192.168.2.157 |

```mermaid
graph LR
    Turing -->|→| Turing
    Lovelace -->|→| Lovelace
    Wyse-5070 -->|→| Hopper
    BMO -->|→| Shannon