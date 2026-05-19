"""
Training Job Dispatcher — Lovelace FastAPI service.

Accepts training job requests from Turing's agent_runtime, runs preflight
checks, then launches grpo_trainer.py as a subprocess on Lovelace's
dual RTX 5060 Ti (32 GB VRAM). Jobs are tracked in memory and can be
polled for status.

Endpoints:
    POST /train         — Submit a training job
    GET  /train/{job_id} — Poll job status
    GET  /jobs           — List recent jobs
    GET  /health         — Liveness check

Authentication:
    Shared secret via X-Dispatcher-Key header.
    Set DISPATCHER_SECRET env var on both sides.

Usage (Lovelace, inside execution_plane docker compose):
    uvicorn agents.training.dispatcher:app --host 0.0.0.0 --port 8001

Turing → Lovelace call:
    POST http://192.168.2.101:8001/train
    X-Dispatcher-Key: <secret>
    {"archetype": "coder", "dataset_path": "/workspace/training_data/curated.jsonl"}
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    TRAINING_BASE_SOLVER,
    TRAINING_OUTPUT_DIR,
    TRAINING_DATASET_DIR,
    LOVELACE_IP,
    ARCHETYPE_TRAINING_CONFIGS,
)

logger = logging.getLogger("TrainingDispatcher")

# ── Auth ──────────────────────────────────────────────────────────────────────

DISPATCHER_SECRET = os.getenv("DISPATCHER_SECRET", "")
_api_key_header = APIKeyHeader(name="X-Dispatcher-Key", auto_error=False)


def _verify_key(key: Optional[str] = Security(_api_key_header)) -> str:
    if not DISPATCHER_SECRET:
        # Secret not configured — reject all requests for safety
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DISPATCHER_SECRET not configured on this node",
        )
    if not key or key != DISPATCHER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Dispatcher-Key",
        )
    return key


# ── Job State ─────────────────────────────────────────────────────────────────

class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingJob:
    def __init__(
        self,
        job_id: str,
        archetype: str,
        base_model: str,
        dataset_path: str,
        extra_args: Dict,
    ):
        self.job_id = job_id
        self.archetype = archetype
        self.base_model = base_model
        self.dataset_path = dataset_path
        self.extra_args = extra_args
        self.status = JobStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.exit_code: Optional[int] = None
        self.log_path: Optional[str] = None
        self.error: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "archetype": self.archetype,
            "base_model": self.base_model,
            "dataset_path": self.dataset_path,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "log_path": self.log_path,
            "error": self.error,
        }


# In-memory job registry — survives container restarts if backed by volume later
_jobs: Dict[str, TrainingJob] = {}


# ── Request / Response Models ─────────────────────────────────────────────────

class TrainRequest(BaseModel):
    archetype: str = Field(
        ...,
        description="Archetype key from ARCHETYPE_TRAINING_CONFIGS (e.g. 'coder', 'coordinator', 'researcher')",
    )
    dataset_path: Optional[str] = Field(
        None,
        description="Absolute path to GRPO JSONL dataset. Defaults to TRAINING_DATASET_DIR.",
    )
    base_model: Optional[str] = Field(
        None,
        description="HuggingFace model ID. Defaults to TRAINING_BASE_SOLVER.",
    )
    max_seq_len: Optional[int] = Field(
        None,
        description="Override TRAINING_MAX_SEQ_LEN for this job.",
    )
    force: bool = Field(
        False,
        description="Bypass training time-window check (FORCE_TRAIN=1).",
    )
    dry_run: bool = Field(
        False,
        description="Run preflight only — do not start actual training.",
    )


class TrainResponse(BaseModel):
    job_id: str
    status: str
    message: str
    log_path: Optional[str] = None


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agent Swarm Training Dispatcher",
    description="Accepts training jobs from Turing and runs them on Lovelace GPUs.",
    version="1.0.0",
)


@app.get("/health")
def health():
    """Liveness probe — no auth required."""
    return {
        "status": "online",
        "node": "lovelace",
        "ip": LOVELACE_IP,
        "active_jobs": sum(1 for j in _jobs.values() if j.status == JobStatus.RUNNING),
        "total_jobs": len(_jobs),
        "available_archetypes": list(ARCHETYPE_TRAINING_CONFIGS.keys()),
    }


@app.post("/train", response_model=TrainResponse)
def submit_train(
    req: TrainRequest,
    _key: str = Security(_verify_key),
):
    """
    Submit a training job.
    
    Runs preflight checks first. On success starts grpo_trainer.py subprocess
    and returns job_id immediately for async status polling.
    """
    from training.preflight import run_preflight

    # ── Validate archetype ────────────────────────────────────────────────────
    if req.archetype not in ARCHETYPE_TRAINING_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown archetype '{req.archetype}'. Valid options: {list(ARCHETYPE_TRAINING_CONFIGS.keys())}",
        )

    job_id = str(uuid.uuid4())[:8]
    base_model = req.base_model or TRAINING_BASE_SOLVER
    dataset_path = req.dataset_path or str(
        Path(TRAINING_DATASET_DIR) / "curated_latest.jsonl"
    )

    # ── Preflight ─────────────────────────────────────────────────────────────
    try:
        preflight = run_preflight(
            force=req.force,
            evict_inference=True,
        )
        if not preflight.ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Preflight failed: {preflight.reason}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Preflight error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Preflight error: {e}",
        )

    if req.dry_run:
        return TrainResponse(
            job_id=job_id,
            status="dry_run",
            message="Preflight passed. Dry run — no training started.",
        )

    # ── Reject if a job is already running ───────────────────────────────────
    running = [j for j in _jobs.values() if j.status == JobStatus.RUNNING]
    if running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Training job {running[0].job_id} already running. Wait for it to finish.",
        )

    # ── Build subprocess command ──────────────────────────────────────────────
    log_path = str(
        Path(TRAINING_OUTPUT_DIR) / f"train_{job_id}.log"
    )
    Path(TRAINING_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "training.grpo_trainer",
        "--dataset", dataset_path,
        "--base-model", base_model,
        "--archetype", req.archetype,
    ]
    if req.max_seq_len:
        cmd += ["--max-seq-len", str(req.max_seq_len)]
    if req.force:
        cmd += ["--force"]

    env = {**os.environ, "FORCE_TRAIN": "1" if req.force else "0"}

    job = TrainingJob(
        job_id=job_id,
        archetype=req.archetype,
        base_model=base_model,
        dataset_path=dataset_path,
        extra_args={"max_seq_len": req.max_seq_len},
    )
    job.log_path = log_path
    _jobs[job_id] = job

    # ── Launch subprocess (non-blocking) ─────────────────────────────────────
    try:
        log_file = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        job._proc = proc
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{job_id}] Training job started: PID={proc.pid}, archetype={req.archetype}")
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.finished_at = datetime.now(timezone.utc).isoformat()
        logger.error(f"[{job_id}] Failed to start subprocess: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start training: {e}",
        )

    return TrainResponse(
        job_id=job_id,
        status=JobStatus.RUNNING,
        message=f"Training started (PID {proc.pid}). Poll /train/{job_id} for status.",
        log_path=log_path,
    )


@app.get("/train/{job_id}")
def get_job(
    job_id: str,
    _key: str = Security(_verify_key),
):
    """Poll training job status. Updates state from subprocess if running."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Update status from subprocess
    if job.status == JobStatus.RUNNING and job._proc:
        rc = job._proc.poll()
        if rc is not None:
            job.exit_code = rc
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.status = JobStatus.COMPLETED if rc == 0 else JobStatus.FAILED
            if rc != 0:
                job.error = f"Subprocess exited with code {rc}"
            logger.info(f"[{job_id}] Job finished: exit_code={rc}")

    return job.to_dict()


@app.get("/jobs")
def list_jobs(
    _key: str = Security(_verify_key),
):
    """List all jobs (newest first)."""
    sorted_jobs = sorted(
        _jobs.values(),
        key=lambda j: j.created_at,
        reverse=True,
    )
    return [j.to_dict() for j in sorted_jobs[:50]]


@app.delete("/train/{job_id}")
def cancel_job(
    job_id: str,
    _key: str = Security(_verify_key),
):
    """Attempt to terminate a running training job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.RUNNING or not job._proc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not running (status={job.status})",
        )

    try:
        job._proc.terminate()
        time.sleep(2)
        if job._proc.poll() is None:
            job._proc.kill()
        job.status = JobStatus.FAILED
        job.error = "Cancelled by user"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{job_id}] Job cancelled")
        return {"job_id": job_id, "status": "cancelled"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {e}",
        )


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
