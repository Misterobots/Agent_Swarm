# Dev Workspace — Frontend Coordination Notes

This directory hosts the `/dev` route UI. Multiple agents may be working in
parallel worktrees on continuity features. **Read this before editing.**

---

## ⚠️ Conflict-zone rules

Files that multiple workstreams touch — coordinate before editing:

| File | Rule |
|------|------|
| `dev-workspace.tsx` | **Do not add new panels directly.** Register via the panel registry (see below). P0 owns migration of built-in panels to the registry. |
| `../../lib/stores/dev-store.ts` | **Frozen.** It is being replaced by per-concern slice stores (see below). P0 updates the facade to re-export from slices. After P0 merges, it is a thin wrapper only. |
| `../../app/dev/page.tsx` | Single-owner edits. Claim in the task tracker before touching. |
| `../../app/api/devops/git/status/route.ts` | Single-owner edits (task Q3). |
| `tabbed-editor.tsx` | Theme-reactivity work (task D1) owns Monaco `theme` prop — do not hardcode `"vs-dark"`. |
| `tabbed-terminal.tsx` | Theme-reactivity work (task D1) owns xterm palette object and background — do not hardcode ANSI colors or `#0a0a14`. |

If you need to edit a conflict-zone file, set `owner` on your task in the
tracker **before** opening a branch, so others can see it's claimed.

---

## Store slices (pre-created)

State lives in 4 slice stores under `ui/src/lib/stores/`:

| Slice file | State owned | Primary writer |
|------------|-------------|----------------|
| `dev-editor-store.ts` | editorContent, activeFile, editorLanguage, selectedText | W1 |
| `dev-agent-store.ts` | agentEnabled, editorSyncEnabled, sessionAutoApprove | Q1 |
| `dev-project-store.ts` | currentProjectId, projects[] | W3 |
| `dev-panel-store.ts` | show* flags, viewMode, terminalTabs, selectedNode | P0 |

**Import from the specific slice in new code**, not from `dev-store`:
```ts
// ✅ good
import { useDevEditorStore } from "@/lib/stores/dev-editor-store";

// ⚠️ legacy — still works, but not for new code
import { useDevStore } from "@/lib/stores/dev-store";
```

`useDevStore` remains as a backwards-compatible facade during the transition.
After all components are migrated, it will be removed.

---

## Panel registry

New flyout panels register in `dev-panels-registry.ts` rather than editing
`dev-workspace.tsx`. Call `registerPanel()` at module scope in your panel file:

```ts
import { registerPanel } from "./dev-panels-registry";
import React from "react";
import { YourIcon } from "lucide-react";
import { YourPanel } from "./your-panel";

registerPanel({
  id: "your-panel",
  title: "Your Panel",
  position: "right",            // "right" | "bottom"
  icon: React.createElement(YourIcon, { size: 14 }),
  component: YourPanel,
  toolbarOrder: 40,             // Editor=10, Terminal=20; use 30+ for new panels
});
```

Then import your panel file from `dev-workspace.tsx` (one new import line —
the only change you need to make to that file). The panel is rendered
automatically.

Reserved `toolbarOrder` slots:
- 10 — Editor (built-in)
- 20 — Terminal (built-in)
- 30 — Goals (Q5)
- 40–90 — available for future panels

---

## Backend API

All agent-runtime requests go through `/api/backend/v1/...`. The proxy at
`ui/src/app/api/backend/[...path]/route.ts` forwards Authentik headers
automatically. **Never set auth headers manually** in client-side fetch calls.

