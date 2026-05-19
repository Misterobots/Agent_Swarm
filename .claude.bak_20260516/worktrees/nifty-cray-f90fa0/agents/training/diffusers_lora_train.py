#!/usr/bin/env python3
"""
agents/training/diffusers_lora_train.py

Minimal but functional LoRA fine-tuner for SD1.5 / SDXL using
Hugging Face diffusers + PEFT. Invoked by image_lora_worker.py
when IMAGE_LORA_TRAINER_COMMAND is set.

Template variables supplied by image_lora_worker:
  {dataset_manifest}   JSONL file with image_path + caption rows
  {output_dir}         Directory to write the adapter and plan
  {base_checkpoint}    Checkpoint filename (e.g. sd_xl_base_1.0_0.9vae.safetensors)
  {trigger_word}       Optional concept trigger token
  {steps}              Number of gradient steps
  {learning_rate}      AdamW learning rate

Example IMAGE_LORA_TRAINER_COMMAND:
  python /app/agents/training/diffusers_lora_train.py \
    --manifest {dataset_manifest} \
    --output_dir {output_dir} \
    --base_checkpoint {base_checkpoint} \
    --trigger_word {trigger_word} \
    --steps {steps} \
    --lr {learning_rate}
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("DiffusersLoRATrain")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Ensure required packages are present (fail-fast so the worker sees the error)
# ---------------------------------------------------------------------------
_REQUIRED = ["diffusers", "peft", "safetensors", "PIL", "torch", "transformers", "accelerate"]

def _ensure_packages():
    missing = []
    for pkg in ["diffusers", "peft", "safetensors", "Pillow", "torch", "transformers", "accelerate"]:
        imp_name = {
            "Pillow": "PIL",
            "safetensors": "safetensors",
        }.get(pkg, pkg)
        try:
            __import__(imp_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        logger.info("Installing missing packages: %s", missing)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )

_ensure_packages()

# ---------------------------------------------------------------------------
# Checkpoint → HuggingFace model ID mapping
# ---------------------------------------------------------------------------
CHECKPOINT_DIR = Path(
    os.getenv("COMFYUI_CHECKPOINT_DIR", "/home/runner/ComfyUI/models/checkpoints")
)

_HF_MODEL_MAP = [
    (["flux"],                                  None),            # not supported yet
    (["sd_xl", "sdxl", "xl_base"],             "stabilityai/stable-diffusion-xl-base-1.0"),
    (["xl_turbo", "turbo"],                    "stabilityai/sdxl-turbo"),
    (["v1-5", "v15", "1.5", "sd15", "pruned"], "runwayml/stable-diffusion-v1-5"),
]


def _resolve_base_model(checkpoint_filename: str) -> tuple[str, bool]:
    """
    Returns (model_id_or_path, is_xl).
    model_id_or_path is either a HuggingFace repo ID or a local safetensors path.
    """
    # Already a HuggingFace repo ID
    if "/" in checkpoint_filename and not checkpoint_filename.endswith(".safetensors"):
        is_xl = "xl" in checkpoint_filename.lower()
        return checkpoint_filename, is_xl

    lower = checkpoint_filename.lower()

    # Try to match to a known HF model
    for patterns, hf_id in _HF_MODEL_MAP:
        if any(p in lower for p in patterns):
            if hf_id is None:
                raise NotImplementedError(
                    f"Checkpoint '{checkpoint_filename}' maps to FLUX which is not "
                    "supported by this trainer. Set trainer_mode=plan-only or use an SDXL checkpoint."
                )
            is_xl = "xl" in hf_id.lower() or "sdxl" in lower
            # Prefer local file over HF download
            local = CHECKPOINT_DIR / checkpoint_filename
            if local.exists():
                logger.info("Using local checkpoint: %s", local)
                return str(local), is_xl
            return hf_id, is_xl

    # No pattern matched — fall back to SDXL as the default
    logger.warning(
        "Cannot map checkpoint '%s' to a known model. Defaulting to SDXL base.",
        checkpoint_filename,
    )
    local = CHECKPOINT_DIR / checkpoint_filename
    if local.exists():
        return str(local), True
    return "stabilityai/stable-diffusion-xl-base-1.0", True


# ---------------------------------------------------------------------------
# Pipeline loader
# ---------------------------------------------------------------------------

def _load_pipeline(base_model: str, is_xl: bool):
    import torch
    if is_xl:
        from diffusers import StableDiffusionXLPipeline
        if base_model.endswith(".safetensors") and Path(base_model).exists():
            logger.info("Loading SDXL from single .safetensors file: %s", base_model)
            return StableDiffusionXLPipeline.from_single_file(
                base_model, torch_dtype=torch.float16, use_safetensors=True
            )
        logger.info("Loading SDXL from HuggingFace: %s", base_model)
        return StableDiffusionXLPipeline.from_pretrained(
            base_model, torch_dtype=torch.float16
        )
    else:
        from diffusers import StableDiffusionPipeline
        if base_model.endswith(".safetensors") and Path(base_model).exists():
            logger.info("Loading SD1.5 from single .safetensors file: %s", base_model)
            return StableDiffusionPipeline.from_single_file(
                base_model, torch_dtype=torch.float16, use_safetensors=True
            )
        logger.info("Loading SD1.5 from HuggingFace: %s", base_model)
        return StableDiffusionPipeline.from_pretrained(
            base_model, torch_dtype=torch.float16
        )


# ---------------------------------------------------------------------------
# Image preprocessing — PIL only, no torchvision dependency
# ---------------------------------------------------------------------------

def _preprocess_image(image_path: str, width: int, height: int):
    """Load, resize, centre-crop, and return a float32 tensor (C, H, W) in [-1, 1]."""
    import torch
    from PIL import Image as _PIL

    img = _PIL.open(image_path).convert("RGB")
    # Resize shortest side to target, then centre-crop
    ratio = max(width / img.width, height / img.height)
    new_w = max(width, round(img.width * ratio))
    new_h = max(height, round(img.height * ratio))
    img = img.resize((new_w, new_h), _PIL.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))

    import numpy as _np
    arr = _np.array(img, dtype=_np.float32) / 127.5 - 1.0  # [0, 255] → [-1, 1]
    tensor = torch.from_numpy(arr).permute(2, 0, 1)  # HWC → CHW
    return tensor


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------

def train(args):
    import torch

    # 1. Load manifest
    rows: list[dict] = []
    with open(args.manifest, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        logger.error("Manifest is empty: %s", args.manifest)
        sys.exit(1)
    logger.info("Loaded %d image-caption pairs from manifest.", len(rows))

    # 2. Resolve base model
    base_model, is_xl = _resolve_base_model(args.base_checkpoint)
    logger.info("Base model resolved to '%s' (is_xl=%s)", base_model, is_xl)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Training device: %s", device)

    # 3. Load pipeline
    pipeline = _load_pipeline(base_model, is_xl)
    pipeline = pipeline.to(device)

    from diffusers import DDPMScheduler
    noise_scheduler = DDPMScheduler.from_config(pipeline.scheduler.config)

    # 4. Inject LoRA into the UNet
    from peft import LoraConfig, get_peft_model

    lora_config = LoraConfig(
        r=args.rank,
        lora_alpha=args.rank * 2,
        target_modules=["to_k", "to_q", "to_v", "to_out.0"],
        lora_dropout=0.05,
        bias="none",
    )
    pipeline.unet = get_peft_model(pipeline.unet, lora_config)
    pipeline.unet.train()
    pipeline.unet.enable_gradient_checkpointing()

    # Freeze everything else
    pipeline.vae.requires_grad_(False)
    pipeline.vae.eval()
    pipeline.text_encoder.requires_grad_(False)
    if hasattr(pipeline, "text_encoder_2"):
        pipeline.text_encoder_2.requires_grad_(False)

    trainable = sum(p.numel() for p in pipeline.unet.parameters() if p.requires_grad)
    logger.info("Trainable parameters: %s", f"{trainable:,}")

    # 5. Optimizer
    import torch.optim as optim
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, pipeline.unet.parameters()),
        lr=args.lr,
        weight_decay=1e-2,
    )

    # 6. Training loop
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    total = len(rows)
    log_interval = max(1, args.steps // 20)

    for step in range(args.steps):
        row = rows[step % total]
        image_path = row.get("image_path", "")
        caption = row.get("caption", "")

        try:
            pixel = _preprocess_image(image_path, args.width, args.height)
            pixel = pixel.unsqueeze(0).to(device).half()  # float16
        except Exception as exc:
            logger.warning("Skipping %s: %s", image_path, exc)
            continue

        # Encode image → latent
        with torch.no_grad():
            latent = pipeline.vae.encode(pixel).latent_dist.sample()
            latent = latent * pipeline.vae.config.scaling_factor

        # Add noise
        noise = torch.randn_like(latent)
        timesteps = torch.randint(
            0,
            noise_scheduler.config.num_train_timesteps,
            (latent.shape[0],),
            device=device,
        ).long()
        noisy_latent = noise_scheduler.add_noise(latent, noise, timesteps)

        # Encode caption
        with torch.no_grad():
            if is_xl:
                tok1 = pipeline.tokenizer(
                    caption,
                    return_tensors="pt",
                    padding="max_length",
                    max_length=77,
                    truncation=True,
                ).to(device)
                tok2 = pipeline.tokenizer_2(
                    caption,
                    return_tensors="pt",
                    padding="max_length",
                    max_length=77,
                    truncation=True,
                ).to(device)
                enc1 = pipeline.text_encoder(tok1.input_ids)[0]
                enc2_out = pipeline.text_encoder_2(tok2.input_ids, output_hidden_states=True)
                enc2 = enc2_out.hidden_states[-2]
                pooled = enc2_out[1]
                text_embeds = torch.cat([enc1, enc2], dim=-1)  # dim 2048 for SDXL
                add_time_ids = torch.tensor(
                    [[args.height, args.width, 0, 0, args.height, args.width]],
                    dtype=torch.float16, device=device,
                ).repeat(latent.shape[0], 1)
                unet_kwargs = {
                    "added_cond_kwargs": {
                        "text_embeds": pooled,
                        "time_ids": add_time_ids,
                    }
                }
            else:
                tok = pipeline.tokenizer(
                    caption,
                    return_tensors="pt",
                    padding="max_length",
                    max_length=77,
                    truncation=True,
                ).to(device)
                text_embeds = pipeline.text_encoder(tok.input_ids)[0]
                unet_kwargs = {}

        # Forward pass
        optimizer.zero_grad()
        noise_pred = pipeline.unet(
            noisy_latent, timesteps, encoder_hidden_states=text_embeds, **unet_kwargs
        ).sample
        loss = torch.nn.functional.mse_loss(
            noise_pred.float(), noise.float(), reduction="mean"
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(pipeline.unet.parameters(), 1.0)
        optimizer.step()

        if step % log_interval == 0:
            logger.info("Step %d/%d  loss=%.4f", step, args.steps, loss.item())

    # 7. Save adapter
    logger.info("Saving LoRA adapter to %s ...", args.output_dir)
    pipeline.unet.save_pretrained(args.output_dir)

    # Rename canonical adapter file so the worker registry check finds it
    peft_file = output_path / "adapter_model.safetensors"
    canonical = output_path / "lora_adapter.safetensors"
    if peft_file.exists() and not canonical.exists():
        shutil.copy(peft_file, canonical)
        logger.info("Canonical adapter: %s", canonical)

    logger.info("Training complete. %d steps, final loss=%.4f", args.steps, loss.item())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Minimal diffusers LoRA trainer")
    p.add_argument("--manifest",        required=True,           help="Path to JSONL dataset manifest")
    p.add_argument("--output_dir",      required=True,           help="Directory for adapter output")
    p.add_argument("--base_checkpoint", required=True,           help="Checkpoint filename or HF model ID")
    p.add_argument("--trigger_word",    default="",              help="Concept trigger token injected into captions")
    p.add_argument("--steps",           type=int,   default=250, help="Gradient steps")
    p.add_argument("--lr",              type=float, default=1e-4,help="AdamW learning rate")
    p.add_argument("--rank",            type=int,   default=16,  help="LoRA rank")
    p.add_argument("--width",           type=int,   default=1024,help="Training image width")
    p.add_argument("--height",          type=int,   default=1024,help="Training image height")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
