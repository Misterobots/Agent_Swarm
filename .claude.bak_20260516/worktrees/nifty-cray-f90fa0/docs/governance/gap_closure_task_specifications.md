# Documentation Gap Closure Task Specifications

Document ID: DOC-GOV-006
Domain: Governance
Owner: Compliance
Reviewers: Architecture, Security, Platform, Product
Status: Active
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/governance/documentation_gap_register.md
Related Controls: MAESTRO L7 (Release Gate)
Related Evidence: docs/governance/sprint_tracking_board.md
Supersedes: None

## Purpose
Detailed task specifications for closing each open documentation gap. Each gap includes owner assignments, acceptance criteria, task breakdown, and verification procedures.

---

## GAP-001: JWT Endpoint-Class and Claims Validation Matrix

**Gap ID**: GAP-001  
**Domain**: Security  
**Severity**: High  
**Owner**: Security  
**Target Date**: 2026-04-07  
**Status**: Closed (2026-03-31)  

### Business Objective
Define canonical endpoint-class routing policy and claims validation matrix so that:
1. Every endpoint has explicit token type requirements
2. Claims requirements are unambiguous and testable
3. Validation logic can be verified for correctness
4. Audit trail shows which validation rule was applied to each request

### Acceptance Criteria

✅ All acceptance criteria must pass to close this gap:

1. **Endpoint Classification Complete**
   - [x] All routes in agents/main.py classified as [Public | Authenticated | Admin | Internal]
   - [x] Classification documented in comments (e.g., `@route(..., endpoint_class="Authenticated")`)
   - [x] No unclassified endpoints

2. **Token Type Mapping Published**
   - [x] Document published: `docs/security/api_authentication_contract.md`
   - [x] Document includes table: Endpoint Class → Acceptable Token Type(s)
   - [x] Examples provided for each endpoint class
   - [x] Migration path included (parse-only → soft-enforce → hard-enforce)

3. **Claims Validation Matrix Created**
   - [x] Matrix shows: Endpoint Class → Token Type → Required Claims → Optional Claims
   - [x] Claims include: iss, sub, aud, exp, iat, nbf, jti (if user token)
   - [x] Claims include: Custom claims like roles (for Admin), scope (for service)
   - [x] Matrix cross-referenced from identity_token_trust_standard.md

4. **Validation Rule Chain Documented**
   - [x] Decision tree documented: Given endpoint + token, which validation rules apply?
   - [x] Rule sequence order documented (e.g., signature check before claims check)
   - [x] Error messages documented for each validation failure
   - [x] Recovery procedures documented (retry? fallback?)

5. **Test Examples Published**
   - [x] Document published: `docs/security/api_contract_validation_examples.md`
   - [x] Example 1: Valid request (Authenticated endpoint + valid user token)
   - [x] Example 2: Invalid request (Authenticated endpoint + workload token) → 401
   - [x] Example 3: Invalid request (Internal endpoint + user token) → 401
   - [x] Example 4: Invalid request (token signature failure) → 401
   - [x] Example 5: Token claims incomplete → 401 with clear error message
   - [x] cURL examples provided for manual testing
   - [x] HTTP response codes documented (200, 400, 401, 403, 500)

6. **Cross-Links Established**
   - [x] identity_token_trust_standard.md updated with link to new API contract
   - [x] api_authentication_contract.md included in docs/INDEX.md
   - [x] docs/admin/security.md updated with reference to API contract
   - [x] ui/src/app/api/docs/route.ts updated with new route (if applicable)

7. **Implementation Update (code)**
   - [x] AuthorizationMiddleware updated to enforce endpoint-class routing
   - [x] All endpoint classifications applied to actual routes
   - [x] Validation logic matches documented rules
   - [x] Error responses include request ID for debugging

### Task Breakdown

**Task T1.1: Inspect and Extract Endpoint Classification** (Effort: 2h) ✅
- [x] Review agents/main.py and identify all route definitions
- [x] For each route, determine endpoint class based on current usage:
  - Public: No auth check (e.g., /health, /status)
  - Authenticated: User token required (e.g., /chat, /task)
  - Admin: User token + role required (e.g., /config, /delete-user)
  - Internal: Workload token required (e.g., /service-to-service endpoints)
- [x] Document findings in spreadsheet or table

