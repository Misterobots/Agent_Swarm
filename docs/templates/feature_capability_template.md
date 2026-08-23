# [Capability Name]

Document ID: CAP-[DOMAIN]-NNN  
Domain: [Domain]  
Owner: [Owner]  
Reviewers: [Reviewers]  
Status: Draft  
Version: 0.1  
Last Updated: YYYY-MM-DD  
Review Due: YYYY-MM-DD  
Source of Truth: [Primary code/config paths]  
Related Controls: [Controls or None]  
Related Evidence: [Evidence paths or Pending]  
Supersedes: None

## Summary

[What this capability does, who uses it, and why it exists.]

## Current Status

| Scope | Status | Last verified | Notes |
|---|---|---:|---|
| [Behavior] | Planned / Implemented / Deployed / Verified | YYYY-MM-DD | [Evidence or limitation] |

## User Contract

### Supported

- [Workflow, command, or behavior]

### Explicitly unsupported

- [Behavior the system must decline or clarify]

### Success and failure language

- Starting: [What the system may claim before completion]
- Success: [What must be verified before claiming success]
- Failure: [How failure is surfaced]
- Ambiguous request: [Clarify, resolve, or decline]

## Architecture and Data Flow

[Short flow from ingress through dependencies to the result. Link a diagram only when it materially improves understanding.]

## Resolution Rules

[How users, devices, areas, models, tenants, or targets are selected. Include precedence and ambiguity behavior.]

## Source-of-Truth Files

| Path | Responsibility |
|---|---|
| `[path]` | [Contract owned here] |

## Configuration Contract

| Variable or setting | Required | Default | Purpose | Sensitive |
|---|---:|---|---|---:|
| `[NAME]` | Yes/No | `[safe default]` | [Purpose] | Yes/No |

## Dependencies and Permissions

- [External services]
- [Required API/service permissions]
- [Network reachability assumptions]

## Failure and Degraded Behavior

| Condition | Observable behavior | Recovery or fallback |
|---|---|---|
| [Failure] | [What user/operator sees] | [Action] |

## Security and Privacy

[Trust boundary, authorization, recipient selection, sensitive data, spoofing risks, retention.]

## Deployment and Rollback

### Deploy

```text
[Commands or runbook link]
```

### Roll back

```text
[Commands or feature flag]
```

## Verification

### Automated

- [Test and expected result]

### End to end

1. [Step]
2. [Expected observable result]

## Known Limitations

- [Current constraint]

## Extension Procedure

1. [How to add another target/integration/device]
2. [Which files and docs must change]
3. [Required verification]

## Open Decisions

- [Question, owner, target date]

## Change Log

| Date | Version | Change | Evidence |
|---|---:|---|---|
| YYYY-MM-DD | 0.1 | Initial draft | Pending |

## Related Documents

- [Documentation standard](../governance/feature_documentation_standard.md)
- [Relevant ADR, runbook, user guide, or evidence]

