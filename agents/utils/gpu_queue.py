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
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")
TRAINING_WINDOW_START = int(os.getenv("TRAINING_WINDOW_START", "2"))   # hour (24h)
TRAINING_WINDOW_END   = int(os.getenv("TRAINING_WINDOW_END",   "6"))   # hour (24h)

def _get_preferred_host(model_name: str) -> str:
    """
    Static hardware-aware routing (no health checks).

    Current topology (all execution-plane services run on Lovelace, 192.168.2.101):
    - OLLAMA_HOST     = http://ollama:11434           → Lovelace local Ollama (2× 5060 Ti, 32GB)
    - SECONDARY_OLLAMA_HOST = http://192.168.2.103:11434 → Turing (3070 Ti 8GB, currently offline)

    Small models are sent directly to OLLAMA_HOST (Lovelace).
    Large models try SECONDARY_OLLAMA_HOST (Turing) first; when Turing is offline the
    health check in get_swarm_worker_host() falls back to OLLAMA_HOST (Lovelace).
    Net effect: all traffic lands on http://ollama:11434 until Turing is back online.
    """
    # Models confirmed to fit on Turing (≤8B params / safety / embeddings).
    # Use precise prefixes: "qwen3:1." matches "qwen3:1.7b" but NOT "qwen3:14b";
    # "qwen3:4b" matches exactly; bare "qwen3:1" would be a substring of "qwen3:14b".
    turing_safe = ["llama-guard", "nomic-embed", "qwen3:0.", "qwen3:1.", "qwen3:4b", "qwen3:8b"]

    if any(m in model_name for m in turing_safe):
        return OLLAMA_HOST
    # Everything else goes to Lovelace (dual 5060 Ti, 32GB VRAM)
    return SECONDARY_OLLAMA_HOST


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

    if preferred == OLLAMA_HOST:
        # Small model — can run on either host; round-robin for parallelism
        candidates = [OLLAMA_HOST]
        if SECONDARY_OLLAMA_HOST and SECONDARY_OLLAMA_HOST != OLLAMA_HOST:
            candidates.append(SECONDARY_OLLAMA_HOST)
    else:
        # Large model — Lovelace only; no round-robin to Turing (OOM risk)
        candidates = [SECONDARY_OLLAMA_HOST]

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

