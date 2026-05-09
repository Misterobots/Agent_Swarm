# Credential exposure audit — turing_gateway/.env values in git history

**Run:** 2026-05-08, against current `main` and all reachable refs.
**Status:** All public credentials rotated 2026-05-08 ✓ (except SMTP, pending Zoho App Password generation).
**Method:** `git log -S<token>` across all branches for each value currently
in `turing_gateway/.env`.

`turing_gateway/.env` itself has never been tracked (in `.gitignore`), but
the values in it appeared in other committed files at various points.

## Findings

| Value | Where | Commits | Action |
| --- | --- | --- | --- |
| Grafana admin pw `jck…` (8-char) | (committed) | `bdc72df`, `006776d` | Rotated 2026-05-08 ✓ via `grafana-cli admin reset-admin-password` + `.env` update |
| Postgres `agno` pw `agno…ively` | (committed) | `7e7541c` | Rotated 2026-05-08 ✓ via `ALTER USER agno`; updated mempalace, agent_runtime, hive_ui, ops_portal, network.env on both Turing and Hopper |
| Authentik DB pw — Saltbox public default `password4321` | upstream Saltbox public repo (`roles/postgres/defaults/main.yml`) | n/a — public default | Rotated 2026-05-08 ✓ via `ALTER USER misterobots` + `postgres_role_docker_env_password` override in `inventories/host_vars/localhost.yml` + `sudo sb install authentik` (worker recreated under same role) |
| Old SMTP `Lin…` | (committed) | `4cf6b91` | Rotated 2026-05-08 ✓ (still pending: Zoho App Password — current value 535s against Zoho; likely 2FA requires app-specific password) |
| ntfy bcrypt hash `$2a$10$YLi…` | committed default | `60396b8`, `27ac415`, `ca6412c` | Rotated 2026-05-08 ✓ — new password + fresh `htpasswd -nbBC 10` bcrypt |
| ntfy alert token `tk_1234…` | committed default | `60396b8`, `27ac415`, `ca6412c` | Rotated 2026-05-08 ✓ via `ntfy token generate`; alertmanager webhook now uses `Authorization: Bearer` via `credentials_file` tmpfs |
| Grafana secret key `hive_…_v1` | (committed) | `549be87`, `7054af6` | Rotated 2026-05-08 ✓ — fresh `openssl rand -hex 32`; existing Grafana sessions invalidated |
| VSCode sudo `shi…` | ambiguous (also a surname; many false positives) | 5+ commits | **Open** — inspect manually before rotating |

The exact values were in `turing_gateway/.env` (gitignored) on this machine
and in the listed commits in git history. Redacted here so this doc itself
isn't a fresh leak vector.

The `shively` matches mostly look like documentation referencing the user's
name, but at least one commit is worth eyeballing to confirm — outstanding.

## Why "ROTATE" not "rewrite history"

Anyone who could see the repo while these were in `main` already has the
values. Rewriting history (filter-repo, BFG) doesn't help once a secret is
out — only rotation does. Also, rewriting `main` would break every working
copy and force a fleet-wide reclone.

## Rotation order used (lowest blast radius first)

1. **Grafana admin** — `docker exec hollerith-turing grafana-cli admin reset-admin-password '<new>'`; updated `GF_SECURITY_ADMIN_PASSWORD` in `.env`. Verified by HTTP basic-auth GET against `/api/org`.
2. **Grafana secret key** — fresh `openssl rand -hex 32`, recreated `hollerith` container. All existing Grafana sessions invalidated; users re-log.
3. **ntfy admin pw + alert token** — generated bcrypt with `htpasswd -nbBC 10`, generated token via `ntfy token generate`. Note: in `turing_gateway/.env` the bcrypt hash needs `$$` to escape compose interpolation (e.g. `NTFY_ADMIN_PASSWORD_HASH=$$2y$$10$$…`).
4. **Postgres `agno`** — `ALTER USER agno WITH PASSWORD '<new>';` on Hopper postgres; updated AGNO_DB_URL on three .env files (Turing turing_gateway/.env, Turing-side network.env, Turing r730_gateway/.env, Hopper Agent_Swarm/network.env). Recreated mempalace (Hopper) and agent_runtime, hive_ui, ops_portal (Turing).
5. **Authentik DB** — `ALTER USER misterobots WITH PASSWORD '<new>';` inside `authentik-postgres`. Saltbox-managed: added `postgres_role_docker_env_password: '<new>'` to `/srv/git/saltbox/inventories/host_vars/localhost.yml` (overrides public default `password4321` in `roles/postgres/defaults/main.yml:20`), then `sudo sb install authentik`. Worker is recreated under same role — `authentik_worker` is not a standalone `sb` tag (the wrapper rejects it; the actual tasks run regardless).
6. **VSCode sudo** — outstanding; need to confirm `shively` is actually live sudo before rotating.

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
- ✅ Grafana admin + secret key rotated (2026-05-08).
- ✅ ntfy admin password + alert token rotated (2026-05-08).
- ✅ Postgres `agno` rotated across all consumers (2026-05-08).
- ✅ Authentik DB password rotated via Saltbox-clean path (2026-05-08).

## Outstanding

- ⚠️ SMTP — current `ALERT_SMTP_PASSWORD` still produces `535 Authentication Failed`
  against Zoho. Likely root cause: Admin@Graceful-Tech.com has 2FA enabled, which
  forces SMTP to use a Zoho **App Password** (Zoho Mail → Settings → Security →
  App Passwords), not the regular login password. Generate one for "Alertmanager",
  set it as `ALERT_SMTP_PASSWORD` on Turing, then `sudo docker compose up -d
  --force-recreate alertmanager` from `turing_gateway/`.
- ⚠️ VSCode sudo password — needs human confirmation that `shively` is actually
  the live `VSCODE_SUDO_PASSWORD` (vs. just appearing in docs as a surname).
