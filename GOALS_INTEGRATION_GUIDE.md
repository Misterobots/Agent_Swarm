# Codex Goals Mode Integration Guide (OpenClaw Local Setup)

## 1) What You Are Building

You want Goals mode to be first-class in your local OpenClaw workflow so every session can:
- create a goal automatically
- track progress as structured plan steps
- persist artifacts/evidence
- optionally schedule follow-ups/automations
- mark goals complete only after a completion audit

This guide is intentionally implementation-focused and does not modify your attached `Agent_Swarm-main.zip` project.

---

## 2) Success Criteria

A local setup is considered complete when all are true:
1. New sessions automatically create an active goal.
2. Goal state is queryable (`active`, `complete`, metadata).
3. Plan steps are tracked and updated during execution.
4. Completion requires checklist evidence, not just "tests passed".
5. Optional recurring checks/reminders can be attached to long-running goals.

---

## 3) Recommended Architecture

Use a thin Goals Orchestrator in front of your existing runtime.

- UI layer (Next.js in your reference): render goal badges, plan, evidence, completion state.
- Orchestrator layer (new service/module): owns goal lifecycle + audit rules.
- Storage layer: local SQLite/Postgres for goals, plans, evidence.
- Automation layer: cron/heartbeat runner for follow-ups.

Data flow:
1. User prompt enters runtime.
2. Orchestrator ensures an active goal exists.
3. Agent work updates plan/evidence incrementally.
4. Completion audit runs before marking complete.
5. Optional automations schedule future checks.

---

## 4) Local File/Module Scaffolding

Create this in your own local repo (not in the attached archive):

```text
openclaw-local/
  goals/
    goals.schema.sql
    goals.types.ts
    goals.store.ts
    goals.service.ts
    goals.audit.ts
    goals.middleware.ts
    goals.automation.ts
  api/
    goals.routes.ts
  ui/
    components/GoalPill.tsx
    components/GoalPlanPanel.tsx
    components/GoalAuditPanel.tsx
```

---

## 5) Database Schema (SQLite/Postgres-friendly)

```sql
-- goals/goals.schema.sql
CREATE TABLE IF NOT EXISTS goals (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','complete','paused')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  tokens_used INTEGER DEFAULT 0,
  time_used_seconds INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS goal_plan_steps (
  id TEXT PRIMARY KEY,
  goal_id TEXT NOT NULL,
  step TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
  ord INTEGER NOT NULL,
  FOREIGN KEY(goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS goal_evidence (
  id TEXT PRIMARY KEY,
  goal_id TEXT NOT NULL,
  requirement TEXT NOT NULL,
  evidence_type TEXT NOT NULL, -- command_output | file_ref | test_result | note
  evidence_ref TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(goal_id) REFERENCES goals(id)
);
```

---

## 6) Core Types

```ts
// goals/goals.types.ts
export type GoalStatus = 'active' | 'complete' | 'paused';
export type PlanStatus = 'pending' | 'in_progress' | 'completed';

export interface Goal {
  id: string;
  threadId: string;
  objective: string;
  status: GoalStatus;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  tokensUsed: number;
  timeUsedSeconds: number;
}

export interface GoalPlanStep {
  id: string;
  goalId: string;
  step: string;
  status: PlanStatus;
  ord: number;
}

export interface GoalEvidence {
  id: string;
  goalId: string;
  requirement: string;
  evidenceType: 'command_output' | 'file_ref' | 'test_result' | 'note';
  evidenceRef: string;
  createdAt: string;
}
```

---

## 7) Goal Service (Lifecycle)

```ts
// goals/goals.service.ts
import { randomUUID } from 'node:crypto';
import type { Goal } from './goals.types';
import { goalsStore } from './goals.store';

export const goalsService = {
  async ensureGoal(threadId: string, objective: string): Promise<Goal> {
    const existing = await goalsStore.getActiveByThread(threadId);
    if (existing) return existing;

    const now = new Date().toISOString();
    const goal: Goal = {
      id: randomUUID(),
      threadId,
      objective,
      status: 'active',
      createdAt: now,
      updatedAt: now,
      tokensUsed: 0,
      timeUsedSeconds: 0,
    };

    await goalsStore.create(goal);
    return goal;
  },

  async updateUsage(goalId: string, deltaTokens: number, deltaSeconds: number) {
    await goalsStore.updateUsage(goalId, deltaTokens, deltaSeconds);
  },

  async completeGoal(goalId: string) {
    const now = new Date().toISOString();
    await goalsStore.setStatus(goalId, 'complete', now);
  },
};
```

---

## 8) Auto-Enable Goals Middleware

This gives you "don’t ask every time" behavior.

```ts
// goals/goals.middleware.ts
import { goalsService } from './goals.service';

interface RequestContext {
  threadId: string;
  userPrompt: string;
  goalId?: string;
}

export async function withAutoGoal(ctx: RequestContext) {
  // Keep objective short and concrete for better tracking.
  const objective = ctx.userPrompt.length > 220
    ? ctx.userPrompt.slice(0, 220)
    : ctx.userPrompt;

  const goal = await goalsService.ensureGoal(ctx.threadId, objective);
  ctx.goalId = goal.id;
  return ctx;
}
```

---

## 9) Plan Tracking Rules

Enforce one `in_progress` step at a time.

