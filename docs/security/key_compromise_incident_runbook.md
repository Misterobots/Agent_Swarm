# Key Compromise Incident Runbook

Document ID: SEC-KEY-002
Domain: Security
Owner: Security
Reviewers: Platform, Compliance, Architecture
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/security/
Related Controls: MAESTRO L3, MAESTRO L6, MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Provide an executable response procedure for suspected compromise of token signing keys or SPIFFE trust material.

## Scope
Applies to:
1. User-token signing secret compromise (JWT-ACE path).
2. Workload identity trust compromise (SPIFFE/SPIRE path).
3. Suspected key misuse causing abnormal authentication failures.

## Severity and SLA
- Severity: SEV-1
- Detection to containment target: <= 15 minutes
- Detection to stable recovery target: <= 60 minutes

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

## Immediate Response (0-5 Minutes)
1. Declare incident and assign incident commander (solo mode: operator self-assigns).
2. Capture incident start timestamp and request ID samples.
3. Freeze key-distribution changes not related to mitigation.
4. Determine impacted profile:
   - User token key path.
   - SPIFFE/SPIRE trust path.
5. Notify affected stakeholders and activate degraded-mode communications.

## Containment (5-15 Minutes)
1. User token path:
   - Rotate JWT signing secret to new value.
   - Invalidate old signing secret acceptance path where possible.
   - Force short token TTL and deny stale tokens.
2. SPIFFE path:
   - Validate trust bundle integrity.
   - Rotate compromised trust assets via SPIRE procedures.
   - Restart/reload impacted agents/services with fresh trust material.
3. Increase auth logging verbosity for forensic capture.
4. Block suspicious source identities if attributable.

## Scope Assessment (15-30 Minutes)
1. Identify first observed failure timestamp.
2. Quantify impacted endpoints and consumers.
3. Enumerate affected identities (`sub`, `iss`, `aud` clusters).
4. Determine whether misuse occurred or only operational mismatch.
5. Preserve evidence artifacts (logs, traces, metric snapshots) before cleanup.

## Recovery (30-60 Minutes)
1. Validate new signing and verification chain in staging-equivalent path.
2. Roll out rotation in production in controlled order:
   - Verify downstream verifiers accept new material.
   - Confirm old compromised material is rejected.
3. Confirm health:
   - 401/403 rates back to baseline.
   - No signature-mismatch spikes.
   - Critical endpoint smoke checks pass.
4. Exit incident only after 30 minutes stable monitoring window.

## Rollback Procedure
Use only if recovery introduces outage risk:
1. Revert to last-known-good key material using secured backup source.
2. Keep strict issuer/audience pinning active.
3. Keep elevated monitoring active.
4. Document rollback reason and re-open SEV-1 until permanent remediation.

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

## Post-Incident (Within 24 Hours)
1. Publish incident summary and root-cause analysis.
2. Document control gaps and remediation actions.
3. Update related standards and tests.
4. Schedule dry-run rehearsal to verify updated procedure.

## Verification Checklist
- [ ] Detection trigger confirmed and timestamped.
- [ ] Compromised profile identified.
- [ ] Rotated key/trust material deployed.
- [ ] Old compromised material rejected.
- [ ] Endpoint health restored and stable.
- [ ] Evidence package captured.
- [ ] Post-incident action items assigned.

## References
- docs/security/key_lifecycle_rotation_runbook.md
- docs/security/identity_token_trust_standard.md
- docs/security/api_authentication_contract.md
- docs/security/key_compromise_incident_checklist.md
