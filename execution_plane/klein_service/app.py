"""
Klein Inference Service — FLUX.1-schnell via Kijai FP8 transformer.

Exposes a minimal REST API so agent_runtime can call it the same way it
calls ComfyUI.  The model is kept warm in VRAM between jobs; call /evict
to fully unload weights (e.g. when switching back to a text-heavy session).

VRAM layout (2× RTX 5060 Ti 16 GB):
  cuda:0 — CLIP + T5-XXL text encoders (~9.7 GB bfloat16)
  cuda:1 — FP8 transformer (~8.6 GB) + VAE (~0.5 GB)
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

KLEIN_MODEL_ID = os.getenv("KLEIN_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
FLUX_FP8_REPO  = os.getenv("FLUX_FP8_REPO",  "Kijai/flux-fp8")
FLUX_FP8_FILE  = os.getenv("FLUX_FP8_FILE",  "flux1-schnell-fp8-e4m3fn.safetensors")
HF_TOKEN       = os.getenv("HF_TOKEN",        None)
OUTPUT_DIR     = os.getenv("OUTPUT_DIR",      "/output")

_pipeline = None


def _log_vram():
    for i in range(torch.cuda.device_count()):
        free, total = torch.cuda.mem_get_info(i)
        logger.info(f"  GPU {i}: used={(total-free)/1e9:.1f} GB  free={free/1e9:.1f} GB")


def _patch_fp8_linear(model):
    """Patch FP8-stored Linear and RMSNorm layers to upcast weights at runtime.

    Weights remain stored as float8_e4m3fn in VRAM (~11.9 GB); a per-layer BF16
    copy is created only during each forward call and immediately freed, so peak
    memory overhead is one layer's BF16 copy at a time.
    """
    import torch.nn as nn
    import torch.nn.functional as F
    linear_count = rms_count = 0
    for mod in model.modules():
        if isinstance(mod, nn.Linear) and mod.weight.dtype == torch.float8_e4m3fn:
            def _fwd_linear(x, m=mod):
                return F.linear(
                    x,
                    m.weight.to(x.dtype),
                    m.bias.to(x.dtype) if m.bias is not None else None,
                )
            mod.forward = _fwd_linear
            linear_count += 1
        elif isinstance(mod, nn.RMSNorm) and mod.weight.dtype == torch.float8_e4m3fn:
            def _fwd_rms(x, m=mod):
                return F.rms_norm(x, m.normalized_shape, m.weight.to(x.dtype), m.eps)
            mod.forward = _fwd_rms
            rms_count += 1
    logger.info(f"Patched {linear_count} FP8 Linear + {rms_count} FP8 RMSNorm layers for BF16 compute")


def _force_free_vram():
    """Force Python GC then empty the CUDA allocator cache on all devices.
    synchronize() before empty_cache() tells WDDM the device is idle so it
    can reclaim physical pages immediately rather than deferring reclaim."""
    import gc
    gc.collect()
    for i in range(torch.cuda.device_count()):
        with torch.cuda.device(i):
            torch.cuda.synchronize()
            torch.cuda.empty_cache()


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return

    t0 = time.time()
    transformer = None  # tracked for cleanup on failure

    from diffusers import FluxPipeline, FluxTransformer2DModel
    from huggingface_hub import hf_hub_download

    try:
        logger.info(f"Downloading FP8 transformer: {FLUX_FP8_REPO}/{FLUX_FP8_FILE} ...")
        fp8_path = hf_hub_download(
            repo_id=FLUX_FP8_REPO,
            filename=FLUX_FP8_FILE,
            token=HF_TOKEN or None,
        )

        logger.info("Loading FP8 transformer → cuda:1 ...")
        transformer = FluxTransformer2DModel.from_single_file(
            fp8_path,
            config="/app/schnell_transformer_config.json",
            torch_dtype=torch.float8_e4m3fn,
            token=HF_TOKEN or None,
        ).to("cuda:1")

        # FP8 weights cannot be multiplied directly with BF16 activations via F.linear.
        # Patch each FP8 linear layer to upcast weights to the input dtype on-the-fly.
        # Weights stay stored as FP8 in VRAM (~11.9 GB); only one layer's BF16 copy
        # is live at a time during the forward pass.
        _patch_fp8_linear(transformer)

        _log_vram()

        logger.info(f"Assembling FluxPipeline from {KLEIN_MODEL_ID} ...")
        _pipeline = FluxPipeline.from_pretrained(
            KLEIN_MODEL_ID,
            transformer=transformer,
            torch_dtype=torch.bfloat16,
            token=HF_TOKEN or None,
        )

        logger.info("Placing text encoders → cuda:0, VAE → cuda:1 ...")
        if getattr(_pipeline, "text_encoder", None) is not None:
            _pipeline.text_encoder = _pipeline.text_encoder.to("cuda:0")
        if getattr(_pipeline, "text_encoder_2", None) is not None:
            _pipeline.text_encoder_2 = _pipeline.text_encoder_2.to("cuda:0")
        if getattr(_pipeline, "vae", None) is not None:
            _pipeline.vae = _pipeline.vae.to("cuda:1")
        _log_vram()

        # diffusers sorts pipeline components alphabetically for device detection,
        # so text_encoder (cuda:0) is found first and _execution_device defaults to
        # cuda:0 — but the transformer and VAE live on cuda:1. Override at the
        # instance level so the pipeline creates latents and routes denoising on
        # cuda:1; text embeddings are automatically moved by the pipeline's .to()
        # calls before they reach the transformer.
        _original_cls = type(_pipeline)
        class _KleinFluxPipeline(_original_cls):
            @property
            def _execution_device(self):
                return torch.device("cuda:1")
        _pipeline.__class__ = _KleinFluxPipeline

        logger.info(f"Pipeline ready in {time.time() - t0:.1f}s")

    except Exception:
        # Release any partially-loaded tensors so CUDA memory is not permanently
        # locked on GPU 1. Without this, a failed warmup leaves ~14 GB stranded
        # and every subsequent warmup attempt also OOMs.
        logger.exception("Pipeline load failed — releasing partially-allocated VRAM")
        _pipeline = None
        del transformer
        _force_free_vram()
        raise


def _unload_pipeline():
    global _pipeline
    if _pipeline is None:
        return
    logger.info("Evicting Klein model from VRAM...")
    # Move all components to CPU synchronously before deleting the pipeline.
    # This immediately releases CUDA memory regardless of Python GC timing.
    # Without this, the FP8 forward patches create reference cycles
    # (mod → closure → mod via default arg) that prevent the transformer from
    # being freed by refcount alone — requiring gc.collect(), which may run
    # after Ollama has already decided to schedule on CPU.
    for attr in ("transformer", "text_encoder", "text_encoder_2", "vae"):
        comp = getattr(_pipeline, attr, None)
        if comp is not None:
            try:
                comp.to("cpu")
            except Exception:
                pass
    del _pipeline
    _pipeline = None
    _force_free_vram()
    logger.info("Klein VRAM freed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy load — the GPU lock in agent_runtime evicts Ollama before calling /warmup.
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
        "fp8_transformer": f"{FLUX_FP8_REPO}/{FLUX_FP8_FILE}",
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
    # CPU generator is safe when pipeline components span multiple GPUs.
    generator = torch.Generator("cpu").manual_seed(seed)

    logger.info(
        f"Generating | steps={req.steps} | {req.width}x{req.height} | "
        f"cfg={req.guidance_scale} | seed={seed} | prompt='{req.prompt[:80]}'"
    )
    t0 = time.time()

    # Text encoders live on cuda:0, transformer/VAE on cuda:1.
    # diffusers pipeline uses _execution_device (cuda:1) for latent creation, so
    # we pre-encode text on cuda:0 and move the embeddings to cuda:1 before
    # calling the pipeline — which then skips re-encoding and runs denoising
    # on cuda:1 with everything on the correct device.
    encoder_device = next(_pipeline.text_encoder.parameters()).device  # cuda:0
    transformer_device = next(_pipeline.transformer.parameters()).device  # cuda:1
    with torch.no_grad():
        prompt_embeds, pooled_prompt_embeds, _ = _pipeline.encode_prompt(
            prompt=req.prompt,
            prompt_2=None,
            device=encoder_device,
            num_images_per_prompt=1,
            max_sequence_length=512,
        )
    prompt_embeds = prompt_embeds.to(transformer_device)
    pooled_prompt_embeds = pooled_prompt_embeds.to(transformer_device)

    # FLUX uses flow-matching; negative_prompt is not supported.
    result = _pipeline(
        prompt=None,  # skip re-encoding; embeddings already provided
        prompt_embeds=prompt_embeds,
        pooled_prompt_embeds=pooled_prompt_embeds,
        width=req.width,
        height=req.height,
        num_inference_steps=req.steps,
        guidance_scale=req.guidance_scale,
        generator=generator,
    )
    image = result.images[0]
    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.1f}s")

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"klein_{int(time.time())}_{seed}.png"
    filepath = Path(OUTPUT_DIR) / filename
    image.save(str(filepath))

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return GenerateResponse(
        filename=filename,
        elapsed=elapsed,
        seed=seed,
        image_b64=img_b64,
    )
