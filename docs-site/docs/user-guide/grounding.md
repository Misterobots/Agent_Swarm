---
title: "Grounding"
---

# Grounding

Grounding enriches the model's context with live, external information before it generates a response — so answers reflect up-to-date facts or your own documents rather than only the model's training data.

Two grounding modes are available:

| Mode | Icon | What it injects | Permission required |
|------|------|-----------------|---------------------|
| **Web Grounding** | 🌐 Globe | Top 5 live DuckDuckGo search results | `web_grounding` — governance approval |
| **Doc Grounding** | 📖 Book | Top 5 relevant chunks from your knowledge library | `docs_grounding` — governance approval |

Both modes are **off by default** and gated behind a governance approval workflow.

---

## Requesting Access

Because grounding can expose sensitive external data or internal documents to AI processing, it requires explicit approval.

### Via the UI

1. In the chat toolbar, click the **Web** or **Docs** toggle button (shown with a lock 🔒 icon when you don't yet have permission)
2. The system automatically submits a governance request on your behalf
3. The button label changes to **"Pending Approval"**
4. An admin reviews and approves your request in the Governance workspace
5. On next page load, the toggle becomes interactive and lights up when active

### Via the API

```bash
# Request web grounding access
curl -X POST {{ hive_ui_url }}/api/v1/grounding/request \
  -H "Content-Type: application/json" \
  -d '{
    "permission": "web_grounding",
    "reason": "Need live search results for research queries"
  }'
```

```bash
# Request document grounding access
curl -X POST {{ hive_ui_url }}/api/v1/grounding/request \
  -H "Content-Type: application/json" \
  -d '{
    "permission": "docs_grounding",
    "reason": "Need access to internal knowledge base for project work"
  }'
```

### Check Your Status

```bash
curl {{ hive_ui_url }}/api/v1/grounding/status
```

```json
{
  "owner_id": "user_001",
  "web_grounding": true,
  "docs_grounding": false
}
```

---

## Using the Toggles

Once approved, toggle buttons appear in the chat header bar (and the mobile overflow menu):

```
[Model ▾]  [🌐 Web]  [📖 Docs]  [🗺️ Plan]  [🧠 Think]  [🔭 Research]
```

- **Active** (accent colour) — grounding is enabled for all messages in this session
- **Inactive** (grey) — grounding is off
- **Locked** (grey + 🔒, faded) — permission not yet granted; click to request

Toggles are persisted in the browser's local storage (`hive-settings`) so they survive page refreshes.

---

## How It Works

### Web Grounding

When Web is enabled and a message is sent:

```
User message
    ↓
Router checks: grounding_web=True AND user has web_grounding permission?
    ↓ Yes
Intent heuristic: does the query need live data?
    ↓ Yes (matches keywords like "latest", "current", "news", "price" …)
DuckDuckGo search: web_search(user_input, num_results=5)
    ↓
Inject as system message:
    [Web Grounding Context]
    [1] Title
        https://example.com
        Snippet...
    [2] …
    ↓
Security scan
    ↓
Model answers with live context in scope
```

#### Intent Heuristic

Web search is **not** triggered for every message — only those where the heuristic detects a likely need for fresh data. Trigger keywords include:

`latest` · `current` · `today` · `now` · `news` · `recent` · `yesterday` · `this week` · `this month` · `this year` · `2025` · `who won` · `price` · `stock` · `weather` · `trending` · `breaking` · `just announced` · `released` · `update` · `version`

For questions like *"explain how recursion works"*, the search is skipped and the model answers from its own knowledge.

### Doc Grounding

When Docs is enabled and a message is sent:

```
User message
    ↓
Router checks: grounding_docs=True AND user has docs_grounding permission?
    ↓ Yes
PgVector hybrid search: architect_knowledge table, limit=5 chunks
    ↓
Inject as system message:
    [Document Context]
    [Source: my-project-spec.pdf]
    The API should support OAuth 2.0 PKCE…

    [Source: architecture-notes.md]
    The database uses a star schema with…
    ↓
Security scan
    ↓
Model answers with your documents in scope
```

---

## Context Injection Order

Multiple grounding sources stack up as system messages, injected in this order before the security scan and model call:

| Layer | Source | Condition |
|-------|--------|-----------|
| 1 | Session Memory summaries | `memory_enabled = true` |
| 2 | MemPalace semantic recall | `memory_enabled = true` + matches found |
| 3 | **Web Grounding Context** | `grounding_web = true` + permitted + intent matches |
| 4 | **Document Context** | `grounding_docs = true` + permitted + chunks found |
| — | Security scan | Always |
| — | Model routing + response | Always |

---

## Populating the Document Library

Doc grounding retrieves from the `architect_knowledge` table in PostgreSQL/PgVector.

### Per-Session (Chat Attachments)

Attach files directly to a message using the paperclip button in the chat input. These are injected into the current message context only — they are not stored persistently.

Doc grounding adds **library retrieval** on top of per-session attachments.

### Persistent Library (Knowledge Ingest)

Send documents to the ingest endpoint to make them available across all sessions:

=== "Text / JSON"

    ```bash
    curl -X POST {{ hive_ui_url }}/api/v1/knowledge/ingest \
      -H "Content-Type: application/json" \
      -d '{
        "content": "The API gateway exposes port 443 and uses Traefik for TLS termination.",
        "source": "architecture-notes",
        "tags": ["architecture", "networking"]
      }'
    ```

=== "File Upload"

    ```bash
    curl -X POST {{ hive_ui_url }}/api/v1/knowledge/ingest_file \
      -F "file=@my-document.pdf" \
      -F "source=my-document.pdf"
    ```

Once ingested, documents are chunked, embedded, and stored in PgVector. They become immediately available for Doc Grounding retrieval.

---

## Admin: Granting Permissions Manually

Skip the approval workflow for trusted users:

=== "Python"

    ```python
    from grounding_permissions import grounding_permissions

    grounding_permissions.grant("user_owner_id", "web_grounding")
    grounding_permissions.grant("user_owner_id", "docs_grounding")
    ```

=== "JSON file"

    Edit `/workspace/grounding_permissions.json` on the control plane:

    ```json
    {
      "user_owner_id": {
        "web_grounding": true,
        "docs_grounding": true,
        "granted_at": "2026-04-20T00:00:00+00:00"
      }
    }
    ```

=== "Governance approval"

    Navigate to **Governance** → find the pending `GROUNDING_WEB` or `GROUNDING_DOCS` request → click **Approve**. The permission is written automatically.

---

## Privacy & Security Notes

!!! warning "Web Grounding sends your query to DuckDuckGo"
    When web grounding triggers a search, the user's message (or a summary of it) is sent as a search query to DuckDuckGo Lite over HTTPS. No API key is required. Results are fetched via the internal `web_browser` tool and are subject to `BROWSER_DOMAIN_ALLOWLIST` / `BLOCKED_DOMAINS` configuration.

!!! info "Doc Grounding keeps data on-premises"
    Document retrieval runs entirely within your local PgVector instance. No data leaves your network.

!!! tip "Grounding runs before the security scan"
    Injected context passes through the Llama-Guard security check along with the rest of the prompt. Malicious content in a web search result or injected document will be caught if the security scan detects it.

---

## Related

- [Governance Requests](governance-requests.md) — how to approve grounding requests
- [Settings](settings.md) — all available chat toggles
- [Plan & Think Modes](plan-think.md) — other reasoning toggles
- [Module: Router](../modules/router.md) — grounding injection in the pipeline
- [API: Grounding](../developer-guide/api/grounding.md) — full API reference