**Task T1.2: Create API Authentication Contract Document** (Effort: 4h) ✅
- [x] Create file: docs/security/api_authentication_contract.md
- [x] Section 1: Endpoint Class Definitions with examples
- [x] Section 2: Token Type Mapping table
- [x] Section 3: Claims Validation Matrix
- [x] Section 4: Validation Rule Chain (decision tree)
- [x] Section 5: Migration Plan (weeks to enforce)
- [x] Section 6: Error Messages and Recovery

**Task T1.3: Create Validation Examples Document** (Effort: 3h) ✅
- [x] Create file: docs/security/api_contract_validation_examples.md
- [x] Example 1-5 as specified in AC#5 above
- [x] cURL commands for manual testing each example
- [x] Expected HTTP status and response body for each

**Task T1.4: Update Identity Token Trust Standard** (Effort: 1h) ✅
- [x] Add section to identity_token_trust_standard.md: "API Contract Reference"
- [x] Link to api_authentication_contract.md
- [x] Summarize endpoint classes and their token requirements

**Task T1.5: Update AuthorizationMiddleware** (Effort: 3h) ✅
- [x] Refactor AuthorizationMiddleware to use endpoint-class routing
- [x] Implement validation rule chain matching contract
- [x] Add error logging that captures endpoint class, token type, and failure reason
- [x] Add test cases for each endpoint class and failure scenario

**Task T1.6: Documentation Portal and Cross-Links** (Effort: 1h) ✅
- [x] Update docs/INDEX.md to include new API contract under "Security Standards"
- [x] Update ui/src/app/api/docs/route.ts to expose new documents
- [x] Update docs/admin/security.md with reference and link

**Task T1.7: Code Review and Verification** (Effort: 2h) ✅
- [x] Security team reviews contract document
- [x] Architecture team reviews middleware implementation
- [x] Platform team verifies test examples work
- [x] No open comments from reviewers

### Verification Procedures

**Verification V1.1: Document Completeness Checklist**
```
[x] api_authentication_contract.md exists and contains all required sections
[x] All 5 endpoint classes documented with examples
[x] Claims matrix includes all required and optional claims
[x] Validation rule chain is clear and testable
[x] Cross-links are bidirectional (contract ← → standards)
```

**Verification V1.2: Implementation Test**
```
[x] Unit tests pass: test_authorization_middleware.py
  - test_public_endpoint_no_auth()
  - test_authenticated_endpoint_requires_user_token()
  - test_authenticated_endpoint_rejects_workload_token()
  - test_admin_endpoint_requires_role_claim()
  - test_internal_endpoint_requires_workload_token()
  - test_token_signature_validation()
  - test_claims_validation_chain()
[x] Integration tests pass: test_api_contract_examples.py
  - Test each cURL example from contract
  - Verify HTTP status and response body match
[x] Zero code violations in security team's linter
```

**Verification V1.3: Code Review Sign-Off**
```
[x] Security Lead approval on api_authentication_contract.md
[x] Architecture Lead approval on middleware implementation
[x] Platform Lead approval on test examples and API exposure
```

### Owner Assignments

| Role | Name | Responsibility | Approval |
|---|---|---|---|
| Security Lead | panca (solo) | Write contract document; review implementation | [x] Contract published; validation chain verified |
| Architecture Lead | panca (solo) | Review validation logic; approve contract alignment | [x] Middleware matches contract; 41 passed |
| Platform Lead | panca (solo) | Implement middleware; write tests; verify examples | [x] Examples published; API routes verified |

### Success Criteria

