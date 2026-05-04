---
name: Sync — Commit, Push & Pull All Nodes
description: >
  Commit all local changes, push to GitHub, then SSH into each remote pioneer
  node (Turing, Hopper, BMO) and run git pull to sync. Lovelace is the LOCAL
  machine — no SSH needed there. Use this when you want to push code and deploy
  to all nodes. Trigger phrases: /sync, sync nodes, push and sync, deploy to all
  nodes, sync all pioneers.
argument-hint: "Optional commit message (default: auto-generated)"
agent: agent
tools:
  - run_in_terminal
  - get_terminal_output
---

You are executing a full repository sync across all Memex pioneer nodes.

## Steps

### 0 — Create rollback point

Before making any changes, tag the current HEAD as a rollback point so any sync can be cleanly undone.

```powershell
cd C:\Users\panca\Documents\GitHub\Agent_Swarm
$rollbackTag = "rollback/" + (Get-Date -Format "yyyy-MM-ddTHH-mm-ss")
git tag $rollbackTag
git push origin $rollbackTag
```

Report the tag name to the user (e.g. `rollback/2026-04-23T14-30-00`). If the repo is completely clean and there is no need to commit, the tag still gets created — it marks the last known good state.

To roll back to this point later:
```powershell
git reset --hard <tag-name>   # local only — then force-push if needed (ask user first)
```

### 1 — Stage and commit local changes

Run the following in the terminal. If `$COMMIT_MSG` was provided as the argument, use it as the commit message. Otherwise generate a one-line conventional-commit message that summarises the staged diff (e.g. `feat: add agent swarm UX panel`).

```powershell
cd C:\Users\panca\Documents\GitHub\Agent_Swarm
git add -A
git diff --cached --stat
```

Show the diff stat to the user, then commit:

```powershell
git commit -m "<commit message>"
```

If there is nothing to commit (exit code 1 / "nothing to commit"), skip to step 2 and note it.

### 2 — Push to GitHub

```powershell
git push origin main
```

Report the push result. If the push is rejected (non-fast-forward), **stop and ask the user** — do not force-push.

### 3 — Sync each pioneer node via SSH

**Lovelace is the LOCAL machine** — the push in step 2 already updated it. No SSH needed.

For the 3 remote nodes, SSH in and run `git pull`. SSH user is `misterobots`.
On Windows the OpenSSH binary is `C:\Windows\System32\OpenSSH\ssh.exe` — not in PATH.

| Pioneer | IP            | Type   | Repo path       |
|---------|---------------|--------|-----------------|
| Turing  | 192.168.2.103 | Remote | ~/Home_AI_Lab   |
| Hopper  | 192.168.2.102 | Remote | ~/Agent_Swarm   |
| BMO     | 192.168.2.106 | Pi     | ~/Home_AI_Lab   |

```powershell
$ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
& $ssh misterobots@192.168.2.103 'cd $HOME/Home_AI_Lab && git pull --ff-only 2>&1'
& $ssh misterobots@192.168.2.102 'cd $HOME/Agent_Swarm && git pull --ff-only 2>&1'
& $ssh misterobots@192.168.2.106 'cd $HOME/Home_AI_Lab && git pull --ff-only 2>&1'
```

Note: use **single quotes** around the remote command so PowerShell does not expand `$HOME` locally.

Capture and report each exit code and last line of output. If a node is unreachable (connection refused / timeout), log it as **OFFLINE** and continue — do not abort.

### 4 — Summary report

After all steps, output a markdown table:

| Step          | Node          | Result |
|---------------|---------------|--------|
| Rollback tag  | GitHub        | ✅ `rollback/YYYY-MM-DDTHH-MM-SS` created |
| Push          | GitHub        | ✅ pushed / ⏭️ nothing to push |
| Pull          | Turing        | ✅ up-to-date / 🔄 updated / ⚠️ OFFLINE |
| Pull          | Hopper        | … |
| Pull          | BMO           | … |

If any node failed with a merge conflict or non-fast-forward error (not just OFFLINE), flag it clearly and recommend the user SSH in manually to resolve.
