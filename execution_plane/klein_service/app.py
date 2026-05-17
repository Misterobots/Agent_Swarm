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

FLUX_FP8_REPO   = os.getenv("FLUX_FP8_REPO",  "Kijai/flux-fp8")
HF_TOKEN        = os.getenv("HF_TOKEN",        None)
OUTPUT_DIR      = os.getenv("OUTPUT_DIR",      "/output")
DEFAULT_VARIANT = os.getenv("KLEIN_DEFAULT_VARIANT", "schnell")

# Model variants supported by Klein. Both share the same architecture (FLUX
# transformer + dual text encoders + VAE) and the same FP8 patch — only the
# weights differ. The pipeline can hot-swap variants by unloading the current
# pipeline and reloading with a different model_id + transformer file.
#
#   schnell — distilled, 4 steps, no CFG. ~10s/image, fast iteration.
#   dev     — full quality, 20-30 steps, real CFG. ~30-45s/image, gated on HF.
VARIANTS = {
    "schnell": {
        "model_id": "black-forest-labs/FLUX.1-schnell",
        "fp8_file": "flux1-schnell-fp8-e4m3fn.safetensors",
        "transformer_config": "/app/schnell_transformer_config.json",
        "default_steps": 4,
        "default_guidance": 1.0,  # Schnell is distilled — CFG is ignored; 1.0 is a no-op
    },
    "dev": {
        "model_id": "black-forest-labs/FLUX.1-dev",
        "fp8_file": "flux1-dev-fp8-e4m3fn.safetensors",
        "transformer_config": "/app/dev_transformer_config.json",  # guidance_embeds: true
        "default_steps": 25,
        "default_guidance": 3.5,
    },
}

# Legacy env vars override the default variant's config when set (back-compat
# with single-variant deployments). KLEIN_MODEL_ID and FLUX_FP8_FILE take
# precedence over VARIANTS[DEFAULT_VARIANT].
_legacy_model_id = os.getenv("KLEIN_MODEL_ID")
_legacy_fp8_file = os.getenv("FLUX_FP8_FILE")
if _legacy_model_id:
    VARIANTS[DEFAULT_VARIANT]["model_id"] = _legacy_model_id
if _legacy_fp8_file:
    VARIANTS[DEFAULT_VARIANT]["fp8_file"] = _legacy_fp8_file

_pipeline = None
_current_variant = None  # which variant is currently loaded, or None if cold


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


