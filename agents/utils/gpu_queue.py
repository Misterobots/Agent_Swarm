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

def get_ollama_host(model_name: str) -> str:
    """
    Hardware-Aware Routing:
    - Justin-PC (Local): 16GB VRAM (5060 Ti). Essential for large models.
    - R730 (Secondary): 8GB VRAM (3070 Ti). Ideal for light models (<8GB).
    """
    # Models that MUST run on local 16GB card (Faster/More VRAM)
    heavy_models = ["qwen2.5-coder", "llama3.1:70b", "qwen3.5"]
    
    # Models that SHOULD run on remote 8GB card to save local VRAM
    light_models = ["nemotron-mini", "nemotron-orchestrator", "llama-guard3:8b", "qwen2.5:3b"]

    if any(m in model_name for m in heavy_models):
        logger.info(f"[GPU Queue] Routing HEAVY model '{model_name}' to Local Host (16GB VRAM).")
        return OLLAMA_HOST
        
    if any(m in model_name for m in light_models):
        logger.info(f"[GPU Queue] Offloading LIGHT model '{model_name}' to R730 (8GB VRAM).")
        return SECONDARY_OLLAMA_HOST
        
    return OLLAMA_HOST

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
