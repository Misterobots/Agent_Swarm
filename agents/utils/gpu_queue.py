import os
import time
import itertools
import threading
import requests
import logging
from datetime import datetime
from contextlib import contextmanager

from logger_setup import setup_logger

logger = setup_logger("GPUQueue")

# Prometheus metrics — degraded to no-ops if metrics module isn't importable
# (e.g. running this file in isolation outside the agents/ sys.path).
try:
    from metrics import (
        GPU_LOCK_DEGRADED_TOTAL,
        GPU_MUTEX_HEALTHY,
        GPU_SERVICE_CIRCUIT_OPEN,
        GPU_PEER_LOCK_DEGRADED_TOTAL,
    )
except Exception:  # pragma: no cover
    class _NoopMetric:
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): pass
        def set(self, *a, **kw): pass
    GPU_LOCK_DEGRADED_TOTAL = _NoopMetric()
    GPU_MUTEX_HEALTHY = _NoopMetric()
    GPU_SERVICE_CIRCUIT_OPEN = _NoopMetric()
    GPU_PEER_LOCK_DEGRADED_TOTAL = _NoopMetric()

# In-process backstop for the cross-process Redis GPU lock. Even when Redis
# is down and request_lock falls open at the cluster layer, a single
# agent_runtime process must not run two GPU-heavy workloads concurrently:
# that's how we OOM Klein on the 5060 Ti. The semaphore guarantees at most
# one zone-switch + workload runs at a time per process.
_INPROC_GPU_LOCK = threading.Semaphore(1)

# Depending on where this script is executed, `redis` might not be installed,
# but we assume the `agent_runtime` has it, or we'll install it.
try:
    import redis
