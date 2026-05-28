"""
agents/api/gpu_lock.py — Cross-host GPU mutex server.

Mounted on the Lovelace agent_runtime at /internal/gpu-lock/.
Provides a polling-based lock that agent_runtimes on ALL hosts call
when Redis is unavailable, giving us genuine cross-process, cross-host
GPU serialization without needing Redis.

Why polling and not long-polling / SSE?
  request_lock() is synchronous.  The client is a simple spin-loop (1s
  sleep between retries) — the same pattern as the Redis NX acquire.
  Long-polling or websockets would require async client code, which
  changes the public API contract the rest of the codebase depends on.

Auth:
  Optional shared-secret via GPU_LOCK_SECRET env var.  If set, all
  mutating endpoints require the header:  X-GPU-Lock-Secret: <value>
  If the env var is empty, the endpoints are open (dev / single-host).
  The status endpoint is always open.

State machine per lease:
  FREE → LOCKED → (ttl expires OR explicit release) → FREE

  The server NEVER blocks in an endpoint — it returns immediately with
  acquired=true or acquired=false.  Callers spin externally.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("GPULockServer")

# ---------------------------------------------------------------------------
# Shared secret auth (optional)
# ---------------------------------------------------------------------------
_SECRET = os.getenv("GPU_LOCK_SECRET", "")


def _check_auth(x_gpu_lock_secret: Optional[str]):
    if _SECRET and x_gpu_lock_secret != _SECRET:
        raise HTTPException(status_code=401, detail="Invalid GPU lock secret")


# ---------------------------------------------------------------------------
# In-memory lease state
# ---------------------------------------------------------------------------
# One asyncio.Lock protects all mutations.  A separate threading.Lock lets
# the same state be read/mutated from non-async contexts if needed.
_state_lock = asyncio.Lock()

class _LeaseState:
    __slots__ = ("lock_id", "context", "acquired_at", "ttl")

    def __init__(self):
        self.lock_id: str | None = None
        self.context: str = ""
        self.acquired_at: float = 0.0
        self.ttl: float = 0.0

    def is_free(self) -> bool:
        if self.lock_id is None:
            return True
        return (time.monotonic() - self.acquired_at) >= self.ttl

    def remaining(self) -> float:
        if self.lock_id is None:
            return 0.0
        r = self.ttl - (time.monotonic() - self.acquired_at)
        return max(0.0, r)

    def clear(self):
        self.lock_id = None
        self.context = ""
        self.acquired_at = 0.0
        self.ttl = 0.0


_state = _LeaseState()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class AcquireRequest(BaseModel):
    lock_id: str       # caller generates this; returned on success to prove ownership
    context: str       # "text" | "image" | "compose" | "training"
    ttl: float = 300.0 # lease duration in seconds


class AcquireResponse(BaseModel):
    acquired: bool
    lock_id: Optional[str] = None
    holder_context: Optional[str] = None
    retry_after: float = 1.0   # seconds; only meaningful when acquired=False


class ReleaseRequest(BaseModel):
    lock_id: str


class ReleaseResponse(BaseModel):
    released: bool
    reason: str = ""


class StatusResponse(BaseModel):
    locked: bool
    holder_context: Optional[str]
    acquired_at: Optional[float]
    ttl: Optional[float]
    expires_at: Optional[float]
    remaining_s: Optional[float]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/internal/gpu-lock", tags=["gpu-lock"])


@router.post("/acquire", response_model=AcquireResponse)
async def acquire(
    body: AcquireRequest,
    x_gpu_lock_secret: Optional[str] = Header(default=None, alias="X-GPU-Lock-Secret"),
):
    """
    Try to acquire the GPU lease.
    Returns immediately — callers must poll until acquired=true or timeout.

    On success: acquired=true, lock_id=<caller's supplied id>.
    When held: acquired=false, holder_context=<current zone>, retry_after=1.0.
    If the current lease has expired, it is silently evicted first.
    """
    _check_auth(x_gpu_lock_secret)

    if body.ttl <= 0:
        raise HTTPException(status_code=400, detail="ttl must be > 0")
    if not body.lock_id:
        raise HTTPException(status_code=400, detail="lock_id required")

    async with _state_lock:
        if _state.is_free():
            if _state.lock_id is not None:
                logger.warning(
                    f"[GPULockServer] Evicting expired lease "
                    f"(context={_state.context!r}, age={time.monotonic()-_state.acquired_at:.1f}s)."
                )
            _state.lock_id = body.lock_id
            _state.context = body.context
            _state.acquired_at = time.monotonic()
            _state.ttl = body.ttl
            logger.info(
                f"[GPULockServer] Lease granted: context={body.context!r} "
                f"lock_id={body.lock_id[:8]}… ttl={body.ttl:.0f}s"
            )
            return AcquireResponse(acquired=True, lock_id=body.lock_id, holder_context=body.context)

        return AcquireResponse(
            acquired=False,
            holder_context=_state.context,
            retry_after=1.0,
        )


@router.post("/release", response_model=ReleaseResponse)
async def release(
    body: ReleaseRequest,
    x_gpu_lock_secret: Optional[str] = Header(default=None, alias="X-GPU-Lock-Secret"),
):
    """
    Release the lease.  Only succeeds if the caller holds it (lock_id must match).
    Idempotent: releasing an already-free lock returns released=true.
    """
    _check_auth(x_gpu_lock_secret)

    async with _state_lock:
        if _state.lock_id is None or _state.is_free():
            logger.debug("[GPULockServer] release() called on free lock — no-op.")
            _state.clear()
            return ReleaseResponse(released=True, reason="was_free")

        if _state.lock_id != body.lock_id:
            logger.warning(
                f"[GPULockServer] release() rejected: caller lock_id={body.lock_id[:8]}… "
                f"but holder is {_state.lock_id[:8]}…"
            )
            return ReleaseResponse(released=False, reason="not_holder")

        ctx = _state.context
        _state.clear()
        logger.info(f"[GPULockServer] Lease released: context={ctx!r}")
        return ReleaseResponse(released=True, reason="ok")


@router.get("/status", response_model=StatusResponse)
async def status():
    """Health/debug endpoint — always open, no auth."""
    async with _state_lock:
        if _state.is_free():
            return StatusResponse(
                locked=False,
                holder_context=None,
                acquired_at=None,
                ttl=None,
                expires_at=None,
                remaining_s=None,
            )
        now = time.monotonic()
        return StatusResponse(
            locked=True,
            holder_context=_state.context,
            acquired_at=_state.acquired_at,
            ttl=_state.ttl,
            expires_at=_state.acquired_at + _state.ttl,
            remaining_s=_state.remaining(),
        )
