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

GPU layout (bf16 + CPU offload, ~16 GB peak)
--------------------------------------------
cuda:1 (Lovelace device_ids=['1']) — same physical GPU ComfyUI uses.
OmniGen2 has no native FP8; bf16 with `enable_model_cpu_offload()` achieves
equivalent "fits on a 5060 Ti" headroom at a small inference-speed cost.
OmniGen2 and Klein are mutually exclusive at the GPU layer; the request_lock
"compose" zone-switch evicts one before warming the other.
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

logger = logging.getLogger("omnigen_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
MODEL_ID = os.getenv("OMNIGEN_MODEL_ID", "OmniGen2/OmniGen2")
# OmniGen2's reference inference.py supports fp32 / fp16 / bf16. bf16 + CPU
# offload is the right combo for 16 GB GPUs (~17 GB at bf16 without offload).
DTYPE = os.getenv("OMNIGEN_DTYPE", "bf16")
DEVICE = os.getenv("OMNIGEN_DEVICE", "cuda:0")  # inside container, cuda:0 is the only visible GPU
USE_MODEL_CPU_OFFLOAD = os.getenv("OMNIGEN_CPU_OFFLOAD", "true").lower() in ("1", "true", "yes")

# OmniGen2 defaults from their reference scripts (NOT FLUX defaults)
DEFAULT_STEPS = int(os.getenv("OMNIGEN_DEFAULT_STEPS", "50"))
DEFAULT_TEXT_GUIDANCE = float(os.getenv("OMNIGEN_DEFAULT_TEXT_GUIDANCE", "5.0"))
DEFAULT_IMAGE_GUIDANCE = float(os.getenv("OMNIGEN_DEFAULT_IMAGE_GUIDANCE", "2.0"))
DEFAULT_MAX_SEQ_LEN = int(os.getenv("OMNIGEN_MAX_SEQ_LEN", "1024"))

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

_pipeline = None
_loaded_at: Optional[float] = None
_torch = None  # lazy import — keeps container start fast


def _dtype_obj():
    """Map env string to torch dtype object. Lazy import so container starts
    even if torch isn't installed (shouldn't happen, but defensive)."""
    global _torch
    if _torch is None:
        import torch as _t
        _torch = _t
    return {"fp32": _torch.float32, "fp16": _torch.float16, "bf16": _torch.bfloat16}[DTYPE]


def _load_pipeline() -> None:
    """Load OmniGen2 weights into VRAM. Idempotent."""
    global _pipeline, _loaded_at
    if _pipeline is not None:
        return

    logger.info(f"Loading OmniGen2 ({MODEL_ID}, dtype={DTYPE}, offload={USE_MODEL_CPU_OFFLOAD}) onto {DEVICE}...")
    t0 = time.time()

    from omnigen2.pipelines.omnigen2.pipeline_omnigen2 import OmniGen2Pipeline

    dtype = _dtype_obj()
    # NOTE: do NOT explicitly reload pipeline.transformer afterwards. The
    # OmniGen2 reference inference does this conditionally — but it doubles
    # peak RAM (~25 GB), exceeds WSL2's default 24 GB limit, and triggers a
    # class-mismatch warning between the remote-code-loaded transformer and
    # the local-clone version. The pipeline's from_pretrained already applies
    # torch_dtype to all components when trust_remote_code is on.
    _pipeline = OmniGen2Pipeline.from_pretrained(
        MODEL_ID, torch_dtype=dtype, trust_remote_code=True
    )

    if USE_MODEL_CPU_OFFLOAD:
        # Keeps most of the model on CPU, swaps modules to GPU as needed.
        # ~17 GB → ~10-12 GB peak GPU usage; ~20% slower inference vs full GPU.
        _pipeline.enable_model_cpu_offload(device=DEVICE)
    else:
        _pipeline = _pipeline.to(DEVICE)

    _loaded_at = time.time()
    logger.info(f"OmniGen2 loaded in {_loaded_at - t0:.1f}s")


def _unload_pipeline() -> None:
    """Drop weights from VRAM (for zone-switches)."""
    global _pipeline, _loaded_at
    if _pipeline is None:
        return
    logger.info("Unloading OmniGen2...")
    import gc
    del _pipeline
    _pipeline = None
    _loaded_at = None
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    except Exception as e:
        logger.warning(f"empty_cache failed (non-fatal): {e}")


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
    text_guidance_scale: float = DEFAULT_TEXT_GUIDANCE
    image_guidance_scale: float = DEFAULT_IMAGE_GUIDANCE
    max_sequence_length: int = DEFAULT_MAX_SEQ_LEN
    negative_prompt: str = ""
    seed: int = -1


class ComposeResponse(BaseModel):
    filename: str
    elapsed: float
    seed: int
    image_b64: str


class WarmupRequest(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_b64_image(b64: str):
    """Base64 → PIL.Image in RGB."""
    from PIL import Image
    raw = base64.b64decode(b64)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _build_instruction(scene_prompt: str, refs: list[ReferenceImage]) -> str:
    """OmniGen2 uses ordinal references ('image 1', 'image 2', ...) in the
    instruction text to bind input_images positionally. Build the final
    instruction by prefixing role context, then the scene prompt."""
    parts: list[str] = []
    for idx, ref in enumerate(refs, start=1):
        label = ref.name or ref.role
        if ref.role == "establishing_shot":
            parts.append(f"Image {idx} is the establishing shot of the scene.")
        elif ref.role == "character":
            parts.append(f"Image {idx} is {label}.")
        elif ref.role == "style":
            parts.append(f"Image {idx} is a style reference.")
    parts.append(scene_prompt)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

app = FastAPI(title="OmniGen2 Composition Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_ID if _pipeline is not None else None,
        "dtype": DTYPE,
        "cpu_offload": USE_MODEL_CPU_OFFLOAD,
        "pipeline_loaded": _pipeline is not None,
        "loaded_at": _loaded_at,
        "device": DEVICE,
    }


@app.post("/warmup")
def warmup(_req: WarmupRequest = None) -> dict:
    _load_pipeline()
    return {"status": "ready", "model": MODEL_ID, "dtype": DTYPE}


@app.post("/evict")
def evict() -> dict:
    _unload_pipeline()
    return {"status": "evicted"}


@app.post("/compose", response_model=ComposeResponse)
def compose(req: ComposeRequest) -> ComposeResponse:
    """Generate a composite from N reference images + scene prompt.

    Pattern A: caller provides an establishing-shot reference + per-character
    reference images. OmniGen2 places each character into the establishing
    scene preserving identity.
    """
    if _pipeline is None:
        _load_pipeline()

    char_refs = [r for r in req.reference_images if r.role == "character"]
    est_refs = [r for r in req.reference_images if r.role == "establishing_shot"]
    if not char_refs:
        raise HTTPException(400, "At least one character reference is required")
    if len(est_refs) > 1:
        raise HTTPException(400, "Only one establishing_shot reference is supported")

    import torch
    seed = req.seed if req.seed >= 0 else int(time.time() * 1000) & 0x7FFFFFFF
    generator = torch.Generator(device="cpu").manual_seed(seed)

    # Decode all references in the same order they're referenced in the instruction.
    input_images = [_decode_b64_image(r.image_b64) for r in req.reference_images]
    instruction = _build_instruction(req.scene_prompt, req.reference_images)
    logger.info(f"OmniGen2 compose: {len(input_images)} refs, instruction={instruction[:200]!r}")

    t0 = time.time()
    result = _pipeline(
        prompt=instruction,
        input_images=input_images,
        width=req.width,
        height=req.height,
        num_inference_steps=req.steps,
        max_sequence_length=req.max_sequence_length,
        text_guidance_scale=req.text_guidance_scale,
        image_guidance_scale=req.image_guidance_scale,
        negative_prompt=req.negative_prompt or None,
        num_images_per_prompt=1,
        generator=generator,
        output_type="pil",
    )
    elapsed = time.time() - t0

    # result.images is the standard diffusers output container.
    image = result.images[0]
    filename = f"omnigen_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    filepath = Path(OUTPUT_DIR) / filename
    image.save(str(filepath))

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    logger.info(f"Composed {filename} in {elapsed:.1f}s")
    return ComposeResponse(filename=filename, elapsed=elapsed, seed=seed, image_b64=img_b64)
