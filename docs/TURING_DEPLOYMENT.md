# Turing deployment and recovery

Turing runs its Compose project from `/home/misterobots/docker-compose.yml` with
the stable Compose project name `misterobots`. Runtime credentials remain in the
root-owned, Git-ignored `/home/network.env`. Do not use the dirty development
checkout at `/home/misterobots/Agent_Swarm` as a deployment source.

## One-time setup

Create an isolated deployment checkout on Turing. It stays clean and may safely
be reset or switched to any published commit without affecting development work.

```bash
git clone git@github.com:Misterobots/Agent_Swarm.git /home/misterobots/Agent_Swarm-deploy
cd /home/misterobots/Agent_Swarm-deploy
git switch main
```

The checkout must not contain `network.env`; the active `/home/network.env` is
kept outside Git and is read only by Compose.

## Normal deployment

```bash
cd /home/misterobots/Agent_Swarm-deploy
git fetch origin
git pull --ff-only
./turing_gateway/deploy.sh --check
./turing_gateway/deploy.sh
```

`deploy.sh` refuses a dirty checkout, renders the candidate against the real
`/home/network.env`, backs up the current root compose as
`/home/misterobots/docker-compose.yml.pre-deploy-<UTC timestamp>`, then promotes
the validated candidate and runs `docker compose build` followed by
`docker compose up -d --pull missing`. Existing named volumes and credentials
are not removed.

## Deploy a branch or pinned commit

Use the clean deployment checkout, never the development checkout:

```bash
cd /home/misterobots/Agent_Swarm-deploy
git fetch origin codex/some-branch
git switch --detach origin/codex/some-branch
./turing_gateway/deploy.sh --check
./turing_gateway/deploy.sh
```

For a commit, replace `origin/codex/some-branch` with the exact commit SHA.
Return to the release branch with `git switch main && git pull --ff-only`.

## Roll back Compose configuration

First prefer redeploying the prior published commit from the clean checkout:

```bash
cd /home/misterobots/Agent_Swarm-deploy
git switch --detach <known-good-commit>
./turing_gateway/deploy.sh
```

If Git is unavailable during an incident, restore the latest root-compose backup
after reviewing its filename, then reconcile without pulling images:

```bash
cd /home/misterobots
ls -1t docker-compose.yml.pre-deploy-*
cp -p docker-compose.yml.pre-deploy-<timestamp> docker-compose.yml
docker compose --env-file /home/network.env -f docker-compose.yml up -d --pull never
```

Do not run `docker compose down -v` for recovery: it can remove named volumes.

## Post-deploy checks

```bash
cd /home/misterobots
docker compose --env-file /home/network.env -f docker-compose.yml ps
curl -fsS http://127.0.0.1:8008/api/v1/mcp/health
```

The first command confirms the `misterobots` service set. The second confirms
that Memex MCP is serving after `agent_runtime` starts.