| Endpoint | Used by | Status |
|----------|---------|--------|
| `/v1/dev/sessions/*` | W2 — session sync hook | ⚙️ stub (F1) |
| `/v1/dev/files/*` | W1 — file tree; W4 — notes | ⚙️ stub (F2) |
| `/v1/dev/projects/*` | W3 — project switcher | ⚙️ stub (F3) |
| `/v1/goals/*` | Q5 — goals panel | ✅ live |
| `/v1/chat/completions` | chat-view | ✅ live |
| `/api/v1/dev/approve/{call_id}` | tool approval | ✅ live |
| `/api/v1/dev/deny/{call_id}` | tool denial | ✅ live |
| `/ws/terminal` | terminal-pane | ✅ live |
| `/api/devops/git/*` | git-panel, quick-actions-toolbar | ⚠️ partial (Q2, Q3) |
| `/api/devops/ssh` | quick-actions-toolbar | ✅ live |
| `/api/devops/logs/stream` | log-viewer | ⚠️ stub (Q7) |

---

## Agent mode (existing)

When `agentEnabled` is `true` (from `dev-agent-store`) and chat renders with
`showDevContext={true}`, requests carry `dev_mode=true` and the runtime
executes tool calls behind user approval gates.

- Approve: `POST /api/backend/api/v1/dev/approve/{call_id}` + `{scope}`
- Deny: `POST /api/backend/api/v1/dev/deny/{call_id}`
- Scopes: `"none"` (one-time), `"session"` (this session), `"workspace"` (persisted)

Session auto-approves live in `dev-agent-store.sessionAutoApprove`.
Workspace auto-approves are persisted server-side in `workspace_auto_approve.json`.

---

## Mobile policy

`/dev` is desktop-only for the editor and terminal. `useIsMobile()` returns
`{ isMobile, isTablet }` based on viewport width (mobile < 768px).

- **Q6** ⚠️ **claimed shipped but NOT merged** — live `dev-workspace.tsx:32-35`
  still contains the hard `router.replace("/chat")`. Re-implement: replace
  the redirect with an in-place placeholder card explaining the limitation.
- **M1** (pending, deps W2): adds a real read-only mobile view — project chip,
  goals, git status, recent files. **Do NOT add editor, terminal, or any
  git-mutation UI on mobile.**

---

## Active tasks at a glance

| ID | Task | Owns | Dep |
|----|------|------|-----|
| P0 | Coordination scaffolding | dev-workspace.tsx shell, dev-store facade | — |
| Q1 | Persist editor state | dev-agent-store | P0 |
| Q2 | Missing Git routes | new api/devops/git/{commit,stage,unstage}/ | — |
| Q3 | Fix git status | api/devops/git/status/route.ts | — |
| Q4 | Auth defense-in-depth | dev/page.tsx, terminal-pane.tsx | — |
| Q5 | Goals widget | goals-panel.tsx + registry | P0 |
| Q6 | Mobile placeholder ⚠️ not merged — hard redirect still in codebase | dev-workspace.tsx (mobile branch) | P0 |
| Q7 | Log streaming | api/devops/logs/stream/route.ts | — |
| W1 | File tree wiring | file-tree.tsx, editor-pane.tsx | F2 |
| W2 | Session sync hook | use-dev-session-sync.ts | F1 |
| W3 | Project switcher | project-switcher.tsx | F3 |
| W4 | Notes panel | notes-panel.tsx | F2+F3 |
| W5 | Cross-surface pill | chat-view.tsx, use-chat-stream.ts | F3+W4 |
| M1 | Mobile dev view | mobile-dev-view.tsx | W2 |
| D0 | Delete orphaned files | see safe-delete list below | — |
| D1 | Theme-reactive editor + terminal | tabbed-editor.tsx, tabbed-terminal.tsx | — |
| D2 | Token sweep | app/dev/page.tsx | — |
| D3 | Pioneers reskin | pioneers/page.tsx | — |
| S1 | Per-conversation mode state | types/chat.ts, chat-store.ts, use-chat-stream.ts, all toggle components, workflow-actions-card.tsx | — |

---

## Visual / theme debt

Identified by design review (2026-05-31). Tasks D0–D3 are **not blocked on P0**
— they touch no conflict-zone files and can land independently in any order.

### Safe-delete list (D0)

Files no active task references. Verify nothing new imports them before deleting.

- `dev-workspace-old.tsx.bak`
- `dev-workspace-flyout.tsx`
- `dev-workspace-working.tsx` — only after W1/W2/W3/W4 panels have migrated to
  the registry and P0 is confirmed merged; it is the integration scaffold
