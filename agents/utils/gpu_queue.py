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
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")
TRAINING_WINDOW_START = int(os.getenv("TRAINING_WINDOW_START", "2"))   # hour (24h)
TRAINING_WINDOW_END   = int(os.getenv("TRAINING_WINDOW_END",   "6"))   # hour (24h)

def _get_preferred_host(model_name: str) -> str:
    """
    Static hardware-aware routing (no health checks).
    - Lovelace (Local): 2x 16GB VRAM (5060 Ti). Primary inference for all task models.
    - Turing (Secondary): 8GB VRAM (3070 Ti). Dedicated to safety + embeddings only.
    
    After model consolidation, qwen3.6:27b is the primary workhorse and always
    runs on Lovelace. Only safety and embedding models route to Turing.
    """
    # Turing models — async safety + embeddings (not latency-critical)
    turing_models = ["llama-guard", "nomic-embed"]

    if any(m in model_name for m in turing_models):
        return SECONDARY_OLLAMA_HOST
    # Everything else goes to Lovelace (fast CPU, dual 5060 Ti)
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

    Instead of routing every worker to the single "best" host (which causes
    them to queue internally on one GPU), this distributes successive worker
    requests across all *healthy* Ollama endpoints — OLLAMA_HOST (Turing) and
    SECONDARY_OLLAMA_HOST (Lovelace) — so multiple workers can run in true
    GPU-level parallel.
    """
    candidates = [OLLAMA_HOST]
    if SECONDARY_OLLAMA_HOST and SECONDARY_OLLAMA_HOST != OLLAMA_HOST:
        candidates.append(SECONDARY_OLLAMA_HOST)

    if len(candidates) == 1:
        logger.debug(f"[GPU Round-Robin] Only one host available; using {candidates[0]}.")
        return candidates[0]

    # Filter to healthy hosts; fall back to all candidates if health check fails
    try:
        from inference.node_health import get_node_monitor
        monitor = get_node_monitor()
        healthy = [h for h in candidates if monitor.is_healthy(h)]
    except Exception:
        healthy = []

    pool = healthy if healthy else candidates

    with _swarm_rr_lock:
        idx = next(_swarm_rr_counter)
        host = pool[idx % len(pool)]

    logger.info(f"[GPU Round-Robin] Worker slot {idx}: '{model_name}' → {host} ({len(pool)} hosts in pool).")
    return host


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
    """Sends a request to ComfyUI to completely dump its VRAM (models)."""
    try:
        logger.info("[GPU Queue] Sending /free request to ComfyUI to evict VRAM...")
        response = requests.post(f"{COMFYUI_HOST}/free", timeout=5)
        if response.status_code == 200:
            logger.info("[GPU Queue] ComfyUI VRAM evicted successfully.")
        else:
            logger.warning(f"[GPU Queue] ComfyUI /free endpoint returned status {response.status_code}.")
    except Exception as e:
        logger.warning(f"[GPU Queue] Failed to evict ComfyUI VRAM: {e}")

def evict_ollama():
    """Unloads active models from Ollama by sending a generation request with keep_alive=0"""
    try:
        logger.info("[GPU Queue] Evicting Ollama models from VRAM...")
        ps_resp = requests.get(f"{OLLAMA_HOST}/api/ps", timeout=5)
        if ps_resp.status_code == 200:
            models = ps_resp.json().get("models", [])
            if not models:
                logger.info("[GPU Queue] No active models in Ollama to evict.")
                return
            for model in models:
                model_name = model.get("name")
                logger.info(f"[GPU Queue] Unloading model: {model_name}")
                requests.post(f"{OLLAMA_HOST}/api/generate", json={
                    "model": model_name,
                    "keep_alive": 0
                }, timeout=5)
            logger.info("[GPU Queue] Ollama VRAM evicted successfully.")
    except Exception as e:
        logger.warning(f"[GPU Queue] Failed to evict Ollama VRAM: {e}")

@contextmanager
def request_lock(context: str, timeout: int = 300):
    """
    Acquires a global Mutex lock for the GPU and handles VRAM eviction for context switching.
    context must be either "text" or "image".
    Fail-open: if Redis is unavailable, skip the lock and run without GPU mutex.
    """
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
    try:
        # Spin loop until lock is acquired or timeout
        while time.time() - start_time < timeout:
            # nx=True ensures that the key is only set if it does not already exist
            # ex=timeout ensures the lock expires even if the process crashes
            if client.set(LOCK_KEY, lock_id, nx=True, ex=timeout):
                acquired = True
                logger.info(f"[GPU Queue] Lock acquired for context: '{context}'.")
                break
            time.sleep(1)
        
        if not acquired:
            raise TimeoutError("[GPU Queue] Failed to acquire GPU lock within timeout.")

        # Smart Context Switching
        current_zone = client.get(ZONE_KEY)
        if current_zone != context:
            logger.info(f"[GPU Queue] Context switch detected: '{current_zone}' -> '{context}'. Prepping VRAM...")
            if context == "text":
                # Switching to text -> we need VRAM for coding models. Dump ComfyUI.
                evict_comfyui()
            elif context == "image":
                # Switching to image -> we need VRAM for Flux/Forge. Dump Ollama.
                evict_ollama()
            elif context == "training":
                # Training needs exclusive VRAM — evict everything
                evict_ollama()
                evict_comfyui()
            else:
                logger.warning(f"[GPU Queue] Unknown context '{context}'.")

            # Update the current zone
            client.set(ZONE_KEY, context)
        else:
            logger.info(f"[GPU Queue] GPU is already in '{context}' zone. No eviction needed.")

        # Yield back to the block doing the work
        yield

    finally:
        if acquired:
            # Only release if we actually hold the lock based on lock_id
            if client.get(LOCK_KEY) == lock_id:
                client.delete(LOCK_KEY)
                logger.info(f"[GPU Queue] Lock released for context: '{context}'.")


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
