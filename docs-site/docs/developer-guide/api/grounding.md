---
title: "Grounding API"
---

# Grounding API

Endpoints for checking and requesting grounding permissions, and for managing the document knowledge library used by Doc Grounding.

---

## Check Grounding Status

Returns the current grounding permissions for the authenticated user.

```
GET /api/v1/grounding/status
```

### Response

```json
{
  "owner_id": "user_001",
  "web_grounding": true,
  "docs_grounding": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `owner_id` | `string` | The resolved owner identifier for the session |
| `web_grounding` | `bool` | Whether internet/web grounding is permitted |
| `docs_grounding` | `bool` | Whether knowledge-base document grounding is permitted |

---

## Request Grounding Permission

Submits a governance request to unlock a grounding capability. The request is reviewed by an admin; on approval the permission is automatically written to the grounding store.

```
POST /api/v1/grounding/request
```

### Body

```json
{
  "permission": "web_grounding",
  "reason": "Need live search results for research workflows"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `permission` | `string` | ✅ | `"web_grounding"` or `"docs_grounding"` |
| `reason` | `string` | — | Human-readable justification shown to the admin reviewer |

### Response

```json
{
  "status": "submitted",
  "request_id": "a1b2c3d4",
  "permission": "web_grounding"
}
```

The returned `request_id` maps to a standard governance request. Track it via [`GET /api/v1/request/{id}`](governance.md#get-request).

### Errors

| HTTP | Meaning |
|------|---------|
| `400` | `permission` value is not `"web_grounding"` or `"docs_grounding"` |
| `500` | Governance request could not be persisted |

---

## Using Grounding in Chat

Pass `grounding_web` and/or `grounding_docs` as boolean fields in the [Chat Completions](chat-completions.md) request body. These are ignored (treated as `false`) if the user does not have the corresponding permission.

```json
{
  "messages": [{"role": "user", "content": "What is the latest Python version?"}],
  "model": "default",
  "stream": true,
  "grounding_web": true,
  "grounding_docs": false
}
```

### Behaviour

| Field | Value | Result |
|-------|-------|--------|
| `grounding_web` | `true` + permission granted + intent matches | DuckDuckGo results injected as `[Web Grounding Context]` system message |
| `grounding_web` | `true` + permission granted + no keyword match | Search skipped; model answers from its own knowledge |
| `grounding_web` | `true` + **no permission** | Status event emitted: *"⚠️ Web grounding not permitted"*; request continues without grounding |
| `grounding_docs` | `true` + permission granted + chunks found | PgVector results injected as `[Document Context]` system message |
| `grounding_docs` | `true` + permission granted + no chunks | Status event: *"→ Doc grounding: no relevant chunks found"* |
| `grounding_docs` | `true` + **no permission** | Status event emitted; request continues without grounding |

---

## Knowledge Ingest

Add documents to the persistent knowledge library used by Doc Grounding.

### Ingest Text

```
POST /api/v1/knowledge/ingest
```

#### Body

```json
{
  "content": "The authentication gateway uses SPIRE SVID tokens for inter-service auth.",
  "source": "architecture-notes",
  "tags": ["auth", "spire", "architecture"]
}
```

#### Response

```json
{
  "status": "accepted"
}
```

!!! note
    The ingest endpoint accepts content and queues it for embedding. Documents are stored in the `architect_knowledge` PgVector table and become available for Doc Grounding retrieval immediately after embedding completes.

### Ingest File

```
POST /api/v1/knowledge/ingest_file
```

Upload a file (PDF, Markdown, plain text) as a multipart form:

```bash
curl -X POST {{ hive_ui_url }}/api/v1/knowledge/ingest_file \
  -F "file=@project-spec.pdf" \
  -F "source=project-spec.pdf"
```

---

## Admin: Manual Permission Grant / Revoke

Admins can manage permissions directly without the governance workflow.

### Grant

```python
from grounding_permissions import grounding_permissions

grounding_permissions.grant("owner_id", "web_grounding")
grounding_permissions.grant("owner_id", "docs_grounding")
```

### Revoke

```python
grounding_permissions.revoke("owner_id", "web_grounding")
```

### Persistence

Permissions are stored at `/workspace/grounding_permissions.json` on the control-plane host. The store is reloaded on each request; no service restart is required after manual edits.

---

## Related

- [Chat Completions API](chat-completions.md) — full chat request schema
- [Governance API](governance.md) — approve/reject pending grounding requests
- [User Guide: Grounding](../../user-guide/grounding.md) — end-user walkthrough


