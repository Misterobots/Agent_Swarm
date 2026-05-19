# Identity and Token Trust Standard

Document ID: SEC-IDENT-001
Domain: Security
Owner: Security
Reviewers: Architecture, Platform, Compliance
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/admin/security.md
Related Controls: MAESTRO L7, MAESTRO L6
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Define the production trust model for token identity in Home AI Lab, including token profiles, validation rigor, and rollback-safe operation.

## Token Profiles (Must Not Be Mixed)
1. Workload Identity Token: SPIFFE JWT-SVID for service-to-service identity.
2. User Access Token: user-scoped JWT for user context and multi-user routing state.

## Validation Requirements
For all accepted tokens:
1. Verify signature against allowlisted algorithms for the profile.
2. Require and validate iss, sub, aud, exp, iat, nbf.
3. Enforce token type and route-class compatibility.
4. Reject token if audience does not match endpoint class.
5. Reject token if issuer not pinned for that profile.

## Prohibited Patterns
1. Accepting none algorithm in production.
2. Accepting both HS and RS validation in the same endpoint path.
3. Trusting dynamic key URLs from token headers unless explicitly allowlisted.

## Route-Class Policy
1. Internal workload endpoints: workload identity profile only.
2. User interaction endpoints: user access profile only.
3. Mixed acceptance is prohibited except temporary migration mode with explicit feature flag.
4. Canonical endpoint-class and claims contract: docs/security/api_authentication_contract.md.

## Rollback-Safe Migration
1. Parse-only mode: observe token claims without enforcement.
2. Soft-enforce mode: enforce but allow controlled fallback with logging.
3. Hard-enforce mode: reject nonconforming tokens.
4. Rollback action: return to soft-enforce while preserving issuer and audience checks.

## Verification
1. Token confusion tests reject cross-profile substitution.
2. Algorithm confusion tests reject RS/HS misuse.
3. Issuer and audience mismatch tests fail closed.
4. Endpoint-class validation examples are maintained in docs/security/api_contract_validation_examples.md.