def _load_pipeline(variant: str = None):
    """Load a variant's pipeline into VRAM. If a different variant is already
    loaded, this evicts it first (~10s) before loading the new one (~40s)."""
    global _pipeline, _current_variant

    target = variant or DEFAULT_VARIANT
    if target not in VARIANTS:
        raise ValueError(f"Unknown variant {target!r}; valid: {list(VARIANTS)}")

    # Already loaded with target variant — no-op
    if _pipeline is not None and _current_variant == target:
        logger.info(f"Variant {target!r} already loaded, no-op.")
        return

    # Different variant currently loaded — evict before switching
    if _pipeline is not None and _current_variant != target:
        logger.info(f"Variant switch: {_current_variant!r} → {target!r}. Unloading current pipeline.")
        _unload_pipeline()

    cfg = VARIANTS[target]
    model_id = cfg["model_id"]
    fp8_file = cfg["fp8_file"]

    t0 = time.time()
    transformer = None  # tracked for cleanup on failure

    from diffusers import FluxPipeline, FluxTransformer2DModel
    from huggingface_hub import hf_hub_download

    try:
        logger.info(f"Loading variant {target!r}: {model_id} + {FLUX_FP8_REPO}/{fp8_file}")
        logger.info(f"Downloading FP8 transformer: {FLUX_FP8_REPO}/{fp8_file} ...")
        fp8_path = hf_hub_download(
            repo_id=FLUX_FP8_REPO,
            filename=fp8_file,
            token=HF_TOKEN or None,
        )

        transformer_config = cfg["transformer_config"]
        logger.info(f"Loading FP8 transformer → cuda:1 (config: {transformer_config}) ...")
        transformer = FluxTransformer2DModel.from_single_file(
            fp8_path,
            config=transformer_config,
            torch_dtype=torch.float8_e4m3fn,
            token=HF_TOKEN or None,
        ).to("cuda:1")

        # FP8 weights cannot be multiplied directly with BF16 activations via F.linear.
        # Patch each FP8 linear layer to upcast weights to the input dtype on-the-fly.
        # Weights stay stored as FP8 in VRAM (~11.9 GB); only one layer's BF16 copy
        # is live at a time during the forward pass.
        _patch_fp8_linear(transformer)

        _log_vram()

        logger.info(f"Assembling FluxPipeline from {model_id} ...")
        _pipeline = FluxPipeline.from_pretrained(
            model_id,
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

        _current_variant = target
        logger.info(f"Pipeline ready ({target}) in {time.time() - t0:.1f}s")

    except Exception:
        # Release any partially-loaded tensors so CUDA memory is not permanently
        # locked on GPU 1. Without this, a failed warmup leaves ~14 GB stranded
        # and every subsequent warmup attempt also OOMs.
        logger.exception("Pipeline load failed — releasing partially-allocated VRAM")
        _pipeline = None
        _current_variant = None
        del transformer
        _force_free_vram()
        raise


def _unload_pipeline():
    global _pipeline, _current_variant
    if _pipeline is None:
        return
    logger.info(f"Evicting Klein {_current_variant!r} model from VRAM...")
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
    _current_variant = None
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
    width: int = 1024
    height: int = 1024
    steps: int = 4
    guidance_scale: float = 3.5
    seed: int = -1
    # If set, switches Klein to this variant before generating (~40s if cold-load
    # or variant-swap, ~10s if already loaded). Default: use whatever is loaded.
    variant: str | None = None
    # FLUX is flow-matching; negative prompts are not part of the model's training
    # signal and have no effect. Field accepted for backwards-compatible callers
    # but explicitly ignored at runtime. Use prompt phrasing to exclude unwanted
    # elements (e.g. "without text, without watermarks").
    negative_prompt: str | None = None


class WarmupRequest(BaseModel):
    # Pre-load this variant. If None, loads DEFAULT_VARIANT.
    variant: str | None = None


class GenerateResponse(BaseModel):
    filename: str
    elapsed: float
    seed: int
    image_b64: str
    variant: str  # which variant was used to generate this image


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    loaded_cfg = VARIANTS.get(_current_variant) if _current_variant else None
    return {
        "status": "ok",
        "model": loaded_cfg["model_id"] if loaded_cfg else None,
        "fp8_transformer": f"{FLUX_FP8_REPO}/{loaded_cfg['fp8_file']}" if loaded_cfg else None,
        "pipeline_loaded": _pipeline is not None,
        "loaded_variant": _current_variant,
        "available_variants": list(VARIANTS),
        "default_variant": DEFAULT_VARIANT,
        "cuda_devices": torch.cuda.device_count(),
    }


@app.post("/warmup")
def warmup(req: WarmupRequest = None):
    """Pre-load a variant's weights into VRAM. Safe to call multiple times.
    If a different variant is currently loaded, it gets evicted first."""
    target = (req.variant if req else None) or DEFAULT_VARIANT
    _load_pipeline(target)
    return {"status": "ready", "variant": _current_variant, "model": VARIANTS[_current_variant]["model_id"]}


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
    # If caller requested a specific variant that isn't currently loaded,
    # switch to it. This may cost ~40s (eviction + reload) but the caller
    # opted into the variant by setting it explicitly.
    if req.variant and req.variant != _current_variant:
        logger.info(f"Variant requested: {req.variant!r} (current: {_current_variant!r}) — switching")
        _load_pipeline(req.variant)
    elif _pipeline is None:
        logger.info("Pipeline not loaded — loading default variant (cold start)...")
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
        variant=_current_variant,
    )
