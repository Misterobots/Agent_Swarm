---
title: "Procedure: Key Compromise — First 60 Minutes"
---

# Key Compromise — First 60 Minutes

One-page on-call checklist for the first 60 minutes of a suspected key
compromise. For full context, evidence templates, and rollback procedure,
see the [Key Compromise Incident Runbook](key-compromise-runbook.md).

!!! danger "SEV-1 — declare immediately"
    Any trigger condition below is a SEV-1. Do not wait for confirmation
    before starting containment.

## Trigger Conditions

Use this checklist when any of the following occur:

1. `AgentRuntimeAuth401RateSpike` alert fires.
2. Token signature failures spike in logs or audit telemetry.
3. Unexpected issuer/audience mismatch pattern appears across services.
4. SPIFFE trust-bundle tampering or secret leakage is suspected.

## 0-5 Minutes

1. Declare SEV-1 and self-assign incident commander.
2. Capture UTC timestamp, alert name, and 3 sample request IDs.
3. Identify the profile under suspicion:
    - User signing secret.
    - SPIFFE/SPIRE trust material.
4. Freeze unrelated releases and config changes.
5. Open the full runbook: [Key Compromise Incident Runbook](key-compromise-runbook.md).

## 5-15 Minutes

1. If user-token path:
    1. Rotate the JWT signing secret.
    2. Shorten token TTL.
    3. Confirm the old secret is rejected.
2. If SPIFFE path:
    1. Validate the trust bundle.
    2. Rotate compromised trust assets — see [Rotate SPIRE Keys](rotate-spire-keys.md).
    3. Restart/reload affected services.
3. Increase auth logging verbosity.
4. Notify operators that temporary 401s may occur during containment.

## 15-30 Minutes

1. Query the impact window start time.
2. Enumerate affected `sub`, `iss`, and `aud` clusters.
3. Compare expected traffic to the current 401/403 spike.
4. Preserve logs, traces, and metric screenshots before cleanup.

## 30-60 Minutes

1. Validate the fresh signing and verification chain in a staging-equivalent path.
2. Roll out recovered key/trust material in controlled order.
3. Confirm:
    - 401 rate back to baseline.
    - Signature failures cleared.
    - Critical endpoint smoke tests pass.
4. Keep the incident open until the 30-minute stable window completes.

!!! warning "Don't close the incident early"
    A brief return to baseline is not the same as a stable window. Hold
    the incident open for the full 30 minutes before declaring recovery.

## Evidence Capture

Record:

1. Alert name and firing timestamp.
2. Request/trace IDs sampled.
3. Key rotation or trust update timestamps.
4. Validation result after recovery.
5. Follow-up action items.

## Alert Mapping

1. Prometheus rule file: `turing_gateway/config/prometheus/auth_alert_rules.yml`
2. Primary alert for runbook entry: `AgentRuntimeAuth401RateSpike`
3. Supporting alerts: `AgentRuntimeAuth403RateSpike`, `AgentRuntimeMetricsUnavailable`

## Related

- [Key Compromise Incident Runbook](key-compromise-runbook.md) — full response procedure, evidence template, and rollback
- [Rotate SPIRE Keys](rotate-spire-keys.md) — trust material rotation and emergency revocation steps
- [Configure Alerting](configure-alerting.md) — alert rule and AlertManager setup
