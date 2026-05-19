# Key Lifecycle and Rotation Runbook

Document ID: SEC-KEY-001
Domain: Security
Owner: Security
Reviewers: Platform, Compliance
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/admin/security.md
Related Controls: MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Provide operational procedures for key generation, custody, rotation, revocation, and emergency rollback.

## Key Lifecycle Stages
1. Generate: create key pair in approved secure environment.
2. Store: keep private key in restricted secret store.
3. Publish: expose public key for validators.
4. Rotate: introduce new key with overlap window.
5. Revoke: disable compromised key ID.
6. Retire: remove old key after validation window closes.

## Standard Rotation Procedure
1. Generate new key and assign key ID.
2. Publish new public key while keeping previous key active.
3. Update issuer to sign new tokens with new key ID.
4. Monitor validation success and unknown key errors.
5. After overlap window, remove old key from active set.

## Emergency Key Compromise Procedure
1. Trigger incident and freeze normal releases.
2. Revoke compromised key ID immediately.
3. Rotate to emergency key pair.
4. Force short token TTL until stabilization.
5. Review validation error spikes and containment status.

## Rollback Procedure
1. Re-enable previous known-good key for verification only.
2. Keep issuer and audience checks enforced.
3. Return to soft-enforce validation mode if needed.
4. Exit rollback only after incident review approval.

## Incident Linkage
For suspected compromise scenarios, execute the dedicated incident procedure:
- docs/security/key_compromise_incident_runbook.md
- docs/security/key_compromise_incident_checklist.md

## Verification
1. Rotation dry run quarterly.
2. Compromise simulation semiannually.
3. Validation metrics baseline after each rotation.
