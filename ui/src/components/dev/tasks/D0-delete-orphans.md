# Task D0 — Delete orphaned files

**Status:** Partially completed — legacy workspace scaffold removed
**Conflict zones touched:** none  
**Estimated effort:** 5 minutes

---

## Context

The `dev/` folder contains several files that no live code path imports. They
are leftovers from earlier workspace iterations and editor-merge conflicts.
Keeping them causes two problems:

1. An agent reading the directory thinks these components are active and may
   edit them instead of the real live files.
2. `dev-workspace-working.tsx` previously imported `FileTree`, `DevOpsPanel`,
   `GitPanel`, and `LogViewer`, making them appear "used" when the file itself
   was never imported by anything. DevOps, Git, and Logs are now registry panels.

---

## Files to delete

### Safe to delete immediately

These are referenced by nothing:

| File | Why orphaned |
|------|-------------|
| `ui/src/components/dev/dev-workspace-old.tsx.bak` | Backup of an earlier iteration |
| `ui/src/components/dev/dev-workspace-flyout.tsx` | Superseded by current `dev-workspace.tsx` |
| `ui/src/app/dev/page_stub.tsx` | Stray stub, never routed |
| `ui/src/components/dev/dev-error-boundary.tsx` | `DevErrorBoundary` class exported but never imported anywhere in the repo |
| `ui/src/components/chat/chat-view-Justin-PC.tsx` | Editor-conflict copy |
| `ui/src/app/governance/page-Justin-PC.tsx` | Editor-conflict copy |
| `ui/src/app/offline/page-Justin-PC.tsx` | Editor-conflict copy |
| `ui/src/components/chat/model-selector-Justin-PC.tsx` | Editor-conflict copy (grep confirms no import) |
| `ui/src/components/chat/doc-grounding-toggle-Justin-PC.tsx` | Editor-conflict copy |
| `ui/src/components/chat/file-grounding-toggle-Justin-PC.tsx` | Editor-conflict copy |

### Completed migration

`dev-workspace-working.tsx` was the P0 integration scaffold. Its DevOps, Git,
and Logs sidebar has been migrated to the panel registry; its stale quick-action
toolbar was retired rather than exposing incomplete deployment commands.

| File | Wait for |
|------|----------|
| `ui/src/components/dev/dev-workspace-working.tsx` | Removed |

---

## Steps

1. **Verify no new imports exist** before deleting each file. Run a quick grep:
   ```bash
   # From repo root — substitute the filename
   grep -r "dev-workspace-flyout" ui/src --include="*.ts" --include="*.tsx"
   ```
   If grep returns nothing, it's safe to delete.

2. Delete the files listed in "Safe to delete immediately."

3. Commit with message:
   ```
   chore(dev): remove orphaned workspace files and editor-conflict copies
   ```

4. Verify the active `dev-workspace.tsx` imports each migrated panel for its
   registry side effect before deleting the scaffold.

---

## Acceptance criteria

- `git status` shows only the deleted files above
- `npm run build` (or `next build`) completes without errors
- No broken imports (TypeScript would surface these at build time)
