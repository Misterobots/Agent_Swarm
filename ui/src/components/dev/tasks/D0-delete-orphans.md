# Task D0 — Delete orphaned files

**Status:** Ready (no blockers)  
**Conflict zones touched:** none  
**Estimated effort:** 5 minutes

---

## Context

The `dev/` folder contains several files that no live code path imports. They
are leftovers from earlier workspace iterations and editor-merge conflicts.
Keeping them causes two problems:

1. An agent reading the directory thinks these components are active and may
   edit them instead of the real live files.
2. `dev-workspace-working.tsx` imports `FileTree`, `DevOpsPanel`, `GitPanel`,
   and `LogViewer`, making them appear "used" when the file itself is never
   imported by anything.

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

### Delete ONLY after P0 is confirmed merged

`dev-workspace-working.tsx` is the P0 integration scaffold. It imports the
stub panels (file-tree, git-panel, devops-panel, log-viewer) that W1/Q2/Q3/Q7
will revive. Delete it only after those tasks have migrated their panels to the
registry and P0 marks the scaffold done.

| File | Wait for |
|------|----------|
| `ui/src/components/dev/dev-workspace-working.tsx` | P0 merged |

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

4. Do **not** delete `dev-workspace-working.tsx` — add a comment to the top if
   you want to signal it is pending P0, but leave the file.

---

## Acceptance criteria

- `git status` shows only the deleted files above
- `npm run build` (or `next build`) completes without errors
- No broken imports (TypeScript would surface these at build time)