except ImportError:
    import sys
    import subprocess
    logger.warning("redis-py missing, installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "redis"])
    import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis_queue")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
KLEIN_HOST = os.getenv("KLEIN_HOST", "http://klein_service:8189")
OMNIGEN_HOST = os.getenv("OMNIGEN_HOST", "http://omnigen_service:8190")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")
# GPU peer lock: Turing's agent_runtime hosts the lock server on its own uvicorn port.
# Default localhost:8000 is correct for single-node (same container).  A second
# agent_runtime on another host would set GPU_LOCK_HOST=http://<turing-ip>:8008.
GPU_LOCK_HOST = os.getenv("GPU_LOCK_HOST", "http://localhost:8000")
TRAINING_WINDOW_START = int(os.getenv("TRAINING_WINDOW_START", "2"))   # hour (24h)
TRAINING_WINDOW_END   = int(os.getenv("TRAINING_WINDOW_END",   "6"))   # hour (24h)

def _get_preferred_host(model_name: str) -> str:
    """
    Static hardware-aware routing (no health checks).

    Topology:
    - OLLAMA_HOST           → Lovelace (2× RTX 5060 Ti, 32 GB) — primary, large models
    - SECONDARY_OLLAMA_HOST → Turing   (RTX 3070 Ti,  8 GB)  — safety + embeddings

    Small/safe models go to Turing (SECONDARY_OLLAMA_HOST); everything else to Lovelace.
    Health-aware callers fall back to the other host if the preferred one is down.
    """
    # Models that live on Turing's local Ollama (RTX 3070 Ti, 8 GB VRAM).
    # As of current deployment, Turing only hosts: llama-guard3:8b, nomic-embed-text.
    # ALL other models (qwen3:8b, qwen3:14b, gemma4:31b, qwen3-coder:30b, qwen3.6:27b,
    # deepseek-r1:32b, etc.) live on Lovelace and are reached via OLLAMA_HOST.
    #
    # NOTE: In Turing's agent_runtime container, OLLAMA_HOST is set to Lovelace
    # (192.168.2.101:11434) and SECONDARY_OLLAMA_HOST is set to the local Turing
    # ollama service. This is the opposite of Lovelace's perspective (where
    # OLLAMA_HOST = local).  The routing below is consistent with BOTH:
    # - On Lovelace: SECONDARY_OLLAMA_HOST = Turing, these models are routed there ✓
    # - On Turing:   SECONDARY_OLLAMA_HOST = local ollama, these models are local ✓
    turing_safe = ["llama-guard", "nomic-embed"]

    if any(m in model_name for m in turing_safe):
        return SECONDARY_OLLAMA_HOST  # Turing: safety + embeddings (8 GB)
    # Everything else (gemma4, qwen3-coder:30b, qwen3.6:27b, qwen3:14b, etc.)
    # → Lovelace (dual 5060 Ti, 32 GB VRAM)
    return OLLAMA_HOST


def _get_fallback_host(preferred: str) -> str:
    """Returns the other host as fallback."""
    if preferred == OLLAMA_HOST:
        return SECONDARY_OLLAMA_HOST
    return OLLAMA_HOST


def get_ollama_host(model_name: str) -> str:
    """
    Health-aware routing with fallback.
    Checks preferred host health first; falls back to alternate if unhealthy.
    If both are down, returns preferred anyway (fail-open).
    """
    from inference.node_health import get_node_monitor

    preferred = _get_preferred_host(model_name)
    fallback = _get_fallback_host(preferred)
    monitor = get_node_monitor()

    if monitor.is_healthy(preferred):
        logger.info(f"[GPU Queue] Routing '{model_name}' to preferred host ({preferred}).")
        return preferred

    logger.warning(f"[GPU Queue] Preferred host {preferred} is DOWN for '{model_name}'.")

    if monitor.is_healthy(fallback):
        logger.info(f"[GPU Queue] Falling back to {fallback} for '{model_name}'.")
        return fallback

    logger.warning(f"[GPU Queue] Both hosts DOWN. Fail-open to preferred ({preferred}).")
    return preferred


def get_best_host_for_model(model_name: str) -> str:
    """
    Smart host selection — prefers hosts that already have the model loaded
    in VRAM (hot), then available on disk, then falls back to static routing.
    """
    from inference.node_health import get_node_monitor

    monitor = get_node_monitor()

    # Best case: model is already loaded in VRAM somewhere
    loaded_hosts = monitor.get_hosts_with_model_loaded(model_name)
    if loaded_hosts:
        # Prefer the statically-preferred host if it has the model loaded
        preferred = _get_preferred_host(model_name)
        if preferred in loaded_hosts:
            logger.info(f"[GPU Queue] '{model_name}' hot in VRAM on preferred host ({preferred}).")
            return preferred
        host = loaded_hosts[0]
        logger.info(f"[GPU Queue] '{model_name}' hot in VRAM on {host}.")
        return host

    # Next: model is available on disk on a healthy host
    available_hosts = monitor.get_hosts_with_model(model_name)
    if available_hosts:
        preferred = _get_preferred_host(model_name)
        if preferred in available_hosts:
            logger.info(f"[GPU Queue] '{model_name}' available on preferred host ({preferred}).")
            return preferred
        host = available_hosts[0]
        logger.info(f"[GPU Queue] '{model_name}' available on {host}.")
        return host

    # Fallback: health-aware static routing
    logger.info(f"[GPU Queue] '{model_name}' not found on any node, using health-aware fallback.")
    return get_ollama_host(model_name)

# ---------------------------------------------------------------------------
# Swarm round-robin: distribute workers across all available GPU hosts so
# they execute in parallel instead of serializing on a single Ollama instance.
# ---------------------------------------------------------------------------
_swarm_rr_counter = itertools.count()
_swarm_rr_lock = threading.Lock()


def get_swarm_worker_host(model_name: str) -> str:
    """
    Round-robin host selector for swarm coordinator workers.

    Distributes workers across GPU hosts for parallel execution, BUT only
    includes a host in the pool if the model can actually run there.
    - Small models (<=8B, safety, embeds): Turing + Lovelace pool (round-robin)
    - Large models (>8B): Lovelace only (Turing has 8GB VRAM, not enough)
    """
    preferred = _get_preferred_host(model_name)

    if preferred == SECONDARY_OLLAMA_HOST:
        # Small model — fits on Turing; can also run on Lovelace, so round-robin for parallelism
        candidates = [SECONDARY_OLLAMA_HOST]
        if OLLAMA_HOST and OLLAMA_HOST != SECONDARY_OLLAMA_HOST:
            candidates.append(OLLAMA_HOST)
    else:
        # Large model — Lovelace only; no round-robin to Turing (OOM risk on 8 GB)
        candidates = [OLLAMA_HOST]

    # Filter to healthy hosts
    try:
        from inference.node_health import get_node_monitor
        monitor = get_node_monitor()
        healthy = [h for h in candidates if monitor.is_healthy(h)]
    except Exception:
        healthy = []

    if not healthy:
        # All preferred candidates are down — fall back to primary host so
        # swarm workers degrade gracefully instead of routing to a dead host.
        # e.g. Turing (SECONDARY) offline → fall back to Lovelace Ollama container.
        fallback_candidates = [h for h in [OLLAMA_HOST, SECONDARY_OLLAMA_HOST]
                               if h and h not in candidates]
        try:
            monitor = get_node_monitor() if 'monitor' not in dir() else monitor
            healthy = [h for h in fallback_candidates if monitor.is_healthy(h)]
        except Exception:
            healthy = []
        if not healthy:
            # Last resort: primary host unconditionally
            logger.warning(f"[GPU Round-Robin] All hosts down for '{model_name}', fail-open to {OLLAMA_HOST}.")
            return OLLAMA_HOST

    pool = healthy if healthy else candidates

    with _swarm_rr_lock:
        idx = next(_swarm_rr_counter)
        host = pool[idx % len(pool)]

    logger.info(f"[GPU Round-Robin] Worker slot {idx}: '{model_name}' → {host} ({len(pool)} hosts in pool).")
    return host


def select_available_model(preferred: str, fallbacks: list) -> tuple:
    """
    Pre-flight VRAM check with model fallback waterfall.

    Returns (model_name, host) — the best model from the preference chain
    that is currently available, prioritising models already hot in VRAM.

    Strategy:
      1. Any model in the chain already hot in VRAM → use it (no load latency)
      2. Preferred model available on disk → accept cold-start cost
      3. Any fallback on disk → use it rather than risk an OOM cold start
      4. Last resort: return preferred + best host (let Ollama handle it)

    Typical call:
        model, host = select_available_model("qwen3:14b", ["qwen3:8b"])
    """
    try:
        from inference.node_health import get_node_monitor
        monitor = get_node_monitor()
    except Exception:
        host = get_best_host_for_model(preferred)
        logger.warning(f"[GPU Queue] select_available_model: node monitor unavailable, using {preferred}.")
        return preferred, host

    chain = [preferred] + list(fallbacks)

    # Pass 1: prefer anything already hot in VRAM (zero load cost)
    for model in chain:
        try:
            loaded = monitor.get_hosts_with_model_loaded(model)
        except Exception:
            loaded = []
        if loaded:
            pref = _get_preferred_host(model)
            host = pref if pref in loaded else loaded[0]
            logger.info(f"[GPU Queue] Model waterfall: '{model}' hot in VRAM on {host}.")
            return model, host

    # Pass 2: preferred model on disk (accept cold start)
    try:
        avail = monitor.get_hosts_with_model(preferred)
    except Exception:
        avail = []
    if avail:
        pref = _get_preferred_host(preferred)
        host = pref if pref in avail else avail[0]
        logger.info(f"[GPU Queue] Model waterfall: '{preferred}' on disk at {host} (cold start).")
        return preferred, host

    # Pass 3: any fallback on disk
    for model in fallbacks:
        try:
            avail = monitor.get_hosts_with_model(model)
        except Exception:
            avail = []
        if avail:
            pref = _get_preferred_host(model)
            host = pref if pref in avail else avail[0]
            logger.info(f"[GPU Queue] Model waterfall: fallback '{model}' on disk at {host}.")
            return model, host

    # Last resort
    host = get_best_host_for_model(preferred)
    logger.warning(f"[GPU Queue] Model waterfall: no model found in chain {chain}, using '{preferred}' on {host}.")
    return preferred, host


class AllModelsFailedError(RuntimeError):
    """Raised when every model in a fallback chain has failed inference."""


def _is_retriable_inference_error(exc: Exception | None, resp_status: int | None, resp_text: str) -> bool:
    """Decide whether an inference failure should trigger a chain-fallback retry."""
    if exc is not None:
        # Connection/timeout/network — definitely retriable
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return True
        # Ollama Python client raises generic exceptions; sniff the text
        msg = str(exc).lower()
        return any(token in msg for token in (
            "out of memory", "cuda", "oom", "500", "connection", "timeout",
            "refused", "unavailable", "model not found", "model '",
        ))
    if resp_status is None:
        return False
    if resp_status >= 500:
        return True
    if resp_status == 404 and "model" in resp_text.lower():
        # Ollama returns 404 when the requested model isn't pulled — try the next one.
        return True
    return False


def call_with_model_fallback(preferred: str, fallbacks: list, call_fn, *, max_retries: int = 2):
    """Run an inference call against a chain of models, dropping any that fail.

    `call_fn(model: str, host: str) -> result` does the actual HTTP / SDK call.
    It should raise a requests/ollama exception on failure, OR return a
    requests.Response with status >= 500 / 404 (model-not-found) to trigger retry.
    Any other return value is considered success and is returned as-is.

    On retriable failure, the failed model is dropped from the chain and
    select_available_model() is re-run against the remainder. Up to
    max_retries retries (so max_retries + 1 attempts total). If every model
    in the chain exhausts, raises AllModelsFailedError.
    """
    chain: list[str] = []
    for m in [preferred] + list(fallbacks):
        if m and m not in chain:
            chain.append(m)

    last_exc: Exception | None = None
    last_status: int | None = None
    last_text: str = ""
    attempts = 0

    while chain and attempts <= max_retries:
        # Re-run selection each attempt so we get the freshest VRAM picture.
        head, tail = chain[0], chain[1:]
        model, host = select_available_model(head, tail)

        try:
            result = call_fn(model, host)
            # If the callable returned a Response object, treat 500/404 as retriable
            status = getattr(result, "status_code", None)
            text = getattr(result, "text", "") or ""
            if status is not None and _is_retriable_inference_error(None, status, text):
                last_status = status
                last_text = text
                last_exc = None
                logger.warning(
                    f"[GPU Queue] Inference call to '{model}' on {host} returned "
                    f"status {status} — dropping from chain and retrying."
                )
            else:
                return result
        except Exception as e:
            if not _is_retriable_inference_error(e, None, ""):
                raise
            last_exc = e
            last_status = None
            last_text = ""
            logger.warning(
                f"[GPU Queue] Inference call to '{model}' on {host} raised "
                f"{type(e).__name__}: {e} — dropping from chain and retrying."
            )

        # Drop the model that actually ran (may differ from head if waterfall chose a fallback)
        chain = [m for m in chain if m != model]
        attempts += 1
        if chain:
            logger.info(
                f"[GPU Queue] Model fallback: retrying with chain {chain} "
                f"(attempt {attempts + 1}/{max_retries + 1})."
            )

    msg = (
        f"All models in chain [{preferred}] + {fallbacks} exhausted "
        f"after {attempts} attempt(s)."
    )
    if last_exc is not None:
        raise AllModelsFailedError(msg) from last_exc
    raise AllModelsFailedError(f"{msg} last_status={last_status} last_text={last_text[:200]!r}")


def is_training_window() -> bool:
    """
    Check if current time falls within the training window.
    Default: 2am–6am local time (configurable via env vars).
    Training should only run during idle hours to avoid disrupting inference.
    """
    now = datetime.now()
    if TRAINING_WINDOW_START < TRAINING_WINDOW_END:
        return TRAINING_WINDOW_START <= now.hour < TRAINING_WINDOW_END
    else:
        # Handles wrap-around (e.g., 22:00–06:00)
        return now.hour >= TRAINING_WINDOW_START or now.hour < TRAINING_WINDOW_END


def get_redis_client():
    return redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=0,
        password=REDIS_PASSWORD, decode_responses=True
    )

