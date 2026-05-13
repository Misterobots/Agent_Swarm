"""
Klein Inference Service — FLUX.2 Klein via HuggingFace Diffusers.

Exposes a minimal REST API so agent_runtime can call it the same way it
calls ComfyUI.  The model is kept warm in VRAM between jobs; call /evict
to fully unload weights (e.g. when switching back to a text-heavy session).
"""

import io
import os
import base64
import logging
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path

import torch
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Klein] %(message)s")
logger = logging.getLogger("KleinService")

KLEIN_MODEL_ID = os.getenv("KLEIN_MODEL_ID", "black-forest-labs/FLUX.2-klein-9B")
HF_TOKEN = os.getenv("HF_TOKEN", None)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
# Reserve 1 GB headroom per GPU so CUDA can allocate activation buffers
MAX_MEMORY = {
    0: os.getenv("KLEIN_GPU0_MEM", "15GiB"),
    1: os.getenv("KLEIN_GPU1_MEM", "15GiB"),
}

_pipeline = None


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return

    logger.info(f"Loading pipeline: {KLEIN_MODEL_ID}")
    t0 = time.time()

    # Try FLUX.2-specific class first; fall back to FluxPipeline if Diffusers
    # hasn't added a dedicated class yet for this model.
    try:
        from diffusers import Flux2Pipeline  # type: ignore
        cls = Flux2Pipeline
        logger.info("Using Flux2Pipeline")
    except ImportError:
        from diffusers import FluxPipeline
        cls = FluxPipeline
        logger.info("Flux2Pipeline not found — falling back to FluxPipeline")

    _pipeline = cls.from_pretrained(
        KLEIN_MODEL_ID,
        torch_dtype=torch.bfloat16,
        # "auto" fills GPU 0 first (3 GiB on this host), then GPU 1 (15 GiB).
        # GPU 0 has ~12 GB Windows host overhead; max_memory accounts for this.
        device_map="auto",
        max_memory=MAX_MEMORY,
        token=HF_TOKEN or None,
    )
    logger.info(f"Pipeline ready in {time.time() - t0:.1f}s")


def _unload_pipeline():
    global _pipeline
    if _pipeline is None:
        return
    logger.info("Evicting Klein model from VRAM...")
    del _pipeline
    _pipeline = None
    torch.cuda.empty_cache()
    logger.info("Klein VRAM freed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy load — the GPU lock in agent_runtime evicts Ollama before calling /warmup,
    # so we don't load here and risk CPU-offloading due to Ollama occupying VRAM.
    yield
    _unload_pipeline()


app = FastAPI(title="Klein Inference Service", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 4
    guidance_scale: float = 3.5
    seed: int = -1


class GenerateResponse(BaseModel):
    filename: str
    elapsed: float
    seed: int
    image_b64: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": KLEIN_MODEL_ID,
        "pipeline_loaded": _pipeline is not None,
        "cuda_devices": torch.cuda.device_count(),
    }


@app.post("/warmup")
def warmup():
    """Pre-load model weights into VRAM. Safe to call multiple times."""
    _load_pipeline()
    return {"status": "ready", "model": KLEIN_MODEL_ID}


@app.post("/evict")
def evict():
    """Fully unload model weights from VRAM (for context switches to text)."""
    _unload_pipeline()
    return {"status": "evicted"}


@app.post("/free")
def free_memory():
    """Clear CUDA activation cache without unloading model weights."""
    torch.cuda.empty_cache()
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    if _pipeline is None:
        logger.info("Pipeline not loaded — loading now (cold start)...")
        _load_pipeline()

    seed = req.seed if req.seed != -1 else random.randint(0, 2 ** 32 - 1)
    generator = torch.Generator(device="cuda").manual_seed(seed)

    logger.info(
        f"Generating | steps={req.steps} | {req.width}x{req.height} | "
        f"cfg={req.guidance_scale} | seed={seed} | prompt='{req.prompt[:80]}'"
    )
    t0 = time.time()

    result = _pipeline(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt or None,
        width=req.width,
        height=req.height,
        num_inference_steps=req.steps,
        guidance_scale=req.guidance_scale,
        generator=generator,
    )
    image = result.images[0]
    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.1f}s")

    # Persist to output dir (shared volume with agent_runtime)
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"klein_{int(time.time())}_{seed}.png"
    filepath = Path(OUTPUT_DIR) / filename
    image.save(str(filepath))

    # Also return base64 so agent_runtime can grab it without a second HTTP call
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return GenerateResponse(
        filename=filename,
        elapsed=elapsed,
        seed=seed,
        image_b64=img_b64,
    )
