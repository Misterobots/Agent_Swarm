---
title: Tasks API
---

# Tasks API

Manage async tasks (image generation, 3D rendering, long-running operations).

## Get Task Status

```
GET /v1/tasks/{task_id}
```

### Response

```json
{
    "task_id": "task-abc123",
    "status": "completed",
    "intent": "IMAGE",
    "created_at": "2026-04-10T14:30:00Z",
    "completed_at": "2026-04-10T14:30:45Z",
    "result": {
        "image_path": "/delivered_artifacts/images/img_20260410.png",
        "metadata": {
            "prompt": "sunset over mountains",
            "steps": 20,
            "seed": 42
        }
    }
}
```

### Task Statuses

| Status | Description |
|--------|-------------|
| `queued` | Waiting in dispatcher queue |
| `processing` | Currently being executed |
| `completed` | Finished successfully |
| `failed` | Execution error |

## List Active Tasks

```
GET /v1/tasks
```

### Response

```json
{
    "tasks": [
        {
            "task_id": "task-abc123",
            "status": "processing",
            "intent": "IMAGE",
            "created_at": "2026-04-10T14:30:00Z"
        }
    ],
    "total": 1
}
```

## Cancel Task

```
DELETE /v1/tasks/{task_id}
```

### Response

```json
{
    "task_id": "task-abc123",
    "status": "cancelled"
}
```