LOCK_KEY = "swarm_gpu_lock"
ZONE_KEY = "swarm_gpu_zone"  # Track whether VRAM is currently dedicated to "text", "image", or "training"


# ---------------------------------------------------------------------------
# Circuit breaker for eviction / warmup HTTP calls.
#
# A flapping Klein/ComfyUI/OmniGen service that times out every call would
# otherwise pin every GPU-using request inside a long evict→warmup→fail
# loop, then immediately retry on the next request — itself a GPU thrash
# path that ends in OOM. The breaker short-circuits known-bad endpoints
# for 60s after 3 consecutive failures, then probes once (half-open).
# ---------------------------------------------------------------------------
class _CircuitBreaker:
    FAIL_THRESHOLD = 3
    FAIL_WINDOW_S = 60.0
    OPEN_DURATION_S = 60.0

    def __init__(self):
        self._lock = threading.Lock()
        # key -> dict(state, failures, first_failure_at, opened_at, service, host)
        self._circuits: dict[tuple, dict] = {}

    @staticmethod
    def _label(host: str) -> str:
        # Strip scheme/port for tidy metric labels (e.g. http://klein_service:8189 -> klein_service)
        try:
            from urllib.parse import urlparse
            netloc = urlparse(host).netloc or host
            return netloc.split(":")[0]
        except Exception:
            return host

    def _emit(self, key, state: str):
        host, service = key[0], key[1]
        try:
            GPU_SERVICE_CIRCUIT_OPEN.labels(
                host=self._label(host), service=service
            ).set(1 if state == "open" else 0)
        except Exception:
            pass

    def allow(self, host: str, service: str) -> bool:
        """Return True if the call should proceed; False to short-circuit."""
        key = (host, service)
        now = time.monotonic()
        with self._lock:
            c = self._circuits.get(key)
            if not c or c["state"] == "closed":
                return True
            if c["state"] == "open":
                if now - c["opened_at"] >= self.OPEN_DURATION_S:
                    c["state"] = "half_open"
                    logger.warning(
                        f"[GPU Queue] Circuit '{service}'@{self._label(host)} → HALF-OPEN (probing after {self.OPEN_DURATION_S:.0f}s cooldown)."
                    )
                    return True
                return False
            # half_open: only one probe allowed at a time; allow it
            return True

    def record_success(self, host: str, service: str) -> None:
        key = (host, service)
        with self._lock:
            c = self._circuits.get(key)
            if c and c["state"] != "closed":
                logger.warning(
                    f"[GPU Queue] Circuit '{service}'@{self._label(host)} → CLOSED (probe succeeded)."
                )
            self._circuits[key] = {"state": "closed", "failures": 0, "first_failure_at": 0.0, "opened_at": 0.0}
            self._emit(key, "closed")

    def record_failure(self, host: str, service: str) -> None:
        key = (host, service)
        now = time.monotonic()
        with self._lock:
            c = self._circuits.get(key) or {"state": "closed", "failures": 0, "first_failure_at": 0.0, "opened_at": 0.0}
            if c["state"] == "half_open":
                c["state"] = "open"
                c["opened_at"] = now
                self._circuits[key] = c
                logger.warning(
                    f"[GPU Queue] Circuit '{service}'@{self._label(host)} → OPEN again (probe failed)."
                )
                self._emit(key, "open")
                return
            # closed or already-open: count toward threshold within window
            if now - c["first_failure_at"] > self.FAIL_WINDOW_S:
                c["failures"] = 1
                c["first_failure_at"] = now
            else:
                c["failures"] += 1
            if c["state"] == "closed" and c["failures"] >= self.FAIL_THRESHOLD:
                c["state"] = "open"
                c["opened_at"] = now
                logger.warning(
                    f"[GPU Queue] Circuit '{service}'@{self._label(host)} → OPEN "
                    f"({c['failures']} failures in <{self.FAIL_WINDOW_S:.0f}s; short-circuiting for {self.OPEN_DURATION_S:.0f}s)."
                )
                self._emit(key, "open")
            self._circuits[key] = c


