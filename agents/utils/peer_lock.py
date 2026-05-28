"""
agents/utils/peer_lock.py — Client for the cross-host GPU peer lock.

This module gives request_lock() its second fallback layer:

  Tier 1: Redis (cross-process, cross-host — primary)
  Tier 2: Peer HTTP lock via Lovelace's lock server (cross-host — Redis-down path)  ← HERE
  Tier 3: In-process semaphore (same host — last resort)

The client is intentionally synchronous (threading, requests) so it can be
used inside the existing request_lock() contextmanager without converting it
to async.  The spin-acquire pattern mirrors the Redis spin loop.

Configuration (all env vars, inherit from network.env / docker env):
  GPU_LOCK_HOST      — base URL of the lock server.
                       Default: http://localhost:8000 (Turing's agent_runtime,
                       which hosts the /internal/gpu-lock/ router on its own
                       uvicorn process).  When a second agent_runtime is added
                       on another host, set GPU_LOCK_HOST on that host to point
                       at the canonical lock-server host (e.g. http://<turing-ip>:8008).
  GPU_LOCK_SECRET    — optional shared secret (must match server-side env var)
                       Default: "" (no auth, safe for single-host dev)
  GPU_LOCK_CONNECT_TIMEOUT — seconds to wait for TCP connection (default 3)
  GPU_LOCK_READ_TIMEOUT    — seconds to wait for response body (default 5)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import contextmanager

import requests

logger = logging.getLogger("GPUQueue")

GPU_LOCK_HOST = os.getenv("GPU_LOCK_HOST", "http://localhost:8000")
_SECRET = os.getenv("GPU_LOCK_SECRET", "")
_CONN_TIMEOUT = float(os.getenv("GPU_LOCK_CONNECT_TIMEOUT", "3"))
_READ_TIMEOUT  = float(os.getenv("GPU_LOCK_READ_TIMEOUT", "5"))

_ACQUIRE_URL = f"{GPU_LOCK_HOST}/internal/gpu-lock/acquire"
_RELEASE_URL = f"{GPU_LOCK_HOST}/internal/gpu-lock/release"
_STATUS_URL  = f"{GPU_LOCK_HOST}/internal/gpu-lock/status"

_HEADERS = {"X-GPU-Lock-Secret": _SECRET} if _SECRET else {}


class PeerLockUnavailableError(Exception):
    """Raised when the peer lock server cannot be reached at all."""


class PeerLockTimeoutError(TimeoutError):
    """Raised when the peer lock cannot be acquired within the timeout."""


def peer_lock_is_reachable() -> bool:
    """Fast health-check.  Returns True if the lock server is up."""
    try:
        r = requests.get(_STATUS_URL, timeout=(_CONN_TIMEOUT, _READ_TIMEOUT))
        return r.status_code == 200
    except Exception:
        return False


def _acquire_once(lock_id: str, context: str, ttl: float) -> dict:
    """POST /acquire once.  Returns the parsed JSON response.  Raises on network error."""
    r = requests.post(
        _ACQUIRE_URL,
        json={"lock_id": lock_id, "context": context, "ttl": ttl},
        headers=_HEADERS,
        timeout=(_CONN_TIMEOUT, _READ_TIMEOUT),
    )
    r.raise_for_status()
    return r.json()


def _release_once(lock_id: str) -> None:
    """POST /release once.  Errors are logged but not re-raised (best-effort)."""
    try:
        r = requests.post(
            _RELEASE_URL,
            json={"lock_id": lock_id},
            headers=_HEADERS,
            timeout=(_CONN_TIMEOUT, _READ_TIMEOUT),
        )
        data = r.json()
        if not data.get("released"):
            logger.warning(
                f"[GPU Peer Lock] Release not acknowledged: {data.get('reason')} "
                f"(lock_id={lock_id[:8]}…)"
            )
    except Exception as e:
        logger.warning(f"[GPU Peer Lock] Release POST failed (lock will expire via TTL): {e}")


@contextmanager
def peer_lock(context: str, timeout: float = 300.0):
    """
    Context manager: acquires the cross-host GPU peer lock, yields, then releases.

    Spin-acquires via polling (1s between retries) up to `timeout` seconds.
    Raises PeerLockUnavailableError if the server is unreachable on the first try.
    Raises PeerLockTimeoutError if the lock cannot be acquired within timeout.

    Usage inside request_lock():
        with peer_lock(context, timeout):
            with _INPROC_GPU_LOCK:
                ... zone switch, yield work slot ...
    """
    lock_id = uuid.uuid4().hex
    deadline = time.monotonic() + timeout
    acquired = False
    first_attempt = True
    t_acquire_start = time.monotonic()

    try:
        while time.monotonic() < deadline:
            try:
                resp = _acquire_once(lock_id, context, ttl=timeout)
            except requests.exceptions.ConnectionError as exc:
                if first_attempt:
                    raise PeerLockUnavailableError(
                        f"GPU peer lock server unreachable at {GPU_LOCK_HOST}: {exc}"
                    ) from exc
                # Server went down mid-wait — treat as unavailable
                raise PeerLockUnavailableError(
                    f"GPU peer lock server lost mid-acquire at {GPU_LOCK_HOST}: {exc}"
                ) from exc
            except Exception as exc:
                if first_attempt:
                    raise PeerLockUnavailableError(
                        f"GPU peer lock server error at {GPU_LOCK_HOST}: {exc}"
                    ) from exc
                raise

            first_attempt = False

            if resp.get("acquired"):
                acquired = True
                wait = time.monotonic() - t_acquire_start
                logger.info(
                    f"[GPU Peer Lock] Acquired: context={context!r} "
                    f"lock_id={lock_id[:8]}… wait={wait:.2f}s"
                )
                break

            holder_ctx = resp.get("holder_context", "unknown")
            retry_after = float(resp.get("retry_after", 1.0))
            remaining = max(0.0, deadline - time.monotonic())
            logger.debug(
                f"[GPU Peer Lock] Waiting for lock (holder_context={holder_ctx!r}, "
                f"retry_after={retry_after}s, timeout_remaining={remaining:.0f}s)"
            )
            time.sleep(min(retry_after, remaining))

        if not acquired:
            raise PeerLockTimeoutError(
                f"[GPU Peer Lock] Could not acquire within {timeout:.0f}s "
                f"(context={context!r})"
            )

        yield

    finally:
        if acquired:
            _release_once(lock_id)
            logger.info(f"[GPU Peer Lock] Released: context={context!r} lock_id={lock_id[:8]}…")
