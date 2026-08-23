---
title: "Procedure: Key Compromise Incident Runbook"
---

# Key Compromise Incident Runbook

Executable response procedure for suspected compromise of token signing
keys or SPIFFE trust material. For the condensed first-60-minutes on-call
version, see the [Key Compromise Checklist](key-compromise-checklist.md).

!!! danger "Severity: SEV-1"
    Detection-to-containment target: **<= 15 minutes**.
    Detection-to-stable-recovery target: **<= 60 minutes**.

## Scope

Applies to:

1. User-token signing secret compromise (JWT-ACE path).
2. Workload identity trust compromise (SPIFFE/SPIRE path).
3. Suspected key misuse causing abnormal authentication failures.

## Detection Signals

Trigger this runbook when any of these are observed:

1. Sudden sustained increase in 401/403 responses for valid workloads or users.
2. Token validation signature failures spike above baseline.
3. Unexpected issuer/audience mismatches across services.
4. Evidence of leaked secrets, unauthorized key access, or trust-bundle tampering.

## Alert and Monitoring Mapping

Use these monitoring hooks for initial triage and escalation:

1. Prometheus rule file: `turing_gateway/config/prometheus/auth_alert_rules.yml`.
2. Primary detection alert: `AgentRuntimeAuth401RateSpike`.
3. Secondary alerts:
    - `AgentRuntimeAuth403RateSpike`
    - `AgentRuntimeMetricsUnavailable`
    - `AgentRuntimeRequestVolumeDrop`
4. Alert labels include `runbook=docs/security/key_compromise_incident_runbook.md` for direct linkage.
5. Alertmanager path: `turing_gateway/config/alertmanager/alertmanager.yml`.

## 1. Immediate Response (0-5 Minutes)

1. Declare the incident and assign an incident commander (solo mode: operator self-assigns).
2. Capture the incident start timestamp and request ID samples.
3. Freeze key-distribution changes not related to mitigation.
4. Determine the impacted profile:
    - User token key path.
    - SPIFFE/SPIRE trust path.
5. Notify affected stakeholders and activate degraded-mode communications.

## 2. Containment (5-15 Minutes)

1. User token path:
    1. Rotate the JWT signing secret to a new value.
    2. Invalidate the old signing secret acceptance path where possible.
    3. Force a short token TTL and deny stale tokens.
2. SPIFFE path:
    1. Validate trust bundle integrity.
    2. Rotate compromised trust assets via [Rotate SPIRE Keys](rotate-spire-keys.md#emergency-revocation-compromised-node).
    3. Restart/reload impacted agents/services with fresh trust material.
3. Increase auth logging verbosity for forensic capture.
4. Block suspicious source identities if attributable.

## 3. Scope Assessment (15-30 Minutes)

1. Identify the first observed failure timestamp.
2. Quantify impacted endpoints and consumers.
3. Enumerate affected identities (`sub`, `iss`, `aud` clusters).
4. Determine whether misuse occurred or only an operational mismatch.
5. Preserve evidence artifacts (logs, traces, metric snapshots) before cleanup.

## 4. Recovery (30-60 Minutes)

1. Validate the new signing and verification chain in a staging-equivalent path.
2. Roll out the rotation in production in controlled order:
    - Verify downstream verifiers accept the new material.
    - Confirm the old compromised material is rejected.
3. Confirm health:
    - 401/403 rates back to baseline.
    - No signature-mismatch spikes.
    - Critical endpoint smoke checks pass.
4. Exit the incident only after a 30-minute stable monitoring window.

## 5. Rollback Procedure

!!! warning "Use only if recovery introduces outage risk"
    Rolling back reintroduces the compromised material's blast radius —
    only do this if the alternative is a worse outage.

1. Revert to last-known-good key material using a secured backup source.
2. Keep strict issuer/audience pinning active.
3. Keep elevated monitoring active.
4. Document the rollback reason and re-open SEV-1 until permanent remediation.

## Evidence and Logging Requirements

For every incident step, log:

- Timestamp (UTC)
- Action owner (solo: panca)
- Endpoint or subsystem affected
- Expected outcome
- Actual outcome
- Next action

Template:

```text
Timestamp: <UTC>
Step: <runbook step id>
Subsystem: <JWT/SPIFFE/API>
Expected: <expected state>
Actual: <observed state>
Request IDs / Trace IDs: <ids>
Action Taken: <what changed>
Outcome: <pass/fail>
```

## 6. Post-Incident (Within 24 Hours)

1. Publish an incident summary and root-cause analysis.
2. Document control gaps and remediation actions.
3. Update related standards and tests.
4. Schedule a dry-run rehearsal to verify the updated procedure.

## Verification Checklist

- [ ] Detection trigger confirmed and timestamped.
- [ ] Compromised profile identified.
- [ ] Rotated key/trust material deployed.
- [ ] Old compromised material rejected.
- [ ] Endpoint health restored and stable.
- [ ] Evidence package captured.
- [ ] Post-incident action items assigned.

## Related

- [Key Compromise Checklist](key-compromise-checklist.md) — condensed first-60-minutes on-call version
- [Rotate SPIRE Keys](rotate-spire-keys.md) — trust material rotation and emergency revocation steps
- [Configure Alerting](configure-alerting.md) — alert rule and AlertManager setup
- [Disaster Recovery](disaster-recovery.md) — full-system restore flow
