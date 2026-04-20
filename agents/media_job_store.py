import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger("MediaJobStore")

_REDIS_CLIENT = None
_REDIS_UNAVAILABLE = False

ART_JOB_PREFIX = "art_job:"
ART_JOB_TTL_SECONDS = int(os.getenv("ART_JOB_TTL_SECONDS", str(7 * 24 * 60 * 60)))

IMAGE_TRAINING_QUEUE_KEY = "image_training_queue"
IMAGE_TRAINING_RUN_PREFIX = "image_training_run:"
IMAGE_TRAINING_RUN_TTL_SECONDS = int(os.getenv("IMAGE_TRAINING_RUN_TTL_SECONDS", str(30 * 24 * 60 * 60)))

_MEMORY_ART_JOBS: dict[str, dict[str, Any]] = {}
_MEMORY_IMAGE_TRAINING_RUNS: dict[str, dict[str, Any]] = {}
_MEMORY_IMAGE_TRAINING_QUEUE: list[str] = []


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _deserialize(value: str | bytes | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    try:
        return json.loads(value)
    except Exception as exc:
        logger.warning("Failed to decode job payload: %s", exc)
        return None


def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE

    if _REDIS_UNAVAILABLE:
        return None
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    try:
        import redis  # type: ignore

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD") or None,
            db=0,
            decode_responses=True,
        )
        client.ping()
        _REDIS_CLIENT = client
        return client
    except Exception as exc:
        logger.warning("Redis unavailable for media job store, falling back to memory: %s", exc)
        _REDIS_UNAVAILABLE = True
        return None


def create_art_job(mode: str, prompt: str) -> str:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "running",
        "result": None,
        "mode": mode,
        "prompt": prompt,
        "created_at": _utc_now_iso(),
        "finished_at": None,
    }

    client = _get_redis_client()
    if client is not None:
        client.setex(f"{ART_JOB_PREFIX}{job_id}", ART_JOB_TTL_SECONDS, _serialize(job))
    else:
        _MEMORY_ART_JOBS[job_id] = job
    return job_id


def get_art_job(job_id: str) -> dict[str, Any] | None:
    client = _get_redis_client()
    if client is not None:
        return _deserialize(client.get(f"{ART_JOB_PREFIX}{job_id}"))
    return _MEMORY_ART_JOBS.get(job_id)


def update_art_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    job = get_art_job(job_id)
    if not job:
        return None

    job.update(fields)
    client = _get_redis_client()
    if client is not None:
        client.setex(f"{ART_JOB_PREFIX}{job_id}", ART_JOB_TTL_SECONDS, _serialize(job))
    else:
        _MEMORY_ART_JOBS[job_id] = job
    return job


def finish_art_job(job_id: str, status: str, result: str) -> dict[str, Any] | None:
    return update_art_job(job_id, status=status, result=result, finished_at=_utc_now_iso())


def create_image_training_run(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    run = {
        "run_id": run_id,
        "status": "queued",
        "created_at": _utc_now_iso(),
        "started_at": None,
        "finished_at": None,
        "payload": payload,
        "result": None,
        "artifacts": {},
    }

    client = _get_redis_client()
    if client is not None:
        client.setex(f"{IMAGE_TRAINING_RUN_PREFIX}{run_id}", IMAGE_TRAINING_RUN_TTL_SECONDS, _serialize(run))
        client.rpush(IMAGE_TRAINING_QUEUE_KEY, run_id)
    else:
        _MEMORY_IMAGE_TRAINING_RUNS[run_id] = run
        _MEMORY_IMAGE_TRAINING_QUEUE.append(run_id)
    return run


def get_image_training_run(run_id: str) -> dict[str, Any] | None:
    client = _get_redis_client()
    if client is not None:
        return _deserialize(client.get(f"{IMAGE_TRAINING_RUN_PREFIX}{run_id}"))
    return _MEMORY_IMAGE_TRAINING_RUNS.get(run_id)


def update_image_training_run(run_id: str, **fields: Any) -> dict[str, Any] | None:
    run = get_image_training_run(run_id)
    if not run:
        return None

    run.update(fields)
    client = _get_redis_client()
    if client is not None:
        client.setex(f"{IMAGE_TRAINING_RUN_PREFIX}{run_id}", IMAGE_TRAINING_RUN_TTL_SECONDS, _serialize(run))
    else:
        _MEMORY_IMAGE_TRAINING_RUNS[run_id] = run
    return run


def pop_image_training_run(block_seconds: int = 5) -> dict[str, Any] | None:
    client = _get_redis_client()
    if client is not None:
        item = client.blpop(IMAGE_TRAINING_QUEUE_KEY, timeout=block_seconds)
        if not item:
            return None
        _, run_id = item
        return get_image_training_run(run_id)

    if _MEMORY_IMAGE_TRAINING_QUEUE:
        run_id = _MEMORY_IMAGE_TRAINING_QUEUE.pop(0)
        return get_image_training_run(run_id)
    return None