_circuit_breaker = _CircuitBreaker()


def _guarded_post(host: str, service: str, path: str, *, timeout: float, json_body=None):
    """requests.post wrapper that respects the eviction circuit breaker.

    Returns the requests.Response on success, or None when short-circuited
    or on transport failure. Callers must treat None as "couldn't reach service".
    """
    if not _circuit_breaker.allow(host, service):
        logger.warning(
            f"[GPU Queue] Circuit OPEN for {service}@{host} — skipping POST {path}."
        )
        return None
    try:
        resp = requests.post(f"{host}{path}", json=json_body, timeout=timeout)
        if 200 <= resp.status_code < 500:
            _circuit_breaker.record_success(host, service)
        else:
            _circuit_breaker.record_failure(host, service)
        return resp
    except Exception as e:
        _circuit_breaker.record_failure(host, service)
        logger.warning(f"[GPU Queue] {service} POST {path} failed: {e}")
        return None

def evict_comfyui():
    """Unloads ComfyUI model weights from VRAM (unload_models=True frees the checkpoint)."""
    logger.info("[GPU Queue] Evicting ComfyUI model weights from VRAM...")
    response = _guarded_post(
        COMFYUI_HOST, "comfyui", "/free",
        timeout=10,
        json_body={"unload_models": True, "free_memory": True},
    )
    if response is None:
        return
    if response.status_code == 200:
        logger.info("[GPU Queue] ComfyUI VRAM evicted successfully.")
    else:
        logger.warning(f"[GPU Queue] ComfyUI /free endpoint returned status {response.status_code}.")

