# Key Compromise Incident Checklist

Document ID: SEC-KEY-003
Domain: Security
Owner: Security
Reviewers: Platform, Compliance, Architecture
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/security/key_compromise_incident_runbook.md
Related Controls: MAESTRO L3, MAESTRO L6, MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Provide a one-page on-call checklist for the first 60 minutes of suspected key compromise response.

## Trigger Conditions
Use this checklist when any of the following occur:
1. `AgentRuntimeAuth401RateSpike` alert fires.
2. Token signature failures spike in logs or audit telemetry.
3. Unexpected issuer/audience mismatch pattern appears across services.
4. SPIFFE trust-bundle tampering or secret leakage is suspected.

## 0-5 Minutes
1. Declare SEV-1 and self-assign incident commander.
2. Capture UTC timestamp, alert name, and 3 sample request IDs.
3. Identify profile under suspicion:
   - User signing secret.
   - SPIFFE/SPIRE trust material.
4. Freeze unrelated releases and config changes.
5. Open the full runbook: `docs/security/key_compromise_incident_runbook.md`.

## 5-15 Minutes
1. If user-token path:
   - Rotate JWT signing secret.
   - Shorten token TTL.
   - Confirm old secret is rejected.
2. If SPIFFE path:
   - Validate trust bundle.
   - Rotate compromised trust assets.
   - Restart/reload affected services.
3. Increase auth logging verbosity.
4. Notify operators that temporary 401s may occur during containment.

## 15-30 Minutes
1. Query impact window start time.
2. Enumerate affected `sub`, `iss`, and `aud` clusters.
3. Compare expected traffic to current 401/403 spike.
4. Preserve logs, traces, and metric screenshots before cleanup.

## 30-60 Minutes
1. Validate fresh signing and verification chain in staging-equivalent path.
2. Roll out recovered key/trust material in controlled order.
3. Confirm:
   - 401 rate back to baseline.
   - Signature failures cleared.
   - Critical endpoint smoke tests pass.
4. Keep incident open until 30-minute stable window completes.

## Evidence Capture
Record:
1. Alert name and firing timestamp.
2. Request/trace IDs sampled.
3. Key rotation or trust update timestamps.
4. Validation result after recovery.
5. Follow-up action items.

## Alert Mapping
1. Prometheus rule file: `r730_gateway/config/prometheus/auth_alert_rules.yml`
2. Primary alert for runbook entry: `AgentRuntimeAuth401RateSpike`
3. Supporting alerts: `AgentRuntimeAuth403RateSpike`, `AgentRuntimeMetricsUnavailable`