- `../../app/dev/page_stub.tsx`
- `dev-error-boundary.tsx` — exported but never imported anywhere
- `../../components/chat/chat-view-Justin-PC.tsx` and all other `*-Justin-PC.*`
  editor-conflict copies across `components/` and `app/`

### D1 — Theme-reactive editor + terminal

`tabbed-editor.tsx:273` hardcodes `theme="vs-dark"` on Monaco. Every Memex
theme (LCARS variants, Dune, Blade Runner, Memex light mode…) results in a
black editor slab that ignores the active theme.

`tabbed-terminal.tsx:152–174, 218` hardcodes ANSI palette and `#0a0a14`
background regardless of theme.

**Fix:** maintain a small `themeId → MonacoTheme + XtermOptions.theme` map
driven by `useSettingsStore(s => s.theme)` and `s.themeMode`. CSS variables
alone are insufficient — both libraries require a JS theme object. Define and
register a custom Monaco theme with `monaco.editor.defineTheme()` per active
Memex theme; xterm accepts `ITheme` in its constructor options.

> **Conflict-zone reminder**: do not touch the Monaco `theme` prop or the xterm
> `theme` constructor object without owning task D1.

### D2 — Token sweep in page.tsx

`app/dev/page.tsx:43–50` Agent Mode active state uses `bg-green-600 text-white`
— a hardcoded green that exists in no Memex theme. Replace with:
```
bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)]
text-[var(--chat-accent-strong)]
border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]
```
Reference: `design-mode-toggle.tsx` (active branch).

`page.tsx:27–36` Files button active uses `text-white` — breaks on light and
LCARS themes. Use `text-[var(--chat-accent-strong)]`.

`page.tsx:53–57` Gear Settings button has no `onClick` — remove it or wire to
a dev-settings popover (not yet built; block on that work or remove for now).

`page.tsx:9–11, 27` `showFileTree` toggle writes `dev-store` but live
`dev-workspace.tsx` never reads `showFileTree` — **dead control** until W1
lands. Remove the button for now to avoid confusing users.

Global reference: `.btn-secondary`, `color-mix` accent blends,
`--chat-accent-strong/soft` — `globals.css:1271–1321`.

### D3 — Pioneers reskin

`pioneers/page.tsx` uses hardcoded gradients (`from-purple-500 to-pink-500`,
`from-blue-500 to-cyan-500`, etc.), literal status colors, and sci-fi copy
("consciousness parameters", "SYNCHRONIZED") that conflicts with the editorial
tone of the rest of Memex.

Reskin checklist:
- Replace bespoke gradient agent cards with `<Card interactive>` from
  `components/ui/card.tsx`
- Status dots: `w-2 h-2 rounded-full bg-emerald-400 animate-pulse` (already
  used in sidebar footer — match that pattern exactly)
- Role badges: `color-mix(in srgb, var(--chat-accent) 18%, transparent)` +
  `text-[var(--chat-accent-strong)]` border blend
- Replace gradient letter-avatars with `bg-[var(--chat-panel)]` + accent border
  `w-10 h-10 rounded-md flex items-center justify-center` — no hardcoded colors
- Remove the animated scrolling grid background (`gridScroll` keyframe)
- Tone down copy: drop "consciousness parameters", "SYNCHRONIZED", "Neural Core"
  in favour of plain "Model" / "Role" labels

Consider moving the roster to `/settings` next to `TeamBuilderSettings` and
making the 7 hardcoded JSX cards data-driven from the actual team config.

### Stale port data in devops-panel.tsx (for Q2/Q3 owners)

`devops-panel.tsx:41–47` lists wrong host ports (per `CLAUDE.md`):

| Service | Listed | Correct |
|---------|--------|---------|
| `agent_runtime` | `:5001` | `:8008` |
| `memex_ui` | `:3000` | `:3200` |
| `Langfuse` | `:3001` | `:3000` |

Fix these constants when reviving the panel for Q2/Q3.
