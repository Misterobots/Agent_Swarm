"""OmniGen2 Composition Service.

Takes a scene prompt + N reference character images (and optionally an
establishing-shot reference) and produces a single coherent composite image.

Mirrors klein_service's API shape so the GPU arbitration in gpu_queue.py can
swap between Klein and OmniGen on the same physical GPU.

Endpoints
---------
GET  /health   — readiness probe; reports pipeline_loaded, model, GPU.
POST /warmup   — preload weights into VRAM (idempotent).
POST /evict    — unload weights (used by gpu_queue zone-switches).
POST /compose  — generate a composite from refs + scene prompt.

GPU layout (FP8, ~12 GB)
------------------------
cuda:1 (Lovelace device_ids=['1']) — the same physical GPU ComfyUI uses.
OmniGen2 and Klein are mutually exclusive at the GPU layer; the request_lock
zone-switch must evict one before warming the other.

Status: scaffold. Model loading and inference are stubbed (NotImplementedError)
pending OmniGen2 FP8 weight selection + multi-image pipeline integration.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Diffusers / OmniGen2 imports are deferred to runtime — the container can
# start (and answer /health) even if the weights aren't downloaded yet.

logger = logging.getLogger("omnigen_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
MODEL_ID = os.getenv("OMNIGEN_MODEL_ID", "VectorSpaceLab/OmniGen2")
# FP8 quantized weights for 5060 Ti (16 GB). FP16 is ~24 GB → doesn't fit.
QUANTIZATION = os.getenv("OMNIGEN_QUANTIZATION", "fp8")
DEVICE = os.getenv("OMNIGEN_DEVICE", "cuda:0")  # inside the container, cuda:0 is the only visible GPU
DEFAULT_STEPS = int(os.getenv("OMNIGEN_DEFAULT_STEPS", "50"))
DEFAULT_GUIDANCE = float(os.getenv("OMNIGEN_DEFAULT_GUIDANCE", "3.0"))

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

_pipeline = None        # OmniGen2Pipeline instance once loaded
_loaded_at: Optional[float] = None


def _load_pipeline() -> None:
    """Load OmniGen2 weights into VRAM. Idempotent."""
    global _pipeline, _loaded_at
    if _pipeline is not None:
        return

    logger.info(f"Loading OmniGen2 ({MODEL_ID}, quantization={QUANTIZATION}) onto {DEVICE}...")
    t0 = time.time()

    # TODO: actual OmniGen2 pipeline load. Expected shape:
    #   from omnigen2 import OmniGen2Pipeline
    #   _pipeline = OmniGen2Pipeline.from_pretrained(
    #       MODEL_ID,
    #       torch_dtype=torch.float8_e4m3fn if QUANTIZATION == "fp8" else torch.bfloat16,
    #   ).to(DEVICE)
    # OmniGen2 may not yet ship FP8 weights officially; fall back to bfloat16
    # with CPU offload if VRAM is tight. Decision deferred until first build.
    raise NotImplementedError(
        "OmniGen2 pipeline load not yet implemented — wire up once FP8 weight "
        "format is confirmed. See https://github.com/VectorSpaceLab/OmniGen2."
    )

    _loaded_at = time.time()
    logger.info(f"OmniGen2 loaded in {_loaded_at - t0:.1f}s")


def _unload_pipeline() -> None:
    """Drop weights from VRAM (for zone-switches)."""
    global _pipeline, _loaded_at
    if _pipeline is None:
        return
    logger.info("Unloading OmniGen2...")
    # TODO: actual unload — del weights, torch.cuda.empty_cache(), gc.collect()
    _pipeline = None
    _loaded_at = None


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ReferenceImage(BaseModel):
    role: str = Field(..., description="One of: 'character', 'establishing_shot', 'style'")
    name: Optional[str] = Field(None, description="Human-readable label (e.g. 'Decker Allie Voss')")
    image_b64: str = Field(..., description="Base64-encoded PNG/JPEG bytes")


class ComposeRequest(BaseModel):
    scene_prompt: str
    reference_images: list[ReferenceImage]
    width: int = 1024
    height: int = 1024
    steps: int = DEFAULT_STEPS
    guidance_scale: float = DEFAULT_GUIDANCE
    seed: int = -1


class ComposeResponse(BaseModel):
    filename: str
    elapsed: float
    seed: int
    image_b64: str


class WarmupRequest(BaseModel):
    pass  # OmniGen2 has only one variant; nothing to pick


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

app = FastAPI(title="OmniGen2 Composition Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Readiness probe. gpu_queue's _omnigen_is_healthy() consumes this."""
    return {
        "status": "ok",
        "model": MODEL_ID if _pipeline is not None else None,
        "quantization": QUANTIZATION,
        "pipeline_loaded": _pipeline is not None,
        "loaded_at": _loaded_at,
        "device": DEVICE,
    }


@app.post("/warmup")
def warmup(_req: WarmupRequest = None) -> dict:
    """Pre-load weights into VRAM. Safe to call repeatedly."""
    _load_pipeline()
    return {"status": "ready", "model": MODEL_ID}


@app.post("/evict")
def evict() -> dict:
    """Unload weights from VRAM (gpu_queue zone-switch path)."""
    _unload_pipeline()
    return {"status": "evicted"}


@app.post("/compose", response_model=ComposeResponse)
def compose(req: ComposeRequest) -> ComposeResponse:
    """Generate a composite from N reference images + scene prompt.

    Pattern A (per design discussion): caller provides an establishing-shot
    reference + per-character reference images. OmniGen2 places each character
    into the establishing scene preserving identity.
    """
    if _pipeline is None:
        _load_pipeline()

    # Validate roles
    char_refs = [r for r in req.reference_images if r.role == "character"]
    est_refs = [r for r in req.reference_images if r.role == "establishing_shot"]
    if not char_refs:
        raise HTTPException(400, "At least one character reference is required")
    if len(est_refs) > 1:
        raise HTTPException(400, "Only one establishing_shot reference is supported")

    t0 = time.time()

    # TODO: decode b64 → PIL.Image list, build OmniGen2 multi-image input,
    # call _pipeline(...), save output, return.
    raise NotImplementedError(
        "Compose pipeline not yet wired — pending OmniGen2 multi-image input "
        "API confirmation and pipeline load implementation."
    )

    elapsed = time.time() - t0
    filename = f"omnigen_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    return ComposeResponse(
        filename=filename, elapsed=elapsed, seed=req.seed, image_b64="..."
    )
