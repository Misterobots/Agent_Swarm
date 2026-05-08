---
title: Training API
---

# Training API

The training pipeline is a **distributed, two-node system**:

- **Lovelace** (`{{ lovelace_ip }}:8001`) — Training Dispatcher FastAPI service. Owns the GPU and runs `grpo_trainer.py` subprocesses.
- **Turing** (`agent_runtime`) — Submits jobs to the dispatcher via `DISPATCHER_URL`.

All dispatcher endpoints except `/health` require the `X-Dispatcher-Key` header (value = `DISPATCHER_SECRET`).

---

## Health Check

```
GET http://{{ lovelace_ip }}:8001/health
```

No authentication required. Used as a liveness probe.

### Response

```json
{
    "status": "online",
    "node": "lovelace",
    "ip": "{{ lovelace_ip }}",
    "active_jobs": 0,
    "total_jobs": 12,
    "available_archetypes": ["coder", "coordinator", "researcher", "creative"]
}
```

---

## Submit Training Job

```
POST http://{{ lovelace_ip }}:8001/train
X-Dispatcher-Key: <DISPATCHER_SECRET>
```

### Body

```json
{
    "archetype": "coder",
    "dataset_path": "/workspace/training_data/curated.jsonl",
    "base_model": "Qwen/Qwen3-27B",
    "max_seq_len": 2048,
    "force": false,
    "dry_run": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `archetype` | string | **Yes** | One of `coder`, `coordinator`, `researcher`, `creative`. Must exist in `ARCHETYPE_TRAINING_CONFIGS`. |
| `dataset_path` | string | No | Override default dataset path. |
| `base_model` | string | No | Override base model from archetype config. |
| `max_seq_len` | int | No | Max sequence length (default: 2048). |
| `force` | bool | No | Bypass training time window check. |
| `dry_run` | bool | No | Run preflight only; do not launch training. |

### Response — Success (`202 Accepted`)

```json
{
    "job_id": "job-20260504-001",
    "status": "running",
    "archetype": "coder",
    "started_at": "2026-05-04T07:15:00Z"
}
```

### Error: Unknown Archetype (`422`)

```json
{"detail": "Unknown archetype 'foo'. Valid: coder, coordinator, researcher, creative"}
```

### Error: Job Already Running (`409`)

```json
{"detail": "A training job is already running (job-20260504-001). Cancel it first or wait."}
```

### Error: Secret Not Configured (`503`)

```json
{"detail": "Dispatcher secret not configured — service is in locked mode."}
```

---

## Poll Job Status

```
GET http://{{ lovelace_ip }}:8001/train/{job_id}
X-Dispatcher-Key: <DISPATCHER_SECRET>
```

### Response

```json
{
    "job_id": "job-20260504-001",
    "archetype": "coder",
    "status": "running",
    "started_at": "2026-05-04T07:15:00Z",
    "finished_at": null,
    "exit_code": null,
    "log_tail": "Epoch 2/3  loss=0.342  reward_mean=0.78 ..."
}
```

`status` values: `running` | `completed` | `failed` | `cancelled`

---

## List Jobs

```
GET http://{{ lovelace_ip }}:8001/jobs
X-Dispatcher-Key: <DISPATCHER_SECRET>
```

Returns up to 50 most-recent jobs, newest first.

### Response

```json
[
    {"job_id": "job-20260504-001", "archetype": "coder", "status": "running", ...},
    {"job_id": "job-20260503-002", "archetype": "researcher", "status": "completed", ...}
]
```

---

## Cancel Job

```
DELETE http://{{ lovelace_ip }}:8001/train/{job_id}
X-Dispatcher-Key: <DISPATCHER_SECRET>
```

Sends `SIGTERM` to the training subprocess. Returns `404` if the job does not exist or has already finished.

### Response (`200`)

```json
{"job_id": "job-20260504-001", "status": "cancelled"}
```

---

## Related

- [Module: Training Dispatcher](../../modules/training-dispatcher.md)
- [Admin: Secrets](../../admin-guide/operations/secrets.md)
- [Config: ARCHETYPE_TRAINING_CONFIGS](../../modules/config.md#archetype-training-configs)