def _restart_container(name: str) -> bool:
    """Restart a Docker container by name via the Docker Unix socket.

    On WDDM (Windows), PyTorch's empty_cache() calls cudaFree but WDDM may
    hold physical GPU pages in the process context indefinitely — even minutes
    after the cache is cleared. Restarting the container destroys the CUDA
    context, forcing WDDM to immediately return all physical pages to the pool.

    Returns True if the restart succeeded, False otherwise.
    """
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(15)
        s.connect("/var/run/docker.sock")
        req = f"POST /containers/{name}/restart HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        s.sendall(req.encode())
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        status_line = resp.split(b"\r\n")[0].decode(errors="replace")
        # 204 No Content = success; 404 = container not found
        if b"204" in resp[:50]:
            logger.info(f"[GPU Queue] Container '{name}' restarted (WDDM VRAM released).")
            return True
        else:
            logger.warning(f"[GPU Queue] Container restart returned: {status_line}")
            return False
    except Exception as e:
        logger.warning(f"[GPU Queue] Could not restart container '{name}': {e}")
        return False


def evict_klein():
    """Fully unloads the Klein model weights from VRAM so Ollama/ComfyUI can use both GPUs.

    Phase 1 (always): POST /evict → Klein moves tensors to CPU + synchronize/empty_cache/gc.
        Long timeout because BF16 text encoders + FP8 transformer are several GB to move,
        and the FP8 forward-patch closures create reference cycles that gc has to break.

    Phase 2 (opt-in, EVICT_CONTAINER_RESTART=true): restart the klein_service container to
        destroy the CUDA context. Needed on WDDM (Windows) hosts where empty_cache() may
        not return physical pages immediately. Only meaningful when this process has docker
        socket write access to the Klein container — i.e. the agent_runtime running on the
        same host as klein_service (Lovelace). Remote agent_runtimes (e.g. Turing) skip
        this phase since they don't own the container.
    """
    # Phase 1: graceful unload — generous timeout, the actual work happens on Klein
    logger.info("[GPU Queue] Evicting Klein model from VRAM (graceful)...")
    response = _guarded_post(KLEIN_HOST, "klein", "/evict", timeout=180)
    if response is not None:
        if response.status_code == 200:
            logger.info("[GPU Queue] Klein VRAM evicted (graceful phase complete).")
        else:
            logger.warning(f"[GPU Queue] Klein /evict returned status {response.status_code}.")

    # Phase 2: optional container restart — only on the host that owns the container
    if os.getenv("EVICT_CONTAINER_RESTART", "false").lower() not in ("true", "1", "yes"):
        logger.info("[GPU Queue] Skipping Klein container restart (EVICT_CONTAINER_RESTART not set).")
        return

    time.sleep(2)
    restarted = _restart_container("klein_service")
    if not restarted:
        logger.warning("[GPU Queue] Klein container restart did not succeed; relying on graceful eviction.")
        return

    # Wait for Klein to come back up (FastAPI cold start without model load ≈ 5s).
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(2)
        try:
            h = requests.get(f"{KLEIN_HOST}/health", timeout=3).json()
            if h.get("status") == "ok":
                logger.info("[GPU Queue] Klein container back up after restart.")
                return
        except Exception:
            pass
    logger.warning("[GPU Queue] Klein container did not respond to /health within 30s after restart.")


def warmup_klein():
    """Triggers Klein to pre-load its model into VRAM before generation starts.
    Retries once after a WDDM grace delay — if the first attempt fails (e.g.
    GPU 0 pages from a prior eviction not yet returned), wait 20s and retry."""
    for attempt in range(2):
        logger.info(f"[GPU Queue] Warming up Klein pipeline (attempt {attempt + 1})...")
        # 600s: first load from HF cache takes ~400s; subsequent loads ~60s
        response = _guarded_post(KLEIN_HOST, "klein", "/warmup", timeout=600)
        if response is not None:
            if response.status_code == 200:
                logger.info("[GPU Queue] Klein pipeline warm.")
                return
            logger.warning(f"[GPU Queue] Klein /warmup returned status {response.status_code}.")

        if attempt == 0:
            logger.info("[GPU Queue] Klein warmup failed — waiting 20s for WDDM page reclaim, then retrying...")
            time.sleep(20)

def evict_omnigen():
    """Unloads OmniGen2 weights via POST /evict. Used in the Klein↔OmniGen swap
    inside the image zone. Mirrors evict_klein's graceful-only approach — we
    don't restart the container because OmniGen runs on a single GPU and
    torch.cuda.empty_cache() is typically sufficient (no dual-GPU WDDM trap)."""
    logger.info("[GPU Queue] Evicting OmniGen2 model from VRAM (graceful)...")
    response = _guarded_post(OMNIGEN_HOST, "omnigen", "/evict", timeout=180)
    if response is not None:
        if response.status_code == 200:
            logger.info("[GPU Queue] OmniGen2 VRAM evicted.")
        else:
            logger.warning(f"[GPU Queue] OmniGen2 /evict returned status {response.status_code}.")


def _omnigen_is_healthy() -> bool:
    """Health check analog to Klein's. Returns True if the service is reachable
    and reports pipeline_loaded OR is loadable (mirroring the Klein cold-start
    fix — explicit /warmup call before /compose handles the actual load)."""
    try:
        r = requests.get(f"{OMNIGEN_HOST}/health", timeout=3)
        if r.status_code != 200:
            return False
        data = r.json()
        return bool(data.get("pipeline_loaded") or data.get("model") is not None)
    except Exception:
        return False


