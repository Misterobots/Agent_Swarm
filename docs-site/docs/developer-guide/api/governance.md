---
title: Governance API
---

# Governance API

Submit and manage governance requests for privileged operations.

## Submit Request

```
POST /v1/governance/request
```

### Body

```json
{
    "action": "execute_command",
    "command": "rm -rf /tmp/old-data",
    "reason": "Cleaning up stale temporary files",
    "session_id": "session-abc",
    "owner_id": "user_001"
}
```

### Response

```json
{
    "request_id": "gov-xyz789",
    "status": "pending_review",
    "action": "execute_command",
    "created_at": "2026-04-10T14:30:00Z"
}
```

## Get Request Status

```
GET /v1/governance/{request_id}
```

### Response

```json
{
    "request_id": "gov-xyz789",
    "status": "approved",
    "action": "execute_command",
    "reviewer": "admin",
    "reviewed_at": "2026-04-10T14:35:00Z",
    "result": "Command executed successfully"
}
```

## Governance Statuses

| Status | Description |
|--------|-------------|
| `pending_review` | Awaiting admin review |
| `approved` | Approved and executed |
| `denied` | Rejected by admin |
| `auto_approved` | Approved by policy (low-risk) |
| `expired` | Not reviewed within timeout |

## List Pending Requests

```
GET /v1/governance/pending
```

Returns all requests in `pending_review` status.

## Approve / Deny

```
POST /v1/governance/{request_id}/approve
POST /v1/governance/{request_id}/deny
```

### Body (Deny)

```json
{
    "reason": "Too risky — use a safer alternative"
}
```
