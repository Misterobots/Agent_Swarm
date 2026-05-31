# Task D3 — Pioneers reskin

**Status:** Ready (no blockers)  
**Conflict zones touched:** none (`pioneers/page.tsx` is not in the conflict-zone table)  
**Estimated effort:** 2–4 hours  
**Dependencies:** none (purely visual)

---

## Problem

`ui/src/app/dev/pioneers/page.tsx` was designed in a different era and uses a
sci-fi cyberpunk aesthetic that no longer matches the rest of Memex:

- 7 agent cards each have a unique hardcoded gradient
  (`from-purple-500 to-pink-500`, `from-blue-500 to-cyan-500`, etc.)
- Status bar uses literal `cyan-500`, `purple-500`, `green-500` dots
- Animated background grid (`gridScroll` keyframe, `opacity-10`)
- Header has `bg-gradient-to-r from-[var(--chat-accent)] to-cyan-400` title
- Copy uses "consciousness parameters", "Neural Core", "SYNCHRONIZED" —
  tech-flavour that conflicts with the product's editorial tone
- Agent roster is hardcoded JSX — 7 cards, not data-driven

The page still wraps the real `<TeamBuilderSettings />` component which is
well-designed. The goal is to make the chrome around it feel like it belongs
in Settings, not a game UI.

---

## Component primitives to use

All are already in the repo — do not introduce new dependencies.

| Pattern | Import / class |
|---------|----------------|
| Card container | `import { Card, CardHeader, CardTitle } from "@/components/ui/card"` |
| Button | `import { Button } from "@/components/ui/button"` |
| Primary surface | `.surface` CSS class (or `<Card>`) |
| Active/role badge | `color-mix(in srgb, var(--chat-accent) 18%, transparent)` + `text-[var(--chat-accent-strong)]` |
| Status dot | `w-2 h-2 rounded-full bg-emerald-400 animate-pulse` (sidebar footer pattern) |
| Section header | `text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]` |
| Page back button | same pattern as other sub-pages — `text-[var(--chat-muted)] hover:text-[var(--chat-accent)]` |

---

## Page-level changes

### 1. Remove the animated grid background

**Delete** the entire `<div>` with class `absolute inset-0 opacity-10` and
its inline `backgroundImage` / `animation` style. Also delete the `<style jsx>`
block at the bottom that defines `@keyframes gridScroll`.

### 2. Simplify the header

**Before:**
```tsx
<div className="relative overflow-hidden border-b border-[var(--chat-border)]">
  {/* Animated background grid */}
  <div className="absolute inset-0 opacity-10" style={{ ... }} />

  <div className="relative px-6 py-6">
    ...
    <h1 className="text-3xl font-bold bg-clip-text text-transparent
                   bg-gradient-to-r from-[var(--chat-accent)] to-cyan-400">
      Pioneer Academy
    </h1>
    <Sparkles size={20} className="text-[var(--chat-accent)] animate-pulse" />
    ...
    <p className="text-[var(--chat-muted)] mt-1 text-sm">
      Assemble your elite team of AI pioneers • Configure roles,
      capabilities, and consciousness parameters
    </p>
  </div>
</div>
```

**After:**
```tsx
<div className="px-6 py-5 border-b border-[var(--chat-border)]">
  <button
    onClick={() => router.push("/dev")}
    className="flex items-center gap-1.5 text-xs text-[var(--chat-muted)]
               hover:text-[var(--chat-accent)] transition-colors mb-4 group"
  >
    <ArrowLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
    Back to Dev
  </button>

  <div className="flex items-center gap-3">
    <div
      className="w-9 h-9 rounded-md flex items-center justify-center
                 text-[var(--chat-accent)] flex-shrink-0"
      style={{
        background: "var(--chat-accent-soft)",
        border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
      }}
    >
      <Users size={18} />
    </div>
    <div>
      <h1 className="text-base font-semibold text-[var(--chat-text)]">
        Pioneer Academy
      </h1>
      <p className="text-xs text-[var(--chat-muted)] mt-0.5">
        Configure your AI agent team — roles, models, and capabilities
      </p>
    </div>
  </div>
</div>
```

Remove the "Mission Brief" and "Stats Bar" sections entirely. They are
decorative and the copy is out of tone.

---

## Agent card changes

### Current structure (repeated 7×)

Each card is a bespoke div with a unique gradient avatar, hardcoded badge
color, and hardcoded `animate-pulse` status dot. They are not data-driven.

### Target structure

Replace the 7 hardcoded cards with a **data-driven** list using `<Card interactive>`.

**Step 1: Define the agent data at the top of the file**