def warmup_omnigen():
    """Pre-load OmniGen2 weights. First load from HF cache ~200s; warm ~30s."""
    for attempt in range(2):
        logger.info(f"[GPU Queue] Warming up OmniGen2 pipeline (attempt {attempt + 1})...")
        response = _guarded_post(OMNIGEN_HOST, "omnigen", "/warmup", timeout=600)
        if response is not None:
            if response.status_code == 200:
                logger.info("[GPU Queue] OmniGen2 pipeline warm.")
                return
            logger.warning(f"[GPU Queue] OmniGen2 /warmup returned status {response.status_code}.")
        if attempt == 0:
            time.sleep(20)


def evict_ollama():
    """Unloads active models from all Ollama hosts (primary + secondary) via keep_alive=0.
    Both hosts must be evicted — large models run on OLLAMA_HOST (Lovelace) which shares
    physical GPUs with ComfyUI/Klein. Turing (SECONDARY_OLLAMA_HOST) holds safety/embedding
    models. Polls /api/ps after eviction to confirm VRAM is free before returning."""
    hosts_to_evict = [OLLAMA_HOST]
    if SECONDARY_OLLAMA_HOST and SECONDARY_OLLAMA_HOST != OLLAMA_HOST:
        hosts_to_evict.append(SECONDARY_OLLAMA_HOST)

    for host in hosts_to_evict:
        try:
            logger.info(f"[GPU Queue] Evicting Ollama models from VRAM on {host}...")
            ps_resp = requests.get(f"{host}/api/ps", timeout=5)
            if ps_resp.status_code != 200:
                logger.warning(f"[GPU Queue] Could not reach Ollama /api/ps on {host}, skipping.")
                continue

            models = ps_resp.json().get("models", [])
            if not models:
                logger.info(f"[GPU Queue] No active models on {host} to evict.")
                continue

            for model in models:
                model_name = model.get("name")
                logger.info(f"[GPU Queue] Unloading {model_name} from {host}")
                try:
                    requests.post(f"{host}/api/generate", json={
                        "model": model_name,
                        "keep_alive": 0
                    }, timeout=10)
                except Exception as e:
                    logger.warning(f"[GPU Queue] keep_alive=0 request timed out for {model_name} on {host}: {e}")

            # Poll /api/ps until models list is empty — unload is async, VRAM needs time to free
            deadline = time.time() + 20
            while time.time() < deadline:
                time.sleep(2)
                try:
                    check = requests.get(f"{host}/api/ps", timeout=3)
                    if check.status_code == 200 and not check.json().get("models", []):
                        logger.info(f"[GPU Queue] Ollama VRAM confirmed free on {host}.")
                        break
                except Exception:
                    break
            else:
                logger.warning(f"[GPU Queue] Ollama VRAM may not be fully free on {host} after 20s — proceeding anyway.")
        except Exception as e:
            logger.warning(f"[GPU Queue] Failed to evict Ollama VRAM on {host}: {e}")

def _run_zone_switch(context: str, current_zone):
    """Perform the eviction/warmup sequence for the requested zone."""
    if current_zone == context:
        logger.info(f"[GPU Queue] GPU is already in '{context}' zone. No eviction needed.")
        return
    logger.info(f"[GPU Queue] Context switch detected: '{current_zone}' -> '{context}'. Prepping VRAM...")
    if context == "text":
        # Switching to text -> evict image backends so Ollama can use both GPUs.
        evict_comfyui()
        evict_klein()
        evict_omnigen()
    elif context == "image":
        # Switching to image -> evict Ollama + ComfyUI + OmniGen to clear both GPUs,
        # then warm Klein (needs GPU 1's full 15 GiB free to load).
        evict_ollama()
        evict_comfyui()
        evict_omnigen()
        warmup_klein()
    elif context == "compose":
        # OmniGen2 multi-image composition zone. Mutually exclusive with Klein
        # at the GPU layer — both target physical GPU 1.
        evict_ollama()
        evict_comfyui()
        evict_klein()
        warmup_omnigen()
    elif context == "training":
        # Training needs exclusive VRAM — evict everything
        evict_ollama()
        evict_comfyui()
        evict_klein()
        evict_omnigen()
    else:
        logger.warning(f"[GPU Queue] Unknown context '{context}'.")