def evict_comfyui():
    """Unloads ComfyUI model weights from VRAM (unload_models=True frees the checkpoint)."""
    try:
        logger.info("[GPU Queue] Evicting ComfyUI model weights from VRAM...")
        response = requests.post(
            f"{COMFYUI_HOST}/free",
            json={"unload_models": True, "free_memory": True},
            timeout=10,
        )
        if response.status_code == 200:
            logger.info("[GPU Queue] ComfyUI VRAM evicted successfully.")
        else:
            logger.warning(f"[GPU Queue] ComfyUI /free endpoint returned status {response.status_code}.")
    except Exception as e:
        logger.warning(f"[GPU Queue] Failed to evict ComfyUI VRAM: {e}")

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

    Two-phase eviction:
    1. Graceful: POST /evict → Klein moves tensors to CPU + calls synchronize/empty_cache.
    2. Hard: restart the container → destroys the CUDA context so WDDM immediately returns
       the physical GPU pages (~9.7 GB text-encoder residual on GPU 0, ~9.1 GB transformer
       residual on GPU 1). Without this, WDDM holds those pages in Klein's process context
       indefinitely, causing the next Klein reload to map into system RAM instead of VRAM.
    """
    # Phase 1: graceful unload
    try:
        logger.info("[GPU Queue] Evicting Klein model from VRAM (graceful)...")
        response = requests.post(f"{KLEIN_HOST}/evict", timeout=30)
        if response.status_code == 200:
            logger.info("[GPU Queue] Klein VRAM evicted (graceful phase complete).")
        else:
            logger.warning(f"[GPU Queue] Klein /evict returned status {response.status_code}.")
    except Exception as e:
        logger.warning(f"[GPU Queue] Graceful Klein eviction failed: {e}")

    # Phase 2: container restart — frees WDDM-held physical pages
    # Wait briefly for the graceful eviction to finish writing to CPU before restart.
    time.sleep(2)
    _restart_container("klein_service")

    # Wait for Klein to come back up (FastAPI cold start without model load ≈ 5s).
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(2)
        try:
            h = requests.get(f"{KLEIN_HOST}/health", timeout=3).json()
            if h.get("status") == "ok":
                logger.info("[GPU Queue] Klein container back up after restart.")
                break
        except Exception:
            pass


def warmup_klein():
    """Triggers Klein to pre-load its model into VRAM before generation starts.
    Retries once after a WDDM grace delay — if the first attempt fails (e.g.
    GPU 0 pages from a prior eviction not yet returned), wait 20s and retry."""
    for attempt in range(2):
        try:
            logger.info(f"[GPU Queue] Warming up Klein pipeline (attempt {attempt + 1})...")
            # 600s: first load from HF cache takes ~400s; subsequent loads ~60s
            response = requests.post(f"{KLEIN_HOST}/warmup", timeout=600)
            if response.status_code == 200:
                logger.info("[GPU Queue] Klein pipeline warm.")
                return
            else:
                logger.warning(f"[GPU Queue] Klein /warmup returned status {response.status_code}.")
        except Exception as e:
            logger.warning(f"[GPU Queue] Klein warmup attempt {attempt + 1} failed: {e}")

        if attempt == 0:
            logger.info("[GPU Queue] Klein warmup failed — waiting 20s for WDDM page reclaim, then retrying...")
            time.sleep(20)

def evict_ollama():
    """Unloads active models from all Ollama hosts (primary + secondary) via keep_alive=0.
    Both hosts must be evicted — large models run on SECONDARY_OLLAMA_HOST (Lovelace) which
    shares physical GPUs with ComfyUI. Evicting only OLLAMA_HOST (Turing, no GPU) is a no-op.
    Polls /api/ps after eviction to confirm VRAM is actually free before returning."""
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

@contextmanager
def request_lock(context: str, timeout: int = 300):
    """
    Acquires a global Mutex lock for the GPU and handles VRAM eviction for context switching.
    context must be either "text" or "image".
    Fail-open: if Redis is unavailable, skip the lock and run without GPU mutex.
    """
    t_total_start = time.monotonic()
    try:
        client = get_redis_client()
        client.ping()  # Verify connection before proceeding
    except Exception as e:
        logger.warning(f"[GPU Queue] Redis unavailable ({e}). Running without GPU lock (fail-open).")
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
            # nx=True ensures that the key is only set if it does not already exist
            # ex=timeout ensures the lock expires even if the process crashes
            if client.set(LOCK_KEY, lock_id, nx=True, ex=timeout):
                acquired = True
                t_lock_wait = time.monotonic() - t_acquire_start
                logger.info(f"[GPU Queue] Lock acquired for context: '{context}'.")
                break
            time.sleep(1)

        if not acquired:
            raise TimeoutError("[GPU Queue] Failed to acquire GPU lock within timeout.")

        # Smart Context Switching
        current_zone = client.get(ZONE_KEY)
        t_evict_start = time.monotonic()
        if current_zone != context:
            logger.info(f"[GPU Queue] Context switch detected: '{current_zone}' -> '{context}'. Prepping VRAM...")
            if context == "text":
                # Switching to text -> evict image backends so Ollama can use both GPUs.
                evict_comfyui()
                evict_klein()
            elif context == "image":
                # Switching to image -> evict Ollama + ComfyUI to clear both GPUs,
                # then warm Klein (needs GPU 1's full 15 GiB free to load).
                evict_ollama()
                evict_comfyui()
                warmup_klein()
            elif context == "training":
                # Training needs exclusive VRAM — evict everything
                evict_ollama()
                evict_comfyui()
                evict_klein()
            else:
                logger.warning(f"[GPU Queue] Unknown context '{context}'.")

            # Update the current zone
            client.set(ZONE_KEY, context)
        else:
            logger.info(f"[GPU Queue] GPU is already in '{context}' zone. No eviction needed.")
        t_eviction = time.monotonic() - t_evict_start

        # Yield back to the block doing the work
        t_work_start = time.monotonic()
        yield
        t_work = time.monotonic() - t_work_start

    finally:
        if acquired:
            # Only release if we actually hold the lock based on lock_id
            if client.get(LOCK_KEY) == lock_id:
                client.delete(LOCK_KEY)
                logger.info(f"[GPU Queue] Lock released for context: '{context}'.")
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