```tsx
const PIONEERS = [
  {
    id: "ada",
    name: "Ada",
    role: "Coordinator",
    description:
      "Mission planner and orchestrator. Decomposes complex tasks and coordinates across agents.",
    model: "qwen3:14b",
    active: true,
  },
  {
    id: "turing",
    name: "Turing",
    role: "Architect",
    description:
      "System designer and technical lead. Plans architectures and defines technical specifications.",
    model: "qwen2.5-coder:14b",
    active: true,
  },
  {
    id: "grace",
    name: "Grace",
    role: "Coder",
    description:
      "Primary implementation specialist. Writes production code and handles file operations.",
    model: "qwen2.5-coder:14b",
    active: true,
  },
  {
    id: "dennis",
    name: "Dennis",
    role: "DevOps",
    description:
      "Infrastructure guardian. Manages containers, orchestrates deployments, writes scripts.",
    model: "qwen3:8b",
    active: true,
  },
  {
    id: "margaret",
    name: "Margaret",
    role: "Researcher",
    description:
      "Knowledge seeker. Explores codebases, searches documentation, builds understanding.",
    model: "llama3.2:3b",
    active: true,
  },
  {
    id: "claude",
    name: "Claude",
    role: "Analyst",
    description:
      "Data interpreter. Analyzes patterns, extracts insights, provides strategic recommendations.",
    model: "qwen3:8b",
    active: true,
  },
  {
    id: "dijkstra",
    name: "Dijkstra",
    role: "Verifier",
    description:
      "Quality guardian and code reviewer. Validates implementations and maintains standards.",
    model: "qwen3:8b",
    active: true,
  },
] as const;
```

**Step 2: Replace the 7 hardcoded cards with a map**

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
  {PIONEERS.map((pioneer) => (
    <Card key={pioneer.id} interactive padding="sm">
      <div className="flex items-start gap-3">
        {/* Avatar — initial in themed container, no gradient */}
        <div
          className="w-9 h-9 rounded-md flex items-center justify-center
                     text-sm font-semibold flex-shrink-0 text-[var(--chat-accent)]"
          style={{
            background: "var(--chat-accent-soft)",
            border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
          }}
        >
          {pioneer.name[0]}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-[var(--chat-text)]">
              {pioneer.name}
            </span>
            {pioneer.active && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
            )}
          </div>

          {/* Role badge */}
          <span
            className="inline-block text-[10px] font-semibold uppercase
                       tracking-wider px-1.5 py-0.5 rounded-sm mb-2"
            style={{
              background: "color-mix(in srgb, var(--chat-accent) 12%, transparent)",
              color: "var(--chat-accent-strong)",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
            }}
          >
            {pioneer.role}
          </span>

          <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-2">
            {pioneer.description}
          </p>

          <div className="flex items-center gap-1.5 text-xs text-[var(--chat-muted)]">
            <span>Model:</span>
            <code className="text-[var(--chat-text)] font-mono text-[11px]">
              {pioneer.model}
            </code>
          </div>
        </div>
      </div>
    </Card>
  ))}
</div>
```

---

## Section header for the roster

Replace the current accent-bar heading with the standard CardTitle pattern:

**Before:**
```tsx
<div className="flex items-center gap-3 mb-6">
  <div className="w-1 h-8 bg-[var(--chat-accent)]" />
  <h2 className="text-2xl font-bold text-[var(--chat-text)]">Active Pioneers</h2>
  <span className="text-sm text-[var(--chat-muted)]">• 7 agents deployed</span>
</div>
```

**After:**
```tsx
<CardTitle className="mb-4">Active Pioneers</CardTitle>
```

The `• 7 agents deployed` count should come from `PIONEERS.filter(p => p.active).length`
if kept, or just be removed.

---

## Team Configuration section

The `<TeamBuilderSettings />` block at the bottom is already well-designed.
Keep it, but wrap in a `<Card>` with standard section header:

```tsx
<Card padding="md" className="mt-6">
  <CardHeader>
    <CardTitle>Team Configuration</CardTitle>
    <p className="text-xs text-[var(--chat-muted)] mt-1">
      Assign models to each Pioneer. Supports local Ollama and cloud providers.
    </p>
  </CardHeader>
  <TeamBuilderSettings />
</Card>
```

---

## Imports to update

```tsx
// Remove:
import { Sparkles, Cpu } from "lucide-react";   // no longer used

// Ensure present:
import { ArrowLeft, Users } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
```

---

## Future consideration (out of scope for D3)

The `PIONEERS` array is currently hardcoded JSX. Ideally it should be fetched
from the backend team config that `TeamBuilderSettings` already reads/writes.
That wiring is deferred — D3 just de-dups the visual, not the data source.
File a follow-up task once `TeamBuilderSettings`'s data API is known.

---

## Acceptance criteria

- [ ] No hardcoded color gradients (`from-*-500`, `to-*-500`) anywhere in the file
- [ ] No `animate-pulse` on the Sparkles icon (ok to keep on status dots)
- [ ] No `@keyframes gridScroll` or animated background grid
- [ ] No "consciousness parameters", "SYNCHRONIZED", "Neural Core" copy
- [ ] Agent cards are rendered from a data array, not 7 individual JSX blocks
- [ ] Page looks at home when navigated to from the sidebar (matches Memex light
  and dark modes, and LCARS)
- [ ] `<TeamBuilderSettings />` still renders correctly below the roster
- [ ] TypeScript clean, `npm run build` passes
