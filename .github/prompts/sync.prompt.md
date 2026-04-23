---
name: Sync — Commit, Push & Pull All Nodes
description: >
  Commit all local changes, push to GitHub, then SSH into each pioneer node
  (Turing, Lovelace, Hopper, BMO) and run git pull to sync. Use this when you
  want to push code and deploy to all nodes. Trigger phrases: /sync, sync nodes,
  push and sync, deploy to all nodes, sync all pioneers.
argument-hint: "Optional commit message (default: auto-generated)"
agent: agent
tools:
  - run_in_terminal
  - get_terminal_output
---

You are executing a full repository sync across all Memex pioneer nodes.

## Steps

### 1 — Stage and commit local changes

Run the following in the terminal. If `$COMMIT_MSG` was provided as the argument, use it as the commit message. Otherwise generate a one-line conventional-commit message that summarises the staged diff (e.g. `feat: add agent swarm UX panel`).

```powershell
cd C:\Users\panca\OneDrive\Documents\GitHub\Agent_Swarm
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

For each node below, SSH in and run `git pull`. Use `misterobots` as the SSH user (or whatever is already in the user's SSH config). The repo path on each node is assumed to be `~/Agent_Swarm` unless the node is BMO (Pi), where it may be `/home/misterobots/Agent_Swarm`.

| Pioneer | IP            | SSH user      | Repo path                          |
|---------|---------------|---------------|------------------------------------|
| Turing  | 192.168.2.103 | misterobots   | ~/Agent_Swarm                      |
| Lovelace| 192.168.2.101 | misterobots   | ~/Agent_Swarm                      |
| Hopper  | 192.168.2.102 | misterobots   | ~/Agent_Swarm                      |
| BMO     | 192.168.2.106 | misterobots   | /home/misterobots/Agent_Swarm      |

Run each pull sequentially:

```powershell
ssh misterobots@192.168.2.103 "cd ~/Agent_Swarm && git pull --ff-only"
ssh misterobots@192.168.2.101 "cd ~/Agent_Swarm && git pull --ff-only"
ssh misterobots@192.168.2.102 "cd ~/Agent_Swarm && git pull --ff-only"
ssh misterobots@192.168.2.106 "cd /home/misterobots/Agent_Swarm && git pull --ff-only"
```

Capture and report each exit code and last line of output. If a node is unreachable (connection refused / timeout), log it as **OFFLINE** and continue — do not abort.

### 4 — Summary report

After all steps, output a markdown table:

| Step | Node | Result |
|------|------|--------|
| Push  | GitHub        | ✅ pushed / ⏭️ nothing to push |
| Pull  | Turing        | ✅ up-to-date / 🔄 updated / ⚠️ OFFLINE |
| Pull  | Lovelace      | … |
| Pull  | Hopper        | … |
| Pull  | BMO           | … |

If any node failed with a merge conflict or non-fast-forward error (not just OFFLINE), flag it clearly and recommend the user SSH in manually to resolve.
