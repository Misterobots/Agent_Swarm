# Feature and Capability Documentation Standard

Document ID: DOC-GOV-002  
Domain: Governance  
Owner: Architecture  
Reviewers: Platform, Operations, Compliance  
Status: Approved  
Version: 1.0  
Last Updated: 2026-08-13  
Review Due: 2026-09-13  
Source of Truth: docs/  
Related Controls: MAESTRO L2, MAESTRO L6, MAESTRO L7  
Related Evidence: docs/evidence/  
Supersedes: None

## Purpose

Define the standard structure for documenting a capability as it moves from idea to live operation. The goal is to keep implementation, configuration, user behavior, limitations, and verification connected without duplicating the source code.

Use the template at [`docs/templates/feature_capability_template.md`](../templates/feature_capability_template.md).

## One Capability, One Canonical Document

Every material capability must have one canonical capability document. That document links outward to code, configuration, ADRs, runbooks, and evidence; those artifacts must not become competing descriptions of current behavior.

A capability document is required when a change does any of the following:

1. Spans more than one service, host, integration, or user surface.
2. Adds configuration, deployment, permissions, or an external dependency.
3. Creates behavior an operator or user needs to understand.
4. Has meaningful fallback, degraded, failure, privacy, or security behavior.
5. Is likely to be extended later.

Small internal refactors need only code comments and tests unless they alter an existing capability contract.

## Required Structure

Each capability document must include:

1. Governance metadata from `DOC-GOV-001`.
2. Capability summary and current status.
3. User-visible behavior, including supported phrases or workflows where relevant.
4. Component and data flow.
5. Source-of-truth files.
6. Configuration contract, including defaults and secrets handling.
7. Resolution or selection rules when behavior depends on a user, device, area, model, or tenant.
8. Success, fallback, degraded, and failure behavior.
9. Security and privacy boundaries.
10. Deployment and rollback procedure.
11. Verification evidence and known limitations.
12. Extension procedure and open decisions.
13. Change log.

## Status Vocabulary

Use these terms consistently:

- **Planned**: accepted scope, implementation not started.
- **Implemented**: code exists but has not been exercised in its target environment.
- **Deployed**: target environment is running the implementation.
- **Verified**: named behavior was observed end to end, with date and evidence.
- **Degraded**: operational with a documented limitation or dependency failure.
- **Disabled**: intentionally unavailable through configuration or feature gate.
- **Retired**: no longer supported; document points to its replacement.

Do not use “complete” without stating what was verified.

## Relationship to Other Documents

- **ADR**: why a consequential or costly-to-reverse design was selected.
- **Capability document**: what the system currently does and how to extend it.
- **Runbook**: exact operational response to deploy, recover, or troubleshoot.
- **User guide**: task-oriented instructions without internal architecture.
- **Evidence record**: dated observation proving a specific claim.
- **Code comment**: local implementation constraint that would be unsafe to separate from code.

Create an ADR in addition to the capability document when the change meets the criteria in [`docs/decisions/ADR_INDEX.md`](../decisions/ADR_INDEX.md).

## Source-of-Truth Rules

1. Runtime values and secrets remain in deployment configuration, not documentation.
2. The capability document names environment variables and safe examples, but does not copy secrets.
3. Code remains authoritative for implementation details; documentation describes contracts and intent.
4. Live topology is governed by `AGENTS.md` until the infrastructure catalog has been reconciled with it.
5. A statement about production must include `Deployed` or `Verified`, plus a date.
6. Superseded documents must link to their replacement and must not be silently left active.

## Definition of Done

A material feature is not documentation-complete until:

- Its canonical capability document exists or was updated.
- It is linked from `docs/INDEX.md`.
- Configuration additions are documented.
- Failure and fallback behavior are explicit.
- Verification steps are reproducible.
- Known limitations and next decisions are recorded.
- Review date and owner are assigned.

## Maintenance Workflow

During implementation:

1. Create the capability document as `Draft` from the template.
2. Record contracts and unresolved decisions before deployment.
3. Update it to `Implemented` when code lands.
4. Record the deployment target and date when deployed.
5. Add a dated evidence record or concise verification entry after end-to-end testing.
6. Review the document in the same change whenever source-of-truth files or configuration change.

Monthly review should focus on architecture and implementation contracts. Quarterly review should confirm user workflows and operational instructions still match live behavior.

