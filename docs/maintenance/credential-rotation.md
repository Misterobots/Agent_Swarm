# Credential exposure audit — turing_gateway/.env values in git history

**Run:** 2026-05-08, against current `main` and all reachable refs.
**Method:** `git log -S<token>` across all branches for each value currently
in `turing_gateway/.env`.

`turing_gateway/.env` itself has never been tracked (in `.gitignore`), but
the values in it appeared in other committed files at various points.

## Findings

| Value | Where | Commits | Action |
| --- | --- | --- | --- |
| Grafana admin pw `jck…` (8-char) | (committed) | `bdc72df`, `006776d` | **ROTATE** — already public |
| Postgres pw `agno…ively` | (committed) | `7e7541c` | **ROTATE** — already public |
| Authentik DB pw `Ffy…` (20-char) | (committed) | `80214de`, `27ac415`, `549be87`, `7054af6` | **ROTATE** — heavy exposure |
| Old SMTP `Lin…` | (committed) | `4cf6b91` | Already rotated 2026-05-08 ✓ |
| ntfy bcrypt hash `$2a$10$YLi…` | committed default | `60396b8`, `27ac415`, `ca6412c` | **ROTATE** the underlying password |
| ntfy alert token `tk_1234…` | committed default | `60396b8`, `27ac415`, `ca6412c` | **ROTATE** |
| Grafana secret key `hive_…_v1` | (committed) | `549be87`, `7054af6` | **ROTATE** — used for session signing |
| VSCode sudo `shi…` | ambiguous (also a surname; many false positives) | 5+ commits | Inspect manually before rotating |

The exact values are in `turing_gateway/.env` (gitignored) on this machine
and in the listed commits in git history. Redacted here so this doc itself
isn't a fresh leak vector.

The `shively` matches mostly look like documentation referencing the user's
name, but at least one commit is worth eyeballing to confirm.

## Why "ROTATE" not "rewrite history"

Anyone who could see the repo while these were in `main` already has the
values. Rewriting history (filter-repo, BFG) doesn't help once a secret is
out — only rotation does. Also, rewriting `main` would break every working
copy and force a fleet-wide reclone.

## Suggested rotation order

Lowest blast radius first so you can validate the process before touching
anything load-bearing:

1. **Grafana admin (`jcknows1`)** — log into Grafana, change pw in Profile →
   Account, update `GF_SECURITY_ADMIN_PASSWORD` in
   `turing_gateway/.env`, restart `grafana-turing`. Verify: log in with new pw.
2. **Grafana secret key (`hive_secret_key_for_persistence_v1`)** — change
   `GF_SECURITY_SECRET_KEY` in `.env` to a fresh `openssl rand -hex 32`,
   restart Grafana. All existing sessions invalidate; users re-log.
3. **ntfy admin password + alert token** — `docker exec ntfy-Turing ntfy
   user change-pass ntfyadmin`, then update
   `turing_gateway/.env: NTFY_ADMIN_PASSWORD_HASH` with the new bcrypt;
   regenerate `NTFY_ALERT_TOKEN` (any random `tk_` string of similar length;
   `ntfy token add ntfyadmin` and capture the output). Update Alertmanager
   webhook config if it references the old token. Restart ntfy.
4. **Postgres `agno` user** — `ALTER USER agno WITH PASSWORD '...';` on
   Hopper; update `AGNO_DB_URL` in `.env`; rolling-restart agent_runtime
   plus anything else that connects.
5. **Authentik DB pw** — heaviest blast radius (Authentik fronts SSO for
   the whole stack). Coordinate with the team. `ALTER USER misterobots
   WITH PASSWORD '...';` then update both `AUTHENTIK_DB_PASSWORD` and
   wherever Authentik itself is configured (its own compose file
   references this same secret). Restart Authentik server + worker.
6. **VSCode passwords** — only if `shively` actually is the live sudo
   password. Update both `VSCODE_PASSWORD` and `VSCODE_SUDO_PASSWORD`,
   restart the IDE containers.

After each rotation: re-run this audit script (see below) to confirm the
*old* value is no longer referenced anywhere live (only in history, which
is acceptable post-rotation).

## Re-audit command

```bash
for tok in "<old-value-1>" "<old-value-2>"; do
  echo "=== $tok ==="
  git grep -n "$tok" || true
done
```

Once rotated, the *new* values must never appear in tracked files. Compose
references should always be `${VAR:?error message}` form, never `${VAR:-default}`.

## Already done

- ✅ SMTP password rotated and moved out of `alertmanager.yml` (2026-05-08).
- ✅ ntfy bcrypt hash + alert token defaults removed from
  `turing_gateway/docker-compose.yml`; compose now requires the env vars.