```ts
// goals/goals.audit.ts (partial)
import type { GoalPlanStep } from './goals.types';

export function validatePlan(steps: GoalPlanStep[]) {
  const inProgressCount = steps.filter(s => s.status === 'in_progress').length;
  if (inProgressCount > 1) {
    throw new Error('Plan invalid: at most one step can be in_progress');
  }
}
```

Plan template for most coding goals:
1. Gather context and constraints.
2. Implement minimal viable change/scaffold.
3. Verify with commands/tests.
4. Produce completion audit mapping requirements to evidence.

---

## 10) Completion Audit Gate (Critical)

Do not mark complete unless each requirement has direct evidence.

```ts
// goals/goals.audit.ts
import type { GoalEvidence } from './goals.types';

export interface RequirementCheck {
  requirement: string;
  requiredEvidenceTypes: Array<GoalEvidence['evidenceType']>;
}

export function canCompleteGoal(
  checks: RequirementCheck[],
  evidence: GoalEvidence[]
): { ok: boolean; missing: string[] } {
  const missing: string[] = [];

  for (const check of checks) {
    const hasAll = check.requiredEvidenceTypes.every(type =>
      evidence.some(e => e.requirement === check.requirement && e.evidenceType === type)
    );

    if (!hasAll) missing.push(check.requirement);
  }

  return { ok: missing.length === 0, missing };
}
```

Example requirement set:
- "Goal auto-created for new thread" requires `command_output` or `test_result`.
- "Plan updates persist" requires `file_ref` + `test_result`.
- "Completion blocked without evidence" requires failing and passing test proof.

---

## 11) API Endpoints

```ts
// api/goals.routes.ts
import { Router } from 'express';
import { goalsService } from '../goals/goals.service';

const router = Router();

router.post('/goals/ensure', async (req, res) => {
  const { threadId, objective } = req.body;
  const goal = await goalsService.ensureGoal(threadId, objective);
  res.json({ goal });
});

router.post('/goals/:id/complete', async (req, res) => {
  await goalsService.completeGoal(req.params.id);
  res.json({ ok: true });
});

export default router;
```

---

## 12) UI Scaffolding (Next.js)

```tsx
// ui/components/GoalPill.tsx
'use client';

type Props = {
  objective: string;
  status: 'active' | 'complete' | 'paused';
};

export function GoalPill({ objective, status }: Props) {
  const color = status === 'complete' ? 'bg-green-600' : status === 'paused' ? 'bg-amber-600' : 'bg-blue-600';
  return (
    <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-white ${color}`}>
      <span className="text-xs uppercase tracking-wide">Goal</span>
      <span className="text-sm font-medium">{objective}</span>
      <span className="text-xs opacity-80">{status}</span>
    </div>
  );
}
```

```tsx
// ui/components/GoalAuditPanel.tsx
'use client';

export function GoalAuditPanel({ missing }: { missing: string[] }) {
  if (missing.length === 0) return <p className="text-green-700">Audit passed. Goal can be completed.</p>;
  return (
    <div>
      <p className="text-red-700 font-semibold">Audit blocked. Missing evidence:</p>
      <ul className="list-disc pl-6">
        {missing.map(item => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
```

---

## 13) Automations (Heartbeat/Cron Concept)

Use automations for long-lived goals:
- Heartbeat: remind/recheck every 30-60 minutes for active incidents.
- Cron: daily summary of goals still active > 24h.

Minimal scheduler stub:

```ts
// goals/goals.automation.ts
export interface GoalAutomationJob {
  id: string;
  goalId: string;
  kind: 'heartbeat' | 'daily_summary';
  intervalMinutes: number;
}

export async function runGoalHeartbeat(goalId: string) {
  // Fetch goal, evaluate stale steps, emit reminder event.
  // Wire to your notification channel (UI toast, Slack, email, etc.).
}
```

---

## 14) Local Rollout Plan

1. Implement schema and store.
2. Add `withAutoGoal` middleware to the first request entry point.
3. Add plan/evidence write calls in your agent execution loop.
4. Implement audit gate before completion endpoint/tool call.
5. Add UI panels for status, plan, and missing evidence.
6. Add heartbeat automation for stale active goals.

---

## 15) Verification Checklist (Run Before Declaring Done)

1. Start a fresh thread/session and confirm a goal appears automatically.
2. Update plan steps and verify only one can be `in_progress`.
3. Attempt completion with missing evidence and confirm it is blocked.
4. Add required evidence and confirm completion succeeds.
5. Confirm usage counters (tokens/time) update and persist.
6. Confirm daily/heartbeat automation emits expected reminders.

---

## 16) Practical "Default On" Policy You Can Keep

In your system/developer prompt (or local orchestrator config), add:

```text
At the start of each new thread, automatically create or ensure an active goal from the user's first actionable request.
Track plan steps during execution.
Require an evidence-based completion audit before marking the goal complete.
```

This is the policy equivalent of "goals always enabled".

---

## 17) Notes Based on Your Reference ZIP

From `Agent_Swarm-main.zip`:
- There is a UI app (`ui/`) on Next.js with React 19 and TypeScript, which is compatible with the component scaffolding above.
- The repository already emphasizes structured runtime loops and verification practices, so the Goals audit gate fits naturally into that architecture.

No files in the attached project were modified.
