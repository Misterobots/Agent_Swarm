---
title: "MemPalace API"
---

# MemPalace API

Complete reference for the MemPalace HTTP API and MCP tool surface. The
service exposes 15 REST endpoints under `/v1/...` and 4 MCP tools under
`/mcp`. Both surfaces share the same Postgres backend and behave
consistently — the MCP tools are designed for agent contexts (terse string
output, `owner_id` always required), the HTTP endpoints for everything else.

> **Source of truth:** [`control_plane/mempalace/app/main.py`](https://github.com/Misterobots/Agent_Swarm/blob/main/control_plane/mempalace/app/main.py)

## Conventions

| Topic | Detail |
|---|---|
| **Base URL** | `http://{{ hopper_ip }}:8200` |
| **Content-Type** | `application/json` for all requests with bodies |
| **Auth** | None at the network layer (relies on private LAN). `actor_id` is a self-declared audit field — see "Identity & Trust" below |
| **Errors** | FastAPI standard `{"detail": "<message>"}` with appropriate HTTP status |
| **Datetimes** | All ISO-8601 with timezone (`+00:00`) |
| **IDs** | UUIDs as strings |

### Identity & Trust

The `actor_id` query parameter on `PATCH /v1/memories/{id}` and
`DELETE /v1/memories/{id}` is recorded into the audit log but is **not
authenticated** — any caller may declare any string. `actor_role` is
hardcoded server-side to `"user"` to prevent self-promotion to admin via
query string.

Until proper authenticated identity is wired in, the audit trail is best
treated as forensic-quality only when the calling agent is itself trusted.

### Memory taxonomy

Every semantic memory has `memory_type` and `domain`:

| `memory_type` | Hall mapping | Meaning |
|---|---|---|
| `semantic` | `hall_facts` | Factual knowledge (default) |
| `episodic` | `hall_events` | Events / experiences |
| `procedural` | `hall_advice` | Rules / how-to |
| `preference` | `hall_preferences` | User preference |
| `discovery` | `hall_discoveries` | Findings / insights |

`domain` is free-form (`coding` / `visual` / `architecture` / `general` / …).
The Palace UI surfaces unique `domain` values as "rooms".

---

## Health

### `GET /health`

Liveness check. Performs a `SELECT 1` against Postgres so a 200 confirms
both the FastAPI process and DB connectivity. Used by the Docker
`HEALTHCHECK`.

**Response 200**

```json
{"status": "ok", "service": "mempalace"}
```

---

## Memories

### `POST /v1/memories` — Store

Stores a single memory. Generates the embedding via Ollama
(`nomic-embed-text`) and writes a `created` audit row in the same
transaction.

**Query**

| Param | Type | Required | Notes |
|---|---|---|---|
| `actor_id` | string | optional | Recorded in audit; defaults to `agent_id` or `owner_id` if empty |

**Body** (`MemoryCreate`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `content` | string | ✓ | | The memory itself |
| `memory_type` | string | | `"semantic"` | One of the 5 taxonomy values |
| `domain` | string | | `"general"` | Free-form |
| `agent_id` | string \| null | | `null` | Creating agent |
| `team_id` | string \| null | | `null` | Coordinator team scope |
| `owner_id` | string | ✓ | | User identity — required for all writes |
| `metadata` | object | | `{}` | Free-form JSON |

**Response 200** (`MemoryOut`) — see [shape below](#memoryout-shape).

**Error 400** when `owner_id` missing or empty:

```json
{"detail": "owner_id is required for memory writes"}
```

### `POST /v1/memories/search` — Semantic search

Cosine similarity search over the embeddings. As a side effect, increments
`access_count` for each hit (used by the Palace UI heat indicator and the
ADR-005 Phase 2 ranking score).

**Body** (`SearchQuery`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `query` | string | required | Free-text query |
| `owner_id` | string \| null | `null` | Filter by user |
| `agent_id` | string \| null | `null` | Filter by agent |
| `team_id` | string \| null | `null` | Filter by team |
| `memory_type` | string \| null | `null` | One of the 5 types |
| `domain` | string \| null | `null` | Free-form |
| `limit` | int | `10` | Top-N results |

**Response 200** — array of `MemoryOut` ordered by ascending cosine distance
(closest first), each with a populated `score` field in `[-1.0, 1.0]`
where `1.0` = identical.

### `PATCH /v1/memories/{memory_id}` — Update

Updates content/type/domain/metadata and writes an `edited` audit row.
Re-embeds if `content` changes.

**Path**: `memory_id` (UUID)

**Query**

| Param | Type | Required | Notes |
|---|---|---|---|
| `actor_id` | string | ✓ | Recorded in audit |

**Body** (`MemoryUpdate` — all fields optional, only changed fields apply)

| Field | Type |
|---|---|
| `content` | string |
| `memory_type` | string |
| `domain` | string |
| `metadata` | object |

**Response 200** (`MemoryOut`).

**Error 404** if memory not found.

### `DELETE /v1/memories/{memory_id}` — Delete

Deletes the memory and writes a `deleted` audit row containing
`previous_content` so the deletion is forensically recoverable from the
audit trail (the audit row's `memory_id` is intentionally not a foreign
key — it survives the deletion).

**Query**

| Param | Type | Default | Notes |
|---|---|---|---|
| `actor_id` | string | `"anonymous"` | Recorded in audit |

**Response 200**

```json
{"status": "deleted", "id": "<uuid>"}
```

**Error 404** if memory not found (no audit row written in this case).

### `GET /v1/memories/stats` — Counts

**Response 200**

```json
{
  "total": 162,
  "breakdown": [
    {"type": "semantic", "domain": "general", "count": 41},
    {"type": "procedural", "domain": "coding", "count": 40},
    ...
  ]
}
```

### `GET /v1/memories/{memory_id}/audit` — Audit history

**Path**: `memory_id` (UUID)

**Response 200** — array of `AuditLogOut` ordered newest-first:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Audit row UUID |
| `memory_id` | string | Original memory UUID (may reference a deleted memory) |
| `action` | string | `"created"` / `"edited"` / `"deleted"` |
| `actor_id` | string | Self-declared at write time |
| `actor_role` | string | Currently always `"user"` |
| `previous_content` | string \| null | For edits/deletes |
| `new_content` | string \| null | For creates/edits |
| `changed_fields` | object | Diff of the changed fields |
| `created_at` | string | ISO-8601 |

---

## Extraction

### `POST /v1/extract` — Run extractor + store

Runs the conversation through the LLM extractor (`qwen2.5-coder:14b`),
embeds each extracted fact in batch, and stores them along with an
`extraction_log` audit row — all in a single Postgres transaction.

**Body** (`ExtractionRequest`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `conversation` | string | ✓ | Up to ~4000 chars sent to LLM (truncated internally) |
| `owner_id` | string | ✓ | Required |
| `agent_id` | string \| null | | |
| `team_id` | string \| null | | |

**Response 200** — array of `MemoryOut` for the stored memories.

**Empty array** is a valid response — meaning the LLM extractor identified
no durable facts. The extraction attempt is still logged.

**Error 400** when `owner_id` missing.

The agent runtime calls this after each model response:
[`agents/main.py:_mempalace_extract_http`](https://github.com/Misterobots/Agent_Swarm/blob/main/agents/main.py).

---

## Agent Snapshots

Versioned per-agent learned state. Race-safe: the writer retries up to 5×
on the unique `(agent_id, owner_id, version)` constraint.

### `POST /v1/snapshots` — Save

**Body** (`SnapshotCreate`)

| Field | Type | Required |
|---|---|---|
| `agent_id` | string | ✓ |
| `owner_id` | string \| null | |
| `snapshot_data` | object | ✓ |

**Response 200** (`SnapshotOut`)

```json
{
  "id": "<uuid>",
  "agent_id": "<agent>",
  "owner_id": "<user>",
  "snapshot_data": {...},
  "version": 3,
  "created_at": "2026-05-08T14:48:21+00:00"
}
```

**Error 503** with body `{"detail": "Snapshot save contention — retry later"}`
if the writer can't claim a free version slot after 5 attempts.

### `GET /v1/snapshots/{agent_id}` — Latest

**Path**: `agent_id` (string)

**Query**

| Param | Type |
|---|---|
| `owner_id` | string \| null |

**Response 200** — latest `SnapshotOut`, or `null` if none exist.

---

## Team Memory

Shared key-value store scoped to a coordinator team. Atomic upserts via
`INSERT … ON CONFLICT (team_id, key) DO UPDATE`.

### `POST /v1/team/{team_id}` — Upsert

**Path**: `team_id` (string)

**Body** (`TeamMemoryCreate`)

| Field | Type | Required |
|---|---|---|
| `key` | string | ✓ |
| `value` | string | ✓ |
| `author_agent` | string \| null | |

**Response 200** (`TeamMemoryOut`).

### `GET /v1/team/{team_id}` — List all

**Response 200** — array of `TeamMemoryOut` ordered by `created_at` ascending.

### `POST /v1/team/{team_id}/search` — Semantic search within team

**Body** (`SearchQuery`) — only `query` and `limit` are used; team is in path.

**Response 200** — array of `TeamMemoryOut`.

### `DELETE /v1/team/{team_id}` — Clear

Bulk-clears all memories for the team. Used post-coordination when the
team's scratchpad is no longer needed.

**Response 200**

```json
{"status": "cleared", "team_id": "<id>", "deleted": 17}
```

---

## Palace Viewer

The 3D Palace UI uses these endpoints. The hierarchy is computed dynamically
from the `memories` table — there is no separate "palace" storage.

### `GET /v1/palace/layout` — Hierarchy

**Query**

| Param | Type | Notes |
|---|---|---|
| `owner_id` | string \| null | Scope to one user |
| `agent_id` | string \| null | Scope to one agent |

**Response 200** (`PalaceLayoutOut`)

```json
{
  "wings": [
    {
      "name": "wing_owner_<owner_id>",
      "halls": [
        {
          "name": "hall_facts",
          "rooms": [
            {"name": "coding", "drawer_count": 18},
            {"name": "general", "drawer_count": 41}
          ]
        }
      ]
    }
  ],
  "total_memories": 162
}
```

Wing prefixes encode scope unambiguously (post-2026-05-08):

| Prefix | Meaning |
|---|---|
| `wing_team_<team_id>` | Team scope |
| `wing_agent_<agent_id>` | Agent scope |
| `wing_owner_<owner_id>` | Owner scope (no agent or team) |
| `wing_self` | Unscoped (no owner / agent / team) |

### `GET /v1/palace/room` — Memories at a coordinate

**Query**

| Param | Type | Required |
|---|---|---|
| `wing` | string | ✓ — see prefix table above |
| `hall` | string | ✓ — `hall_facts` / `hall_events` / `hall_advice` / etc. |
| `room` | string | ✓ — the `domain` value |
| `owner_id` | string \| null | optional extra filter |
| `limit` | int (default 100) | |
| `offset` | int (default 0) | |

**Response 200** — array of `MemoryOut` ordered by `created_at` desc.

### `GET /v1/palace/audit/extractions` — Per-owner extraction stats

Single-query summary used by the Palace audit panel.

**Response 200**

```json
[
  {
    "owner_id": "62e65d4d...",
    "owner_id_short": "62e65d4d...",
    "total_attempts": 39,
    "total_memories_stored": 151,
    "current_memory_count": 154,
    "success_rate": 0.8974,
    "last_attempt_at": "2026-05-08T00:28:48+00:00",
    "last_success_at": "2026-05-08T00:28:48+00:00"
  }
]
```

| Field | Meaning |
|---|---|
| `total_attempts` | Number of `/v1/extract` calls for this owner |
| `total_memories_stored` | Sum of memories stored across all attempts |
| `current_memory_count` | Live row count in `memories` table for this owner |
| `success_rate` | Attempts that produced ≥1 memory ÷ total attempts |

`current_memory_count` may differ from `total_memories_stored` because
memories can be deleted via `DELETE /v1/memories/{id}` after they were
originally stored.

---

## MCP Tools

Mounted at `/mcp` (Streamable HTTP transport). All four tools require
`owner_id` to be a non-empty string — without it they short-circuit and
return an error string rather than performing the operation. This matches
the HTTP `owner_id` requirement and prevents agents from creating orphan
memories or reading across user boundaries.

Transport security restricts allowed hosts to `192.168.2.102:*`,
`localhost:*`, `127.0.0.1:*`, and `hopper:*`. DNS rebinding protection is
enabled.

### `search_memories_mcp`

```python
search_memories_mcp(query: str, owner_id: str, agent_id: str = "", limit: int = 10) -> str
```

Returns a newline-joined string of results, one per line:

```
[0.8743] (semantic/coding) Always use type hints in Python code
[0.8124] (procedural/coding) Prefer dataclasses over plain dicts
```

Or `"No memories found."` if empty. Or `"Error: owner_id is required ..."`
if `owner_id` blank.

### `store_memory_mcp`

```python
store_memory_mcp(
    content: str,
    memory_type: str = "semantic",
    domain: str = "general",
    agent_id: str = "",
    owner_id: str,
) -> str
```

Returns `"Stored memory <uuid> [<type>/<domain>]"` on success, or
`"Error: owner_id is required for memory writes"` if blank.

### `get_memory_stats_mcp`

```python
get_memory_stats_mcp() -> str
```

Returns a multi-line summary:

```
Total: 162
  semantic/coding: 18
  procedural/coding: 40
  ...
```

### `extract_from_conversation_mcp`

```python
extract_from_conversation_mcp(
    conversation: str,
    owner_id: str = "",
    agent_id: str = "",
    domain: str = "general",
) -> str
```

Returns a multi-line summary of stored memories with truncated content
previews:

```
Stored 3 memories:
  - User prefers cyberpunk visual style with neon colors and rain…
  - Python code should always use type hints and follow PEP-8…
  - When deploying mempalace, stamp baseline before first boot…
```

Or `"No memories extracted from conversation."` if the LLM identified none.

---

## Schema reference

### `MemoryOut` shape

The canonical "stored memory" representation, used by every endpoint that
returns a memory:

| Field | Type | Notes |
|---|---|---|
| `id` | string | UUID |
| `content` | string | The memory |
| `memory_type` | string | One of 5 taxonomy values |
| `domain` | string \| null | |
| `agent_id` | string \| null | |
| `team_id` | string \| null | |
| `owner_id` | string \| null | |
| `metadata` | object | Free-form |
| `created_at` | string | ISO-8601 |
| `access_count` | int | Bumped on every search hit |
| `score` | float \| null | Populated only on search responses |
| `wing` / `hall` / `room` | string \| null | Populated from `metadata` if present |

### Status codes

| Code | Used by | Meaning |
|---|---|---|
| `200` | All success paths | |
| `400` | `POST /v1/memories`, `POST /v1/extract` | Missing `owner_id` |
| `404` | `PATCH`/`DELETE /v1/memories/{id}` | Memory not found |
| `422` | `PATCH /v1/memories/{id}` | Missing required `actor_id` query param |
| `500` | Any | Ollama unreachable, unhandled error |
| `503` | `POST /v1/snapshots` | Version-claim contention exhausted retries |

---

## Examples

### Store a memory

```bash
curl -X POST http://{{ hopper_ip }}:8200/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers cyberpunk aesthetic with neon and rain",
    "memory_type": "preference",
    "domain": "visual",
    "owner_id": "user_001"
  }'
```

### Search

```bash
curl -X POST http://{{ hopper_ip }}:8200/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what visual style does the user like?",
    "owner_id": "user_001",
    "memory_type": "preference",
    "limit": 5
  }'
```

### Extract from a conversation

```bash
curl -X POST http://{{ hopper_ip }}:8200/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "conversation": "User asked for help with Python error handling. Assistant noted user prefers concise responses with code examples.",
    "owner_id": "user_001",
    "agent_id": "code_developer"
  }'
```

### Save a snapshot

```bash
curl -X POST http://{{ hopper_ip }}:8200/v1/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "architect",
    "owner_id": "user_001",
    "snapshot_data": {
      "learned_rules": ["prefer alpine images", "always use type hints"]
    }
  }'
```

### Edit a memory (with audit)

```bash
curl -X PATCH "http://{{ hopper_ip }}:8200/v1/memories/<uuid>?actor_id=user_001" \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated memory text"}'
```

---

## Related

- [Service: MemPalace](../../modules/services/mempalace.md) — operator reference (deployment, env, ops)
- [Architecture Deep Dive](../../architecture/mempalace-deep-dive.md) — design + rationale
- [Memory System](../../architecture/memory-system.md) — how MemPalace fits with other memory subsystems
- [Migrations Procedure](../../procedures/mempalace-migration.md) — Alembic workflow + deploy
- [Source: control_plane/mempalace/app/main.py](https://github.com/Misterobots/Agent_Swarm/blob/main/control_plane/mempalace/app/main.py)
