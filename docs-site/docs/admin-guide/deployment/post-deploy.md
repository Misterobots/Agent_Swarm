---
title: Post-Deployment Verification
---

# Post-Deployment Verification

Smoke tests and verification steps after deploying all three nodes.

## Pre-Checks

Ensure all three nodes are deployed:

- [ ] Control Plane services are running
- [ ] Execution Plane services are running
- [ ] Gateway services are running

## Verification Steps

### 1. End-to-End Connectivity

```bash
# From Gateway, verify execution node
curl -s http://{{ lovelace_ip }}:{{ agent_runtime_port }}/ | jq .

# From Execution, verify control plane
curl -s http://{{ hopper_ip }}:3000/api/public/health | jq .
curl -s http://{{ hopper_ip }}:8200/health
```

### 2. SPIRE Identity Chain

```bash
# On Execution node
docker compose exec spire-agent \
    /opt/spire/bin/spire-agent healthcheck

# Should show: Agent is healthy
```

### 3. Model Availability

```bash
curl -s http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags | \
    python -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['models']]"
```

Expected models:

- `{{ solver_model }}`
- `{{ router_model }}`
- `{{ verifier_model }}`
- `moondream:latest`

### 4. First Chat Request

```bash
curl -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Hello, are you working?"}],
        "stream": false
    }'
```

Expected: A response with `"intent": "CONVERSATION"` and a friendly answer.

### 5. Image Generation

```bash
curl -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Generate an image of a sunset"}],
        "stream": false
    }'
```

Check that ComfyUI executes and an image path is returned.

### 6. Monitoring Stack

| Check | URL | Expected |
|-------|-----|----------|
| hollerith | `http://{{ turing_ip }}:3001` | Login page |
| jacquard | `http://{{ turing_ip }}:9091/targets` | All targets UP |
| Langfuse | `http://{{ hopper_ip }}:3000` | Traces from step 4 |

### 7. Traefik Routes

```bash
curl -s http://{{ turing_ip }}:8080/api/http/routers | \
    python -c "import sys,json; [print(r['rule']) for r in json.load(sys.stdin)]"
```

Should list PathPrefix rules for `/swarm`, `/comfyui`, `/docs`, `/hollerith`.

## Common First-Run Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 502 on `/swarm/*` | Agent Runtime not started | Check execution node containers |
| Empty model list | Models not pulled | Run `ollama pull` for each model |
| Langfuse "connection refused" | ClickHouse not ready | Wait 30s, restart Langfuse |
| SPIRE attestation failure | Expired join token | Generate new token from Control Plane |
| jacquard target down | Wrong IP in jacquard.yml | Update scrape config IPs |

## What's Next

Once verification passes:

1. Import hollerith dashboards (see [Monitoring](../operations/monitoring.md))
2. Review alert rules (see [Operations: Alerts](../operations/monitoring.md#alerts))
3. Set up backup schedule (see [Backup & Restore](../operations/backup-restore.md))
4. Onboard users (see [Getting Started: User Quickstart](../../getting-started/quickstart-user.md))


