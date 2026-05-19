---
title: "Skills & Hooks Pipeline Deep Dive"
---

# Skills Registry and Hook Invocation Pipeline Deep Dive

Document ID: ARCH-DD-004
Domain: Architecture
Owner: Architecture
Reviewers: Security, Platform
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Source of Truth: agents/church.py, agents/handlers/, agents/routing/gates.py, agents/security_agent.py, agents/corrector_agent.py

## Purpose
Describe how skill execution and hook processing are orchestrated with policy controls and identity context propagation.

## Pipeline Stages
1. Router resolves intent and candidate execution path.
2. Skill registry resolves callable skill/tool handlers.
3. Security and policy hooks are evaluated before sensitive execution.
4. Execution is dispatched with request/session/owner context.
5. Results are post-processed and returned through response safety checks.

## Security Controls
- Endpoint-class and token-profile enforcement before skill execution.
- Sensitive operation confirmation requirements for IoT control paths.
- Structured audit logging for blocked/executed/error outcomes.

## Observability
- Trace metadata includes session and owner context.
- IoT-sensitive action counters and alerts provide control visibility.

## Evidence
- `agents/tools/iot_ops.py`
- `agents/metrics.py`
- `turing_gateway/config/jacquard/auth_alert_rules.yml`
- `tests/test_iot_controls.py`

## Open Follow-Ups
- Extend hook evidence retention and dashboarding for long-window audit analytics.


