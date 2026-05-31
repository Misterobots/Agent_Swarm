# Task D2 — Token sweep in page.tsx

**Status:** Ready (no blockers, but `../../app/dev/page.tsx` is a conflict-zone file — claim it in the tracker before branching)  
**Conflict zones touched:** `../../app/dev/page.tsx`  
**Estimated effort:** 30 minutes  
**Dependencies:** none

---

## Context

`ui/src/app/dev/page.tsx` has four problems introduced before the Memex token
system matured:

1. **Agent Mode active = `bg-green-600 text-white`** — a hardcoded green that
   doesn't exist in any Memex theme. On LCARS or Dune it clashes visibly; on
   light mode it's still wrong because `text-white` loses contrast.

2. **Files button active = `text-white`** — same problem. Breaks on light + LCARS.

3. **Gear button has no `onClick`** — it's inert UI that misleads users into
   thinking there's a settings panel.

4. **"Files" toggle is a dead control** — it writes `showFileTree` to the store
   but `dev-workspace.tsx` never reads `showFileTree`. The file tree (task W1)
   hasn't landed yet. Showing the button implies a feature that doesn't exist.

---

## Changes — exact before/after

### Fix 1: Agent Mode button (lines 39–50)

**Before:**
```tsx
<button
  onClick={() => setAgentEnabled(!agentEnabled)}
  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors ${
    agentEnabled
      ? "bg-green-600 text-white"
      : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
  }`}
  title="Toggle agent mode (file + terminal access)"
>
  <Bot size={14} />
  Agent Mode
</button>
```

**After:**
```tsx
<button
  onClick={() => setAgentEnabled(!agentEnabled)}
  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors ${
    agentEnabled
      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
      : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
  }`}
  title="Toggle agent mode (file + terminal access)"
>
  <Bot size={14} />
  Agent Mode
</button>
```

Reference: `design-mode-toggle.tsx` uses the identical active-state pattern.

---

### Fix 2: Files button — remove it entirely (lines 25–36)

The `showFileTree` toggle is a dead control until task W1 (file tree wiring)
lands. Remove the button rather than leave broken UI:

**Before:**
```tsx
<button
  onClick={() => setShowFileTree(!showFileTree)}
  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors ${
    showFileTree
      ? "bg-[var(--chat-accent)] text-white"
      : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
  }`}
  title="Toggle file tree"
>
  <FolderTree size={14} />
  Files
</button>
```

**After:** delete the entire button block.

When W1 lands and the file tree is real, this button should be re-added using
the same accent blend pattern as Fix 1 above (and `text-[var(--chat-accent-strong)]`
for active state, not `text-white`).

---

### Fix 3: Gear button — remove it (lines 52–58)

**Before:**
```tsx
<button
  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
  title="Workspace settings"
>
  <Settings size={14} />
</button>
```

**After:** delete the entire button block.

Re-add when a dev-settings popover is built (not scoped to any current task).

---

### Fix 4: Clean up unused imports

After removing the Files and Settings buttons, remove the now-unused imports:

**Before (line 5):**
```tsx
import { FolderTree, Eye, Settings, Bot, Layers } from "lucide-react";
```

**After:**
```tsx
import { Bot } from "lucide-react";
```

Also remove the destructured store values that are now unused:

**Before (lines 9–12):**
```tsx
const {
  showFileTree,
  agentEnabled,
  setShowFileTree,
  setAgentEnabled,
} = useDevStore();
```

**After:**
```tsx
const {
  agentEnabled,
  setAgentEnabled,
} = useDevStore();
```

---

## Result

The page.tsx toolbar will have exactly two controls:
- The `<h1>Developer Workspace</h1>` label (unchanged)
- The **Agent Mode** toggle button, properly themed

This is intentionally minimal. The toolbar will grow again as D3, W1, and the
dev-settings popover land — but each addition should use the token system from
the start.

---

## Acceptance criteria

- [ ] "Agent Mode" active state uses teal/accent colour matching the chat mode
  toggles — not green
- [ ] No `text-white` in the toolbar
- [ ] "Files" button is gone
- [ ] Gear Settings button is gone
- [ ] No TypeScript errors (all removed imports and destructures cleaned up)
- [ ] `npm run build` passes
- [ ] Switching to Memex light theme: Agent Mode still readable (accent-strong
  is dark on light backgrounds)
- [ ] Switching to LCARS amber: Agent Mode takes on the purple accent