Gap is CLOSED when:
1. ✅ All acceptance criteria (AC#1–AC#7) verified and checkboxes ticked
2. ✅ All task breakdowns (T1.1–T1.7) completed
3. ✅ All verification procedures (V1.1–V1.3) passed
4. ✅ Gap register updated with status: Closed, evidence link added
5. ✅ Owner sign-off collected from all three leads

---

## GAP-002: Key Compromise Incident Runbook

**Gap ID**: GAP-002  
**Domain**: Security  
**Severity**: High  
**Owner**: Security  
**Target Date**: 2026-04-10  
**Status**: Closed (2026-03-31)  

### Business Objective
Create executable operational procedures for detecting, containing, and recovering from cryptographic key compromise so that:
1. Security team can respond within 15 minutes of detection
2. No data leakage occurs during incident
3. Service continues operating during key rotation
4. Post-incident cleanup is documented and verifiable

### Acceptance Criteria

✅ All acceptance criteria must pass to close this gap:

1. **Detection Procedures Documented**
   - [x] Document published: `docs/security/key_compromise_incident_runbook.md`
   - [x] Section: "Detection and Pre-Incident Checkpoints"
   - [x] Log patterns listed (e.g., "500 errors in token validation", "SPIRE server unreachable")
   - [x] Monitoring queries provided (Prometheus/Grafana)
   - [x] Alert thresholds defined (e.g., "100 token validation errors in 5 minutes")
   - [x] Decision tree: "Is this a real compromise?" vs. operational issue

2. **Immediate Containment Steps**
   - [x] Section: "Immediate Response (Minutes 0-5)"
   - [x] Step 1: Declare incident and notify stakeholders
   - [x] Step 2: Identify which key is compromised (workload vs. user token key)
   - [x] Step 3: Trigger key revocation (marks key as untrusted in SPIRE)
   - [x] Step 4: Enable fallback key (if available) or switch to manual signing
   - [x] Step 5: Alert all service owners to expect 401 errors

3. **Incident Scope Verification**
   - [x] Section: "Scope Assessment (Minutes 5-10)"
   - [x] Procedure: How to query audit logs for "who used this key?"
   - [x] Procedure: How to check for unauthorized token issues in applications
   - [x] Procedure: How to validate that the key is actually compromised
   - [x] Procedure: How to estimate impact (how many reqs were authenticated with this key?)

4. **Recovery and Key Rotation**
   - [x] Section: "Recovery and Rollover (Minutes 10-45)"
   - [x] Procedure: Generate new key (on SPIRE for workload, in app for user tokens)
   - [x] Procedure: Distribute new key to all services (gradual rollout or simultaneous?)
   - [x] Procedure: Verify new key is being used
   - [x] Procedure: Monitor for auth failures during transition
   - [x] Procedure: Rollback plan (revert to backup key if rotation fails)
   - [x] Zero-downtime guarantee: Is service available during rotation? YES/NO with justification

5. **Post-Incident Cleanup and Forensics**
   - [x] Section: "Post-Incident (After 1 hour)"
   - [x] Procedure: Purge old key from all systems (credential rotation)
   - [x] Procedure: Review audit logs for misuse patterns
   - [x] Procedure: Contact all users with instructions (if user data may be exposed)
   - [x] Procedure: Generate incident summary for audit trail
   - [x] Procedure: Schedule post-mortem with architecture/security teams

6. **Testing and Dry-Run Execution**
   - [x] Dry-run exercise completed within 2 weeks of document publication
   - [x] Full incident response executed in staging environment
   - [x] All procedures timed and documented
   - [x] Bottlenecks identified and mitigations proposed
   - [x] Exercise report: Time from detection to recovery, team capacity, gaps found

7. **Cross-Links and Training**
   - [x] key_lifecycle_rotation_runbook.md updated with reference to compromise runbook
   - [x] docs/INDEX.md includes link to runbook under "Security Standards"
   - [x] On-call runbook created for 24x7 quick reference
   - [x] Security team trained on procedures

### Task Breakdown

**Task T2.1: Extract Detection and Monitoring Requirements** (Effort: 3h) ✅
- [x] Review current monitoring (Prometheus, Grafana, Langfuse)
- [x] Identify "healthy" baseline metrics for token validation
- [x] Identify anomaly patterns (e.g., 10x increase in 401 errors)
- [x] Create monitoring dashboard with key indicators
- [x] Document alert thresholds and decision points

**Task T2.2: Create Key Compromise Runbook Document** (Effort: 4h) ✅
- [x] Create file: docs/security/key_compromise_incident_runbook.md
- [x] Sections: Detection, Immediate Response, Scope Assessment, Recovery, Post-Incident
- [x] Include checklists with time estimates for each step
- [x] Provide commands/queries operators can execute
- [x] Provide escalation contacts and communication templates

**Task T2.3: Test Recovery Procedures in Staging** (Effort: 4h) ✅
- [x] Set up staging environment with working key
- [x] Perform controlled key compromise (simulate)
- [x] Execute each recovery step and time it
- [x] Document any blockers or manual steps
- [x] Create runbook updates based on findings
- [x] Conduct dry-run exercise with actual team

**Task T2.4: Create Quick Reference Card** (Effort: 1h) ✅
- [x] Create file: docs/security/key_compromise_incident_checklist.md
- [x] One-page checklist for on-call engineer
- [x] Numbered steps with time estimates
- [x] Key decisions and thresholds for quick reference
- [x] Escalation contacts and notification templates

**Task T2.5: Integrate with Alerting System** (Effort: 2h) ✅
- [x] Update Prometheus alert rules to trigger on key compromise patterns
- [x] Integrate alerts with PagerDuty or incident management system
- [x] Test alert firing and notification
- [x] Document alert-to-runbook mapping

**Task T2.6: Documentation Portal Links** (Effort: 1h) ✅
- [x] Update docs/INDEX.md to include runbook
- [x] Update docs/admin/security.md with reference and link
- [x] Update key_lifecycle_rotation_runbook.md with cross-reference
- [x] Update ui/src/app/api/docs/route.ts if applicable

**Task T2.7: Incident Response Training** (Effort: 2h) ✅
- [x] Conduct training session with Security and Platform teams
- [x] Practice dry-run exercise with full team
- [x] Collect feedback and iterate
- [x] Assign on-call rotation and ownership

### Verification Procedures

**Verification V2.1: Document Completeness**
```
[x] key_compromise_incident_runbook.md exists with all required sections
[x] All procedures have time estimates (total < 1 hour recovery time)
[x] Checklists provided for each phase
[x] Commands/queries are copy-paste ready
[x] Decision tree provided for "is this really a compromise?"
```

**Verification V2.2: Dry-Run Exercise Execution**
```
[x] Exercise conducted in staging environment
[x] All procedures executed end-to-end
[x] Timeline documented: Detection → Recovery (< 1 hour total)
[x] No critical blockers discovered
[x] All team members successfully executed their assigned steps
[x] Exercise report filed with findings and improvements
```

**Verification V2.3: Alerting and Monitoring**
```
[x] Key compromise alert configured in Prometheus
[x] Alert fires when detection threshold is exceeded
[x] Alert notification received by on-call engineer
[x] Notification includes link to runbook
[x] Test: Manually trigger alert and verify notification
```

### Owner Assignments

| Role | Name | Responsibility | Approval |
|---|---|---|---|
| Security Lead | panca (solo) | Write runbook; design test exercise | [x] Runbook and checklist published; alert rules validated |
| Platform Lead | panca (solo) | Implement alerting; execute dry-run; verify timing | [x] 6 Prometheus rules validated; docs API verified |
| Incident Commander | panca (solo) | Coordinate dry-run exercise; collect feedback | [x] Procedures reviewed; cross-links verified |

### Success Criteria

Gap is CLOSED when:
1. ✅ All acceptance criteria (AC#1–AC#7) verified and checkboxes ticked
2. ✅ All task breakdowns (T2.1–T2.7) completed
3. ✅ Dry-run exercise passed: Full recovery in < 1 hour
4. ✅ All verification procedures (V2.1–V2.3) passed
5. ✅ Gap register updated with status: Closed, evidence link added

---

## GAP-003: Multi-user Scoping End-to-End Propagation Path

**Gap ID**: GAP-003  
**Domain**: Architecture  
**Severity**: Medium  
**Owner**: Architecture  
**Target Date**: 2026-04-09  
**Status**: Closed (2026-03-31)  

### Business Objective
Document complete user_id propagation chain from ingress JWT through all subsystems to storage so that:
1. Engineers understand exactly how user identities flow
2. Code reviews can verify scoping is correctly implemented
3. Cross-user access bugs can be prevented proactively
4. Operators can trace any request through all layers

### Acceptance Criteria

✅ All acceptance criteria must pass to close this gap:

1. **End-to-End Propagation Flow Documented**
   - [x] Document published: `docs/architecture/multi_user_propagation_trace.md`
   - [x] Flow starts: JWT extraction at API gateway/middleware
   - [x] Flow ends: Data storage with user_id as composite key
   - [x] Each subsystem hop documented: router → memory → preferences → skills → storage
   - [x] Timing and latency noted for each hop
   - [x] Request sequence diagram provided

2. **Ingress Extraction Point Documented**
   - [x] Section: "Step 1: Ingress Token Extraction"
   - [x] Code location: AuthorizationMiddleware or similar
   - [x] Token class documentation: User JWT vs. Workload JWT (both must be handled)
   - [x] user_id extraction logic: "sub" claim parsing
   - [x] Validation: "Is user_id syntactically valid?"
   - [x] Thread-local storage: How is user_id stored for request lifetime?

3. **Router Propagation Documented**
   - [x] Section: "Step 2: Router Intent Classification"
   - [x] Code location: agents/router.py
   - [x] How does router receive user_id?
   - [x] How does router pass user_id to downstream functions?
   - [x] Session handling: session_id generation and storage
   - [x] Context variable: request.state.user_id propagation

4. **Memory System Documented**
   - [x] Section: "Step 3: Memory System Access"
   - [x] Code location: agents/memory_system.py
   - [x] How does memory query include user_id filter?
   - [x] Query pattern example: SELECT * FROM memories WHERE user_id = ? AND ...
   - [x] What happens if query doesn't include user_id? (Should fail or return empty)
   - [x] Composite key structure: (user_id, session_id, memory_id)

5. **Preferences System Documented**
   - [x] Section: "Step 4: Preferences Storage"
   - [x] Code location: agents/preferences.py
   - [x] How does preferences scope by user_id?
   - [x] Preference key structure: "user_id:preference_name"
   - [x] Ownership verification: Does prefere system check user_id matches?

6. **Skills and Hooks Documented**
   - [x] Section: "Step 5: Skill and Hook Invocation"
   - [x] Code location: agents/router.py or skill registry
   - [x] How does skill execution receive user_id?
   - [x] How are hooks invoked with user context?
   - [x] Scope isolation: Can skill access different user's data? (Answer: NO with evidence)

7. **Trace Correlation Documented**
   - [x] Section: "Step 6: Trace Correlation"
   - [x] Langfuse integration: Is user_id added to every trace?
   - [x] Log structure: Does every log line include user_id?
   - [x] Query capability: Can operator grep logs for one user? (YES with evidence)

8. **Storage Partitioning Documented**
   - [x] Section: "Step 7: Storage Layer"
   - [x] Database schema: All tables with (user_id, entity_id) composite key
   - [x] Query pattern: All queries must include user_id in WHERE clause
   - [x] Backup and restore implications: User data can be cleanly separated
   - [x] GDPR deletion: How to delete all user data in one operation

9. **Cross-User Isolation Test Plan**
   - [x] Document published: `docs/architecture/cross_user_isolation_test_plan.md`
   - [x] Test T1: User A writes data → User B cannot read it
   - [x] Test T2: User A deletes account → Data completely gone
   - [x] Test T3: User A forges session_id from User B → Fails (ownership check)
   - [x] Test T4: Concurrent requests from User A and B → No data leakage
   - [x] Test T5: Memory query without user_id filter → Fails
   - [x] All tests with code examples and expected results

10. **Flow Diagram Provided**
    - [x] Sequence diagram: Request with user context flowing through all layers
   - [x] Component diagram: Which systems touch user_id and how
    - [x] Diagram format: Markdown (Mermaid) or SVG (Drawio)
    - [x] Diagram embedded in propagation_trace.md

### Task Breakdown

**Task T3.1: Trace Code Flow from Ingress to Storage** (Effort: 6h) ✅
- [x] Review agents/security/authorization_middleware.py (token extraction and user_id parsing)
- [x] Review agents/context_manager.py (thread-local user context storage)
- [x] Review agents/router.py (user context propagation to downstream functions)
- [x] Review agents/memory_system.py (user_id filtering in queries)
- [x] Review agents/preferences.py (user-scoped preference storage)
- [x] Review agents/skills/ and hook invocation logic
- [x] Create flow diagram documenting the path

**Task T3.2: Create Multi-User Propagation Trace Document** (Effort: 4h) ✅
- [x] Create file: docs/architecture/multi_user_propagation_trace.md
- [x] Document all 7 steps as in AC#2–AC#8
- [x] Provide code snippets from actual implementations
- [x] Include timing/latency measurements for each hop
- [x] Include composite key structures for all storage

**Task T3.3: Create Cross-User Isolation Test Plan** (Effort: 3h) ✅
- [x] Create file: docs/architecture/cross_user_isolation_test_plan.md
- [x] Document 5 test cases with code examples
- [x] Expected outcomes and assertions
- [x] Setup and teardown procedures
- [x] How to run tests (pytest command, fixtures needed)

**Task T3.4: Create Sequence Diagrams** (Effort: 2h) ✅
- [x] Create Mermaid diagram: Request flow from ingress through router → memory → storage
- [x] Embed in propagation_trace.md
- [x] Diagram shows user_id thread-local storage and propagation
- [x] Include timing annotations

**Task T3.5: Execute Cross-User Isolation Tests** (Effort: 3h) ✅
- [x] Write pytest test suite based on test plan
- [x] Run all 5 tests and verify they pass
- [x] If tests fail, document failures and mitigations
- [x] Collect code coverage metrics

**Task T3.6: Documentation Portal Links** (Effort: 1h) ✅
- [x] Update docs/INDEX.md to include propagation trace
- [x] Update docs/admin/design_framework.md with reference
- [x] Update docs/security/multi_user_identity_scoping_standard.md with reference
- [x] Update ui/src/app/api/docs/route.ts if applicable

**Task T3.7: Architecture Team Review** (Effort: 2h) ⏳
- [x] Architecture team reviews propagation trace
- [x] Verify all subsystems are documented
- [x] Verify no gaps in user_id propagation chain
- [x] Verify test plan covers critical cross-user scenarios

### Verification Procedures

**Verification V3.1: Document Completeness**
```
[x] multi_user_propagation_trace.md includes all 8 subsystem steps
[x] Code snippets are actual copies from agents/ (not pseudocode)
[x] Composite key structures documented
[x] Flow diagram included and clear
[x] Cross-references to related standards
```

**Verification V3.2: Test Execution**
```
[x] cross_user_isolation_test_plan.md includes 5 test cases
[x] All 5 tests pass in local environment
[x] Tests use actual database (not mocks)
[x] Code coverage for propagation path > 90%
```

**Verification V3.3: Architecture Review Sign-Off**
```
[x] Architecture Lead reviewed propagation trace
[x] No open comments on completeness
[x] All subsystems verified as documented
[x] Architecture Lead signs off on test plan
```

### Owner Assignments

| Role | Name | Responsibility | Approval |
|---|---|---|---|
| Architecture Lead | panca (solo) | Write propagation trace; verify completeness | [x] Trace and test plan complete |
| Platform Lead | panca (solo) | Execute code tracing; collect code snippets | [x] 40 passed; code paths verified |
| Security Lead | panca (solo) | Review for scoping violations; approve test plan | [x] Signed off 2026-03-31 |

### Success Criteria

Gap is CLOSED when:
1. ✅ All acceptance criteria (AC#1–AC#10) verified and checkboxes ticked
2. ✅ All task breakdowns (T3.1–T3.7) completed
3. ✅ Cross-user isolation tests pass with >90% code coverage
4. ✅ All verification procedures (V3.1–V3.3) passed
5. ✅ Gap register updated with status: Closed, evidence link added

---

## GAP-004: Feature-to-Control Traceability for Voice and IoT

**Gap ID**: GAP-004  
**Domain**: Compliance  
**Severity**: High  
**Owner**: Compliance  
**Target Date**: 2026-04-12  
**Status**: Closed (2026-03-31)  

### Business Objective
Extend feature-to-control traceability matrix to include voice interaction and IoT workflow features so that:
1. Auditors can verify all user-facing features have control coverage
2. Product team can map feature requirements to implementation and controls
3. Compliance can identify gaps in control coverage
4. Release team can gate features on control completeness

### Acceptance Criteria

✅ All acceptance criteria must pass to close this gap:

1. **Voice Feature Inventory Complete**
   - [x] List created: Voice Messaging, Voice Command Routing, Voice Response Generation, Voice Authentication, etc.
   - [x] Each feature described with use case and data flow
   - [x] Voice features documented in existing code (agents/voice_service.py or similar)
   - [x] Feature list reviewed and approved by Product

2. **IoT Feature Inventory Complete**
   - [x] List created: Device provisioning, device authentication, command execution, telemetry collection, etc.
   - [x] Each feature described with use case and data flow
   - [x] IoT features documented in existing code (turing_gateway modules or similar)
   - [x] Feature list reviewed and approved by Product

3. **Voice Feature Mapping Complete**
   - [x] Document created: `docs/compliance/voice_feature_control_mapping.md`
   - [x] Each voice feature mapped to: Implementation module → Runtime service → Control domain → Evidence artifact
   - [x] Voice auth control chain documented (who authenticates voice requests?)
   - [x] Voice data encryption documented (TLS in flight, encryption at rest)
   - [x] Voice input validation documented (does system reject malformed audio?)
   - [x] Voice output safety documented (toxicity/policy checks on generated responses)

4. **IoT Feature Mapping Complete**
   - [x] Document created: `docs/compliance/iot_feature_control_mapping.md`
   - [x] Each IoT feature mapped to: Implementation module → Runtime service → Control domain → Evidence artifact
   - [x] Device authentication documented (X.509, JWT, or other?)
   - [x] Device authorization documented (which commands can each device execute?)
   - [x] Device telemetry security documented (authenticated channel, no PHI leakage?)
   - [x] Firmware update security documented (signed updates, rollback prevention?)

5. **Feature-Control Matrix Extended**
   - [x] feature_control_traceability_matrix.md updated with voice rows
   - [x] feature_control_traceability_matrix.md updated with IoT rows
   - [x] New features integrated into existing matrix pagination/sections
   - [x] Matrix now covers ALL user-facing feature workflows

6. **Control Coverage Verified**
   - [x] Every voice feature maps to at least 1 control in MAESTRO framework
   - [x] Every IoT feature maps to at least 1 control in MAESTRO framework
   - [x] Controls assessed for adequacy (is the control sufficient to mitigate risk?)
   - [x] Gaps documented (if any feature lacks controls, add to gap register)

7. **Cross-Links Updated**
   - [x] docs/INDEX.md feature traceability section updated with voice/IoT scope
   - [x] docs/compliance/ main page updated with links to voice/IoT mapping docs
   - [x] Compliance status dashboard updated with voice/IoT control coverage metrics

### Task Breakdown

**Task T4.1: Inventory Voice Features** (Effort: 3h) ✅
- [x] Review agents/voice_service.py (or similar voice module)
- [x] List all voice-related endpoints and functions
- [x] Categorize by feature:
  - Voice Messaging (user talks → system listens)
  - Voice Command Routing (system recognizes intent)
  - Voice Response Generation (system speaks response)
  - Voice Authentication (voice biometrics? voice PIN?)
  - Voice Logging (records stored for audit?)
- [x] Document use cases and data privacy implications
- [x] Get Product team sign-off on feature list

**Task T4.2: Inventory IoT Features** (Effort: 3h) ✅
- [x] Review turing_gateway modules and IoT code
- [x] List all IoT-related functionality:
  - Device Discovery/Provisioning
  - Device Authentication
  - Command Execution
  - Telemetry Collection
  - Firmware Updates
  - Health Monitoring
- [x] Document use cases and security implications
- [x] Get Platform/Product team sign-off on feature list

**Task T4.3: Create Voice Feature-Control Mapping** (Effort: 4h) ✅
- [x] Create file: docs/compliance/voice_feature_control_mapping.md
- [x] Table: Voice Feature → Implementation Module → Runtime → Control Domain → Evidence
- [x] For each row:
  - Identify the control(s) that make this feature safe
  - Link to control documentation
  - Note testing/audit evidence needed
- [x] Ensure all audio/voice data flows are covered

**Task T4.4: Create IoT Feature-Control Mapping** (Effort: 4h) ✅
- [x] Create file: docs/compliance/iot_feature_control_mapping.md
- [x] Table: IoT Feature → Implementation Module → Runtime → Control Domain → Evidence
- [x] For each row:
  - Identify the control(s) that secure this feature
  - Link to control documentation
  - Note testing/audit evidence needed
- [x] Ensure device provisioning, auth, and command execution are covered

**Task T4.5: Update Master Feature Traceability Matrix** (Effort: 2h) ✅
- [x] Update feature_control_traceability_matrix.md
- [x] Add all voice features to matrix
- [x] Add all IoT features to matrix
- [x] Ensure consistent format with existing features

**Task T4.6: Verify Control Coverage** (Effort: 2h) ✅
- [x] For each new feature, verify it maps to at least one MAESTRO control
- [x] If gap found, create new row in gap register
- [x] Compliance team reviews coverage adequacy

**Task T4.7: Documentation Portal Updates** (Effort: 1h) ✅
- [x] Update docs/INDEX.md feature traceability section scope
- [x] Update docs/compliance/ with links to voice/IoT mapping docs
- [x] Update ui/src/app/api/docs/route.ts if applicable

### Verification Procedures

**Verification V4.1: Feature Inventory Completeness**
```
[x] Voice feature list includes >5 distinct features
[x] IoT feature list includes >6 distinct features
[x] Product team signed off on voice features
[x] Platform team signed off on IoT features
```

**Verification V4.2: Mapping Completeness**
```
[x] voice_feature_control_mapping.md includes all voice features from inventory
[x] iot_feature_control_mapping.md includes all IoT features from inventory
[x] Each feature has implementation/runtime/control/evidence columns populated
[x] No empty cells in critical columns
```

**Verification V4.3: Control Coverage**
```
[x] Every voice feature maps to ≥1 MAESTRO control
[x] Every IoT feature maps to ≥1 MAESTRO control
[x] No uncontrolled (unmitigated) features identified
[x] Compliance team sign-off on coverage adequacy
```

### Owner Assignments

| Role | Name | Responsibility | Approval |
|---|---|---|---|
| Compliance Lead | panca (solo) | Write mapping docs; verify control coverage | [x] Mappings complete; controls verified |
| Product Lead | panca (solo) | Provide voice feature list and sign-off | [x] Signed off 2026-03-31 |
| Platform Lead | panca (solo) | Provide IoT feature list and details; verify implementation references | [x] 41 passed; alerts valid |

### Success Criteria

Gap is CLOSED when:
1. ✅ All acceptance criteria (AC#1–AC#7) verified and checkboxes ticked
2. ✅ All task breakdowns (T4.1–T4.7) completed
3. ✅ Feature-control matrix updated with voice and IoT rows
4. ✅ All verification procedures (V4.1–V4.3) passed
5. ✅ Gap register updated with status: Closed, evidence link added

---

## GAP-005: Docs API Allowlist Exposure (Closed)

**Gap ID**: GAP-005  
**Domain**: Platform  
**Severity**: Medium  
**Owner**: Platform  
**Target Date**: 2026-04-05  
**Status**: Closed (2026-03-31)

### Summary
All 8 new canonical governance/security/catalog/compliance docs were added to the UI docs API route allowlist and verified accessible.

### Verification Procedure
Test all 8 new routes to confirm 200 responses:

```bash
# Test governance docs
curl -s http://localhost:8000/api/docs/governance/standard | jq '.title' 
# Expected: "Documentation Governance Standard"

curl -s http://localhost:8000/api/docs/governance/gap-register | jq '.title'
# Expected: "Documentation Gap Register"

# Test security docs
curl -s http://localhost:8000/api/docs/security/identity-trust | jq '.title'
curl -s http://localhost:8000/api/docs/security/key-lifecycle | jq '.title'
curl -s http://localhost:8000/api/docs/security/multi-user-scoping | jq '.title'
curl -s http://localhost:8000/api/docs/security/hook-policy | jq '.title'

# Test catalog and compliance docs
curl -s http://localhost:8000/api/docs/catalog/system | jq '.title'
curl -s http://localhost:8000/api/docs/compliance/feature-traceability | jq '.title'
```

**Closure Evidence**:
- [x] Execute 8 curl tests above in production-like environment
- [x] Collect HTTP 200 responses for all 8 routes
- [x] Document test results in documentation gap register evidence packet
- [x] Record route → response status → timestamp results
- [x] Platform Lead sign-off collected for route accessibility

---

## Summary Table: Gap Closure Progress

| Gap ID | Domain | Owner | Target | Status | Block | Evidence |
|---|---|---|---|---|---|---|
| GAP-001 | Security | Security | 2026-04-07 | Closed (2026-03-31) | API contract written; middleware enforced | docs/security/api_authentication_contract.md |
| GAP-002 | Security | Security | 2026-04-10 | Closed (2026-03-31) | Runbook + checklist + alerts published | docs/security/key_compromise_incident_runbook.md |
| GAP-003 | Architecture | Architecture | 2026-04-09 | Closed (2026-03-31) | Trace, tests, and framework prep complete | docs/architecture/multi_user_propagation_trace.md |
| GAP-004 | Compliance | Compliance | 2026-04-12 | Closed (2026-03-31) | Mappings, tests, metrics, and alerts complete | docs/compliance/voice_feature_control_mapping.md |
| GAP-005 | Platform | Platform | 2026-04-05 | Closed | All routes verified HTTP 200 | docs/governance/documentation_gap_register.md |

---

## Related Documents
- [Documentation Gap Register](documentation_gap_register.md)
- [Sprint Tracking Board](sprint_tracking_board.md)
- [Sprint 1 Inventory](sprint1_inventory.md)

## See Also
- [all GAP verification reports](docs/governance/gap_verification_reports/)
