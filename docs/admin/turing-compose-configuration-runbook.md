# Turing Compose Configuration Runbook

This runbook records the verified configuration path for the Turing deployment and the diagnostic sequence for future credential or Compose warnings.

## Canonical live paths

- Live Compose file: `/home/misterobots/docker-compose.yml`
- Service env file: `/home/network.env`
- Project interpolation file: `/home/misterobots/.env`
- Shared Docker network: `ai_lab_net` (pre-existing and external)
- Agent container: `agent_runtime`
- Compose service: `agent-runtime`

The live Turing checkout may be on a divergent branch with uncommitted work. Check branch, status, and latest commit before touching repository files. The root-level live Compose file is not interchangeable with `turing_gateway/docker-compose-Justin-PC.yml`.

## Live service ownership

The current host intentionally has two Compose projects:

- Project `misterobots`, `/home/misterobots/docker-compose.yml`: `agent-runtime`, infrastructure, Grafana, NTFY, Cloudflare, and sandbox services.
- Project `turing_gateway`, `/home/misterobots/Agent_Swarm/turing_gateway/docker-compose-Justin-PC.yml`: `memex-ui` and `docs-site`.

Do not run a whole-stack `up` against either file. It will try to claim fixed container names owned by the other project. Target only the service(s) belonging to the selected project.

## Source-of-truth deployment check

Before declaring backend changes deployed, verify the running bind mount and the tested checkout. The root project now mounts `/home/misterobots/Agent_Swarm/agents` into `/app/agents`, making the repository checkout the canonical runtime source. Verify the effective mount and revision before restarting `agent-runtime`; a healthy container can still be running stale or incomplete source.

Do not copy over or clean either location while the Turing checkout is dirty. Preserve the existing branch and uncommitted work, isolate the intended changes, and deploy only an identified revision.

For the current parity work, the non-destructive staging bundle is:

`/home/misterobots/Agent_Swarm/.codex/deploy/20260824-backend-parity/`

The staged files have been compiled and fingerprinted on Turing. Staging is not activation: do not copy the bundle into the canonical checkout until dependency/import validation and an explicit activation plan are complete.

### Current source-drift evidence (2026-08-24)

The staged backend parity files compile and match the local source hashes. A
disposable overlay validation found the original source split: the old
`/home/agents` bind source was incomplete and lacked required siblings such as
`swarm_run_repo_store.py`. The root Compose mount has now been changed to the
repository checkout, the missing modules and targeted fixes were synchronized,
and the container was recreated successfully. Future changes must preserve this
single canonical source path.

## Required Compose invocation

Use `/home/network.env` explicitly for Compose interpolation:

```bash
docker compose --env-file /home/network.env -f /home/misterobots/docker-compose.yml config --quiet
```

Do not rely on the project `.env` alone. `env_file:` values are injected into containers but are not automatically available for \${VAR} interpolation while Compose parses the YAML.

## AGNO database diagnostic sequence

Do not rotate the database password repeatedly. Establish the layer first:

1. Test the known password directly against PostgreSQL, bypassing Compose and `AGNO_DB_URL`.
2. Compare the effective container credential to the known password without printing either value.
3. Check the actual env-file path and file permissions.
4. Update `/home/network.env` with appropriate privilege if it is root-owned.
5. Recreate only `agent-runtime`, then verify:

```bash
docker exec agent_runtime python3 -c 'import os,psycopg2; c=psycopg2.connect(os.environ["AGNO_DB_URL"],connect_timeout=5); print("runtime_db_auth=ok"); c.close()'
```

The successful `runtime_db_auth=ok` result and `docker inspect agent_runtime --format={{.State.Status}}` returning `running` are the completion criteria for this issue.

The durable parity probe also passed against the live Postgres database on
2026-08-24: approval lookup survived a module reload, two concurrent decisions
collapsed to one audited outcome, and workspace lookup preserved owner
isolation after reload. The probe used uniquely prefixed rows and removed them
afterward. Keep this probe separate from the normal unit suite because the
runtime image does not include pytest.

## Literal dollar signs in env files

Compose interprets `$NAME` in interpolation env files. Bcrypt hashes and other literal secret values containing `$` must use `$$` in the Compose interpolation source so the container receives a literal `$`.

The live `/home/network.env` file must contain real line breaks. A file containing literal backslash-n text is not a valid env file and will be parsed as one long line.

## MemPalace connectivity

The root live Compose file must include this mapping under `agent-runtime`:

~~~yaml
extra_hosts:
  - "mempalace:\${HOPPER_IP:-192.168.2.102}"
~~~

Verify from the running container:

~~~bash
docker exec agent_runtime getent hosts mempalace
~~~

Then verify TCP reachability to `mempalace:8200`. A successful hostname lookup alone is not sufficient.

## Redis consumer timeout diagnostic

A successful authenticated Redis `PING` does not by itself prove that blocking
consumers are configured correctly. The dispatcher uses `BLPOP(..., timeout=5)`;
the Redis socket timeout must be strictly greater than five seconds. With newer
redis-py versions, inspect the effective connection settings rather than
assuming the library default. The canonical dispatcher configuration uses a
10-second socket timeout and a 5-second connect timeout. After a restart,
observe several idle polling intervals and confirm there are no `Timeout reading
from socket` or `redis.exceptions.TimeoutError` lines.

## Shared-network warning

If Compose reports that `ai_lab_net` exists but was not created for the project, the network declaration must be:

```yaml
networks:
  ai_lab_net:
    external: true
    name: ai_lab_net
```

Do not delete or recreate the shared network.

## Fixed container-name conflicts

`docker compose up` can fail with `/memex_ui` or `/agent_runtime` already in use when the running containers belong to another Compose project. Inspect labels and project metadata first. Do not remove containers or use `--force-recreate` across mismatched Compose projects without an explicit migration plan.

## Shell convention

The workstation default is Windows PowerShell. If a remote Linux command must run in Bash, explicitly tell the operator that Bash is required and provide the PowerShell-safe SSH invocation. Diagnostic commands must not include `exit`, `logout`, or automatic SSH disconnects.
