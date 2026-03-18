import os
import time
import requests
import logging
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

REDIS_HOST = os.getenv("REDIS_HOST", "redis_queue")  # Assuming redis_queue is the hostname in docker-compose
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")

def _get_preferred_host(model_name: str) -> str:
    """
    Static hardware-aware routing (no health checks).
    - Justin-PC (Local): 16GB VRAM (5060 Ti). Essential for large models.
    - R730 (Secondary): 8GB VRAM (3070 Ti). Ideal for light models (<8GB).
    """
    heavy_models = ["qwen2.5-coder", "llama3.1:70b", "qwen3.5"]
    light_models = ["nemotron-mini", "nemotron-orchestrator", "llama-guard3:8b", "qwen2.5:3b"]

    if any(m in model_name for m in heavy_models):
        return OLLAMA_HOST
    if any(m in model_name for m in light_models):
        return SECONDARY_OLLAMA_HOST
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

def get_redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

LOCK_KEY = "swarm_gpu_lock"
ZONE_KEY = "swarm_gpu_zone"  # Track whether VRAM is currently dedicated to "text" or "image"

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
    """
    client = get_redis_client()
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