@contextmanager
def request_lock(context: str, timeout: int = 300):
    """
    Acquires a global Mutex lock for the GPU and handles VRAM eviction for context switching.
    context must be one of "text", "image", "compose", or "training".

    Two-layer locking:
      1. Cross-process: a Redis NX/EX mutex coordinates between agent_runtimes.
      2. In-process: a threading.Semaphore(1) guarantees a single agent_runtime
         process never runs two zone-switches concurrently — even when Redis
         is unavailable. This is the backstop against single-host OOMs when
         the cluster-wide mutex is degraded.

    Degraded mode: if Redis is unavailable we still hold the in-process
    semaphore, increment gpu_lock_degraded_total, and set gpu_mutex_healthy=0
    so operators can alert on it.
    """
    t_total_start = time.monotonic()
    client = None
    try:
        client = get_redis_client()
        client.ping()  # Verify connection before proceeding
        GPU_MUTEX_HEALTHY.set(1)
    except Exception as e:
        # Tier 1 (Redis) is down.  Try Tier 2: cross-host peer HTTP lock.
        logger.error(
            f"[GPU Queue] Redis unavailable ({e}). Cross-process Redis GPU mutex "
            f"is DEGRADED — trying peer HTTP lock (Tier 2)."
        )
        try:
            GPU_LOCK_DEGRADED_TOTAL.labels(reason="redis_unavailable").inc()
            GPU_MUTEX_HEALTHY.set(0)
        except Exception:
            pass

        from utils.peer_lock import (
            PeerLockUnavailableError,
            PeerLockTimeoutError,
            peer_lock,
        )
        try:
            with peer_lock(context, timeout=timeout):
                # Peer lock acquired — cross-host coordination is active.
                logger.info(
                    f"[GPU Queue] Peer HTTP lock acquired (Tier 2) for context='{context}'."
                )
                with _INPROC_GPU_LOCK:
                    yield
            return
        except PeerLockUnavailableError as pl_exc:
            # Lock server unreachable — fall all the way through to Tier 3.
            logger.error(
                f"[GPU Queue] Peer HTTP lock server unreachable ({pl_exc}). "
                f"Falling back to in-process semaphore ONLY (Tier 3). "
                f"Multi-host GPU coordination is OFF — concurrent agent_runtimes "
                f"on different hosts can now race. Check {GPU_LOCK_HOST!r}."
            )
            try:
                GPU_PEER_LOCK_DEGRADED_TOTAL.labels(reason="server_unreachable").inc()
            except Exception:
                pass
        except PeerLockTimeoutError as pl_exc:
            logger.error(
                f"[GPU Queue] Peer HTTP lock timed out ({pl_exc}). "
                f"Falling back to in-process semaphore ONLY (Tier 3)."
            )
            try:
                GPU_PEER_LOCK_DEGRADED_TOTAL.labels(reason="timeout").inc()
            except Exception:
                pass

        # Tier 3: in-process semaphore (only serializes within this process).
        with _INPROC_GPU_LOCK:
            yield
        return

    lock_id = os.urandom(16).hex()
    acquired = False
    logger.info(f"[GPU Queue] Attempting to acquire GPU lock for context: '{context}'...")

    start_time = time.time()
    t_acquire_start = time.monotonic()
    t_lock_wait = 0.0
    t_eviction = 0.0
    t_work = 0.0
    try:
        # Spin loop until lock is acquired or timeout
        while time.time() - start_time < timeout:
            # nx=True: only sets if key doesn't exist. ex=timeout: expires even if process crashes.
            if client.set(LOCK_KEY, lock_id, nx=True, ex=timeout):
                acquired = True
                t_lock_wait = time.monotonic() - t_acquire_start
                logger.info(f"[GPU Queue] Lock acquired for context: '{context}'.")
                break
            time.sleep(1)

        if not acquired:
            raise TimeoutError("[GPU Queue] Failed to acquire GPU lock within timeout.")

        # In-process backstop. Even with the Redis mutex held cluster-wide,
        # a second thread in this process must not race the zone switch.
        with _INPROC_GPU_LOCK:
            current_zone = client.get(ZONE_KEY)
            t_evict_start = time.monotonic()
            _run_zone_switch(context, current_zone)
            client.set(ZONE_KEY, context)
            t_eviction = time.monotonic() - t_evict_start

            t_work_start = time.monotonic()
            yield
            t_work = time.monotonic() - t_work_start

    finally:
        if acquired:
            # Only release if we actually hold the lock based on lock_id
            try:
                if client is not None and client.get(LOCK_KEY) == lock_id:
                    client.delete(LOCK_KEY)
                    logger.info(f"[GPU Queue] Lock released for context: '{context}'.")
            except Exception as e:
                logger.warning(f"[GPU Queue] Lock release failed: {e}")
            t_total = time.monotonic() - t_total_start
            logger.info(
                f"[Timing] context={context} lock_wait={t_lock_wait:.2f}s "
                f"eviction={t_eviction:.2f}s work={t_work:.2f}s total={t_total:.2f}s"
            )


# ---------------------------------------------------------------------------
# Tiered Queue System
#
# Design:
#   SMALL models (≤ LARGE_MODEL_VRAM_THRESHOLD_GB): bypass the lock entirely.
#     Ollama handles concurrent small-model requests natively. No Redis queue.
#   LARGE models (> threshold): serialized via the existing Redis mutex PLUS
#     a Redis list (swarm:queue:large) that tracks queue position for UX.
#
# The Redis queue list entries are JSON strings:
#   {"request_id": str, "uid": str, "model": str, "queued_at": float}
#
# SSE feedback:
#   Before acquiring request_lock for a large model, call get_queue_status()
#   and yield a "model_queue_status" event to the client. If wait > 30s and
#   alternatives exist, set should_prompt = True for the UI to offer options.
# ---------------------------------------------------------------------------

LARGE_QUEUE_KEY      = "swarm:queue:large"
PROMPT_WAIT_THRESHOLD = 30   # seconds — show alternative suggestion above this

