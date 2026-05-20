---
title: Goals Mode
---

# Goals Mode

Per-thread task tracking that turns a chat thread into a structured, auditable work session.

## Overview

When Goals Mode is active for a thread, a slide-in panel appears on the right side of the chat interface. The panel displays:

- **Objective** — the natural-language goal for this thread
- **Progress bar** — completed steps / total steps
- **Plan steps** — ordered checklist with `pending → in_progress → completed` status flow
- **Evidence log** — artifacts collected during execution (command output, file refs, test results, notes)
- **Footer actions** — Pause and Complete controls

Goals persist in the database across page refreshes. Each goal is scoped to a single thread.

---

## How to Access

Goals Mode is activated by the agent when it detects a substantive, multi-step request — or can be triggered manually via the API.

### Via Chat

Ask the agent to work on something with a clear deliverable:

> *"Build out the authentication module for the API"*  
> *"Research and summarise the three main approaches to CRDT conflict resolution"*  
> *"Set up the monitoring stack on Hopper"*

The agent creates a goal automatically and the Goals panel slides open.

### Via API

```bash
POST /api/v1/goals
Content-Type: application/json

{
  "thread_id": "thread_abc123",
  "objective": "Implement JWT refresh token rotation"
}
```

Response:

```json
{
  "id": "goal_xyz",
  "thread_id": "thread_abc123",
  "objective": "Implement JWT refresh token rotation",
  "status": "active",
  "created_at": "2026-05-19T10:00:00Z"
}
```

---

## The Goals Panel

The panel slides in from the right edge of the chat layout. A tab handle is always visible at the right margin — click it to open or close the panel at any time.

```
                           ┌──────────────────────────┐
                           │  ★ ACTIVE GOAL    active  │
                     ──────┤                           │
  Chat area          │ Tab │  Objective text here...   │
                     ──────│                           │
                           │  Progress ─────────── 40% │
                           │  2 / 5 steps              │
                           │                           │
                           │  Plan                     │
                           │  ○ Gather context         │
                           │  ◌ Implement scaffold ←   │
                           │  ○ Write tests            │
                           │  ○ Verify                 │
                           │  ○ Completion audit       │
                           │                           │
                           │  ▶ Evidence (2)           │
                           │                           │
                           │  [Pause]   [Complete ✓]  │
                           └──────────────────────────┘
```

The panel tab pulses with the accent colour when a step is `in_progress`.

### Panel Open Animation

When the panel opens it plays a one-shot glassomorphic sweep — a diagonal shimmer across the frosted-glass surface — followed by a staggered cascade of plan steps fading in from top to bottom (40 ms delay per step).

---

## Plan Steps

Each plan step has three states:

| State | Icon | Meaning |
|-------|------|---------|
| `pending` | Empty circle | Not yet started |
| `in_progress` | Spinning ring | Currently being worked on |
| `completed` | Green check | Done |

### Status Transitions

Steps flow forward only: `pending → in_progress → completed`.

The agent updates steps automatically as it works. You can also advance a step manually using the **Start** / **Done** buttons on each row.

When a step transitions to `in_progress` or `completed`, a sweep shimmer animation runs across that row — the same glassomorphic effect as the panel open.

### Staggered Entry

When the panel first opens, each plan step fades in with a 40 ms stagger so rows cascade in top-to-bottom rather than all appearing at once.

---

## Evidence

The Evidence section (collapsed by default) shows artifacts the agent has collected to verify progress:

| Evidence Type | What it captures |
|--------------|-----------------|
| `command_output` | Shell command result |
| `file_ref` | Path to a file written or modified |
| `test_result` | Test pass/fail output |
| `note` | Free-form annotation |

Click **Evidence (N)** to expand the log. Each evidence card shows the requirement it satisfies and the reference value.

---

## Goal Status

A goal moves through three top-level states:

| Status | Meaning |
|--------|---------|
| `active` | Work is in progress |
| `paused` | Manually paused — no automatic step updates |
| `complete` | Goal has been marked complete |

Use the **Pause** button to suspend without closing, and **Complete ✓** to finalise. Once complete, the step list becomes read-only and the footer shows a confirmation badge.

---

## Database Schema

Goals data lives in the agent runtime's PostgreSQL database:

```sql
-- Thread-scoped goals
CREATE TABLE goals (
  id          TEXT PRIMARY KEY,
  thread_id   TEXT NOT NULL,
  objective   TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('active','complete','paused')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- Ordered plan steps per goal
CREATE TABLE goal_plan_steps (
  id       TEXT PRIMARY KEY,
  goal_id  TEXT NOT NULL REFERENCES goals(id),
  step     TEXT NOT NULL,
  status   TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
  ord      INTEGER NOT NULL
);

-- Evidence artifacts per goal
CREATE TABLE goal_evidence (
  id             TEXT PRIMARY KEY,
  goal_id        TEXT NOT NULL REFERENCES goals(id),
  requirement    TEXT NOT NULL,
  evidence_type  TEXT NOT NULL,  -- command_output | file_ref | test_result | note
  evidence_ref   TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/goals` | Create a goal for a thread |
| `GET`  | `/api/v1/goals/{thread_id}/active` | Fetch the active goal for a thread |
| `POST` | `/api/v1/goals/{goal_id}/steps` | Add a plan step |
| `PATCH`| `/api/v1/goals/{goal_id}/steps/{step_id}` | Update step status |
| `POST` | `/api/v1/goals/{goal_id}/evidence` | Add an evidence item |
| `POST` | `/api/v1/goals/{goal_id}/complete` | Mark goal complete |
| `POST` | `/api/v1/goals/{goal_id}/pause` | Pause / unpause |

Full schema: see [API Reference: Internal](../developer-guide/api/internal.md).

---

## Tips

!!! tip "Short objectives work best"
    Keep the objective to one sentence. The agent uses it as context for every plan step it writes.

!!! tip "Evidence before Complete"
    The **Complete ✓** button is always available, but the agent will normally collect evidence before suggesting completion. Check the Evidence log if the result looks incomplete.

!!! note "One goal per thread"
    Each thread can have at most one `active` goal at a time. Starting a new goal while one is active requires completing or pausing the existing one first.

---

## Related

- [Plan & Think Modes](plan-think.md) — plan decomposition without persistent tracking
- [Module: Coordinator](../modules/coordinator.md) — multi-agent orchestration that populates plan steps
- [Developer Guide: Glass Animation System](../developer-guide/glass-animations.md) — technical detail on the sweep animations
