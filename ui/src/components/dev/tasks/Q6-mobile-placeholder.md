# Task Q6 — Mobile placeholder

**Status:** ⚠️ Previously claimed as shipped — live code shows it was NOT merged. Re-implement from scratch.  
**Conflict zones touched:** `dev-workspace.tsx` (conflict-zone — claim before branching)  
**Estimated effort:** 1 hour  
**Dependencies:** P0 (listed in tracker, but the fix itself doesn't require P0's panel registry — only the mobile branch of `dev-workspace.tsx`)

---

## Problem

`dev-workspace.tsx:30–35` contains a hard redirect:

```tsx
// Redirect to chat on mobile — Dev workspace is desktop-only
useEffect(() => {
  if (isMobile) router.replace("/chat");
}, [isMobile, router]);

if (isMobile) return null;
```

This is a poor experience: the user taps "Dev" in the nav, the page flashes,
and they land in Chat with no explanation. They have no idea the tab exists or
why they were redirected.

The fix (originally scoped as Q6) replaces the silent redirect with an
in-place informational placeholder so the user understands what Dev is and
why it requires a larger screen.

---

## Implementation

### 1. Remove the redirect

Delete the `useEffect` redirect block and the `if (isMobile) return null` guard:

```tsx
// DELETE these lines (32–35):
useEffect(() => {
  if (isMobile) router.replace("/chat");
}, [isMobile, router]);

// DELETE this line (35):
if (isMobile) return null;
```

Keep `const { isMobile } = useIsMobile();` — it's used by the conditional below.

Also remove the `useRouter` import and call if nothing else uses it in this file:
```tsx
// Remove if unused after the redirect is gone:
import { useRouter } from "next/navigation";
const router = useRouter();
```

### 2. Add a mobile placeholder branch

In the component's return, wrap the existing layout in a desktop-only branch
and add a mobile placeholder:

```tsx
export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  // ... existing store destructure ...

  // Mobile: show an informational placeholder instead of redirecting
  if (isMobile) {
    return <DevMobilePlaceholder />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* ... existing layout unchanged ... */}
    </div>
  );
}
```

### 3. Create the placeholder component

Add this below the `DevWorkspace` function in the same file (or extract to
`dev-mobile-placeholder.tsx` if you prefer):

```tsx
function DevMobilePlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 py-12 text-center gap-6">
      {/* Icon */}
      <div
        className="w-14 h-14 rounded-xl flex items-center justify-center
                   text-[var(--chat-accent)] flex-shrink-0"
        style={{
          background: "var(--chat-accent-soft)",
          border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
          boxShadow: "var(--elev-1)",
        }}
      >
        <Monitor size={24} />
      </div>

      {/* Heading */}
      <div className="space-y-2 max-w-xs">
        <h2 className="text-base font-semibold text-[var(--chat-text)]">
          Dev workspace requires a larger screen
        </h2>
        <p className="text-sm text-[var(--chat-muted)] leading-relaxed">
          The code editor and terminal are desktop-only. Open Memex on a
          laptop or desktop to access the Dev workspace.
        </p>
      </div>

      {/* What's here note */}
      <div
        className="w-full max-w-xs rounded-lg px-4 py-3 text-left space-y-1.5"
        style={{
          background: "var(--chat-panel)",
          border: "1px solid var(--chat-border)",
        }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
          Available on desktop
        </p>
        <ul className="text-xs text-[var(--chat-muted)] space-y-1">
          <li>· Monaco code editor with multi-tab support</li>
          <li>· Integrated terminal (SSH / Docker)</li>
          <li>· Live preview canvas</li>
          <li>· One-click git pull + container restart</li>
        </ul>
      </div>
    </div>
  );
}
```

### 4. Add the `Monitor` import

`Monitor` is from lucide-react. Check if it's already imported in the file;
if not, add it:

```tsx
import { Code2, Eye, FileCode, Terminal, X, Users, Monitor } from "lucide-react";
```

---

## Mobile policy reminder (from AGENTS.md)

Task **M1** (pending, deps W2) will add a real read-only mobile Dev view with
project chip, goals, git status, and recent files. When M1 lands, this
placeholder should be replaced by `<MobileDevView />` — not expanded in-place.

**Do NOT add editor, terminal, or git-mutation UI to the mobile branch.**
The placeholder is intentionally read-only and informational.

---

## Acceptance criteria

- [ ] Navigating to `/dev` on a mobile viewport (<768px) shows the placeholder card,
  **not** a redirect to `/chat`
- [ ] The placeholder is on-theme (updates when the theme picker changes)
- [ ] Navigating to `/dev` on desktop shows the normal workspace unchanged
- [ ] No TypeScript errors
- [ ] `npm run build` passes
- [ ] The `router.replace("/chat")` call is gone from the file entirely