def _get_loaded_model_names(host: str = OLLAMA_HOST) -> list[str]:
    """Query Ollama /api/ps and return names of currently VRAM-resident models."""
    try:
        resp = requests.get(f"{host}/api/ps", timeout=5)
        if resp.status_code == 200:
            return [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def enqueue_large_request(request_id: str, uid: str, model: str) -> int:
    """
    Add a large-model request to the Redis position queue.
    Returns the 1-based position (1 = next to run).
    Fail-open: returns 0 if Redis is unavailable.
    """
    import json as _json
    import time as _time
    try:
        client = get_redis_client()
        entry = _json.dumps({
            "request_id": request_id,
            "uid": uid,
            "model": model,
            "queued_at": _time.time(),
        })
        client.rpush(LARGE_QUEUE_KEY, entry)
        length = client.llen(LARGE_QUEUE_KEY)
        logger.debug(f"[GPU Queue] Enqueued request {request_id} for {model}. Position: {length}")
        return length
    except Exception as e:
        logger.debug(f"[GPU Queue] Could not enqueue request (fail-open): {e}")
        return 0


def dequeue_large_request(request_id: str) -> None:
    """Remove a request from the position queue when it completes."""
    import json as _json
    try:
        client = get_redis_client()
        entries = client.lrange(LARGE_QUEUE_KEY, 0, -1)
        for entry in entries:
            try:
                data = _json.loads(entry)
                if data.get("request_id") == request_id:
                    client.lrem(LARGE_QUEUE_KEY, 1, entry)
                    logger.debug(f"[GPU Queue] Dequeued request {request_id}")
                    return
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[GPU Queue] Could not dequeue request (non-fatal): {e}")


def get_queue_status(model_name: str, uid: str = "") -> dict:
    """
    Return queue status for a model request — used to generate SSE feedback
    BEFORE acquiring the GPU lock.

    Returned dict shape (also the payload for "model_queue_status" SSE event):
    {
      "model":            str,
      "tier":             "small" | "large",
      "is_loaded":        bool,     # model currently in Ollama VRAM
      "queue_position":   int,      # 0 = no wait, N = N requests ahead
      "estimated_wait_s": int,      # seconds until this request can start
      "alternatives":     [         # loaded alternatives that could answer faster
          {"name": str, "description": str, "vram_gb": float}
      ],
      "should_prompt":    bool,     # True → UI should offer alternative suggestion
    }
    """
    try:
        from model_registry import is_large_model, get_alternatives, estimate_queue_wait, get_model
    except ImportError:
        # model_registry not available — return minimal safe status
        return {
            "model": model_name, "tier": "large", "is_loaded": False,
            "queue_position": 0, "estimated_wait_s": 20,
            "alternatives": [], "should_prompt": False,
        }

    tier = "large" if is_large_model(model_name) else "small"

    # Small models: no queue, just check if loaded
    if tier == "small":
        loaded = _get_loaded_model_names()
        return {
            "model": model_name,
            "tier": "small",
            "is_loaded": model_name in loaded,
            "queue_position": 0,
            "estimated_wait_s": 0,
            "alternatives": [],
            "should_prompt": False,
        }

    # Large model: check VRAM residency and queue depth
    loaded = _get_loaded_model_names()
    is_loaded = model_name in loaded

    # Queue depth: how many large requests are currently ahead of ours
    queue_depth = 0
    try:
        client = get_redis_client()
        queue_depth = client.llen(LARGE_QUEUE_KEY)
    except Exception:
        pass

    estimated_wait = 0 if is_loaded else estimate_queue_wait(model_name, queue_depth)

    # Find currently-loaded alternatives that could answer without a model swap
    alt_specs = get_alternatives(model_name, only_available=True)
    loaded_alts = [
        {"name": s.name, "description": s.description, "vram_gb": s.vram_gb}
        for s in alt_specs
        if s.name in loaded
    ]

    should_prompt = (
        estimated_wait > PROMPT_WAIT_THRESHOLD
        and len(loaded_alts) > 0
    )

    return {
        "model": model_name,
        "tier": tier,
        "is_loaded": is_loaded,
        "queue_position": queue_depth,
        "estimated_wait_s": estimated_wait,
        "alternatives": loaded_alts,
        "should_prompt": should_prompt,
    }


def pre_lock_status_events(context: str, model_name: str = "", uid: str = ""):
    """
    Generator — yields SSE-style dicts describing GPU contention BEFORE
    ``request_lock()`` is called.  Designed for: ``yield from pre_lock_status_events(...)``.

    Emits up to three events (all optional):
      {"type": "status", "content": "⏳ GPU busy — N ahead..."}
        → when lock is currently held by another request
      {"type": "status", "content": "⚡ Releasing <zone> context..."}
        → when a zone switch is required (e.g. image → text)
      {"type": "model_queue_status", ...}
        → when the target model is not loaded in VRAM or queue_position > 0

    Always non-blocking and fail-open: if Redis is unavailable, yields nothing.
    """
    try:
        _client = get_redis_client()
        _client.ping()
    except Exception:
        return

    lock_held = bool(_client.get(LOCK_KEY))
    current_zone = _client.get(ZONE_KEY)

    if lock_held:
        try:
            queue_depth = _client.llen(LARGE_QUEUE_KEY)
        except Exception:
            queue_depth = 0

        if queue_depth > 1:
            yield {"type": "status", "content": f"⏳ GPU is busy — {queue_depth} request(s) queued ahead of you..."}
        else:
            yield {"type": "status", "content": "⏳ GPU is busy — queuing your request..."}

    elif current_zone and current_zone != context:
        _zone_labels = {
            "text": "text inference",
            "image": "image generation",
            "compose": "image composition",
            "training": "model training",
        }
        from_label = _zone_labels.get(current_zone, current_zone)
        to_label = _zone_labels.get(context, context)
        yield {"type": "status", "content": f"⚡ Releasing {from_label} GPU context → switching to {to_label}..."}

    if model_name:
        try:
            qs = get_queue_status(model_name, uid)
            # Only surface the event when there is actually something to report
            if not qs.get("is_loaded", True) or qs.get("queue_position", 0) > 0 or qs.get("should_prompt"):
                yield {"type": "model_queue_status", **qs}
        except Exception:
            pass
