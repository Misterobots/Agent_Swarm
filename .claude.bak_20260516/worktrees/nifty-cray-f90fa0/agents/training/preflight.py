"""
Training pre-flight checker.

Run this before any training job to ensure the environment is ready.
Checks:
  1. VRAM headroom >= minimum required (default 20 GB for 27B QLoRA)
  2. HF_TOKEN is set and non-empty
  3. Training window is active (2-6 AM local time) or FORCE_TRAIN=1
  4. Inference model is unloaded from Lovelace Ollama (to free VRAM)
  5. Base model is accessible on HuggingFace

Usage:
    python -m training.preflight                        # check only
    python -m training.preflight --evict-inference      # check + unload inference model first
    python -m training.preflight --force                # bypass time-window check
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    TRAINING_WINDOW_START,
    TRAINING_WINDOW_END,
    TRAINING_BASE_SOLVER,
    LOVELACE_IP,
)

logger = logging.getLogger("training.preflight")

# Minimum free VRAM (GB) required before starting a training job
MIN_VRAM_GB = float(os.getenv("TRAINING_MIN_VRAM_GB", "20.0"))

# Lovelace Ollama endpoint (accessible from agent_runtime over LAN)
LOVELACE_OLLAMA = os.getenv("SECONDARY_OLLAMA_HOST", f"http://{LOVELACE_IP}:11434")


@dataclass
class PreflightResult:
    ok: bool
    reason: str
    details: dict

    def __str__(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"[{status}] {self.reason}"


def _check_training_window(force: bool = False) -> PreflightResult:
    """Verify we are inside the configured training window."""
    if force or os.getenv("FORCE_TRAIN", "0") in ("1", "true", "yes"):
        return PreflightResult(ok=True, reason="Training window bypassed (FORCE_TRAIN=1)", details={})

    now = datetime.now()
    hour = now.hour
    start = TRAINING_WINDOW_START
    end = TRAINING_WINDOW_END

    # Handle overnight windows (e.g., 22-6)
    if start <= end:
        in_window = start <= hour < end
    else:
        in_window = hour >= start or hour < end

    if in_window:
        return PreflightResult(
            ok=True,
            reason=f"In training window ({start}:00–{end}:00, current {hour}:00)",
            details={"hour": hour, "window_start": start, "window_end": end},
        )
    return PreflightResult(
        ok=False,
        reason=f"Outside training window ({start}:00–{end}:00, current {hour}:00). Set FORCE_TRAIN=1 to override.",
        details={"hour": hour, "window_start": start, "window_end": end},
    )


def _check_hf_token() -> PreflightResult:
    """Verify HF_TOKEN is set."""
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        return PreflightResult(ok=True, reason="HF_TOKEN is set", details={"token_prefix": token[:8] + "..."})
    return PreflightResult(
        ok=False,
        reason="HF_TOKEN is not set. Required to download Qwen/Qwen3.6-27B from HuggingFace.",
        details={},
    )


def _get_ollama_loaded_vram_gb() -> tuple[float, list[dict]]:
    """
    Query Lovelace Ollama /api/ps for models currently loaded in VRAM.
    Returns (total_vram_used_gb, list_of_loaded_models).
    """
    import urllib.request, json

    url = f"{LOVELACE_OLLAMA}/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        models = data.get("models", [])
        total_vram = sum(m.get("size_vram", 0) for m in models) / (1024 ** 3)
        return total_vram, models
    except Exception as e:
        logger.warning(f"Could not query Ollama /api/ps at {url}: {e}")
        return 0.0, []


def _get_total_vram_gb() -> float:
    """
    Try nvidia-smi or torch to get total GPU VRAM.
    Falls back to querying Ollama (can't directly measure free VRAM from within).
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            values = [int(x.strip()) for x in result.stdout.strip().split("\n") if x.strip()]
            return sum(values) / 1024  # MiB → GiB
    except Exception:
        pass

    try:
        import torch
        total = sum(torch.cuda.get_device_properties(i).total_memory
                    for i in range(torch.cuda.device_count()))
        return total / (1024 ** 3)
    except Exception:
        pass

    # Fallback: assume Lovelace's known 32 GB
    return 32.0


def _check_vram(min_gb: float = MIN_VRAM_GB) -> PreflightResult:
    """
    Estimate available VRAM on Lovelace.
    Total VRAM minus models currently loaded in Ollama must be >= min_gb.
    """
    total_gb = _get_total_vram_gb()
    used_gb, loaded_models = _get_ollama_loaded_vram_gb()
    free_gb = total_gb - used_gb

    loaded_names = [m.get("name", "unknown") for m in loaded_models]
    details = {
        "total_vram_gb": round(total_gb, 1),
        "ollama_used_gb": round(used_gb, 1),
        "estimated_free_gb": round(free_gb, 1),
        "loaded_models": loaded_names,
        "minimum_required_gb": min_gb,
    }

    if free_gb >= min_gb:
        return PreflightResult(
            ok=True,
            reason=f"VRAM OK: {free_gb:.1f} GB free (need {min_gb} GB)",
            details=details,
        )
    return PreflightResult(
        ok=False,
        reason=(
            f"Insufficient VRAM: {free_gb:.1f} GB free, need {min_gb} GB. "
            f"Loaded: {loaded_names}. Run with --evict-inference to unload."
        ),
        details=details,
    )


def _evict_inference_model() -> PreflightResult:
    """
    Send keep_alive=0 to Lovelace Ollama for all currently loaded models
    to free VRAM before training.
    """
    import urllib.request, json

    _, loaded_models = _get_ollama_loaded_vram_gb()
    if not loaded_models:
        return PreflightResult(ok=True, reason="No models loaded in Ollama — nothing to evict", details={})

    evicted = []
    failed = []
    for m in loaded_models:
        name = m.get("name", "")
        if not name:
            continue
        try:
            payload = json.dumps({"model": name, "keep_alive": 0}).encode()
            req = urllib.request.Request(
                f"{LOVELACE_OLLAMA}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            evicted.append(name)
            logger.info(f"[Preflight] Evicted {name} from Ollama VRAM")
        except Exception as e:
            failed.append(name)
            logger.warning(f"[Preflight] Failed to evict {name}: {e}")

    # Wait a moment for VRAM to be released
    if evicted:
        time.sleep(3)

    if failed:
        return PreflightResult(
            ok=False,
            reason=f"Failed to evict: {failed}",
            details={"evicted": evicted, "failed": failed},
        )
    return PreflightResult(
        ok=True,
        reason=f"Evicted {len(evicted)} model(s): {evicted}",
        details={"evicted": evicted},
    )


def _check_base_model_accessible(model_id: str) -> PreflightResult:
    """
    Verify the HuggingFace model is accessible (cached locally or reachable).
    Checks HF cache first, then a lightweight HEAD request to the HF API.
    """
    # Check HF cache
    hf_cache = Path(os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface")))
    model_cache_name = model_id.replace("/", "--")
    # HF stores models as models--Org--ModelName
    cache_pattern = f"models--{model_cache_name}"
    cached_dirs = list(hf_cache.glob(f"hub/{cache_pattern}"))
    if cached_dirs:
        return PreflightResult(
            ok=True,
            reason=f"Base model '{model_id}' found in HF cache ({cached_dirs[0]})",
            details={"cached": True, "path": str(cached_dirs[0])},
        )

    # Not cached — check HF token and reachability
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        return PreflightResult(
            ok=False,
            reason=f"Base model '{model_id}' not cached and HF_TOKEN not set. First training run will need to download ~55 GB.",
            details={"cached": False},
        )

    import urllib.request
    url = f"https://huggingface.co/api/models/{model_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return PreflightResult(
                    ok=True,
                    reason=f"Base model '{model_id}' accessible on HuggingFace (not yet cached — first run will download ~55 GB)",
                    details={"cached": False, "hf_accessible": True},
                )
    except Exception as e:
        pass

    return PreflightResult(
        ok=False,
        reason=f"Base model '{model_id}' not cached and not accessible on HuggingFace. Check HF_TOKEN and network.",
        details={"cached": False, "hf_accessible": False},
    )


def run_preflight(
    force: bool = False,
    evict: bool = False,
    min_vram_gb: float = MIN_VRAM_GB,
    base_model: str = TRAINING_BASE_SOLVER,
) -> PreflightResult:
    """
    Run all preflight checks. Returns a combined PreflightResult.

    Args:
        force: Skip time-window check (same as FORCE_TRAIN=1)
        evict: Unload inference models from Ollama before checking VRAM
        min_vram_gb: Minimum free VRAM required in GB
        base_model: HuggingFace model ID to verify accessibility

    Returns:
        PreflightResult with ok=True only if all checks pass.
    """
    checks = []

    # 1. Time window
    checks.append(("time_window", _check_training_window(force)))

    # 2. HF token
    checks.append(("hf_token", _check_hf_token()))

    # 3. Evict inference model if requested (must happen before VRAM check)
    if evict:
        checks.append(("evict_inference", _evict_inference_model()))

    # 4. VRAM headroom
    checks.append(("vram", _check_vram(min_vram_gb)))

    # 5. Base model accessibility
    checks.append(("base_model", _check_base_model_accessible(base_model)))

    # Aggregate
    failures = [(name, r) for name, r in checks if not r.ok]
    all_details = {name: r.details for name, r in checks}

    if failures:
        failure_reasons = "; ".join(f"{n}: {r.reason}" for n, r in failures)
        return PreflightResult(
            ok=False,
            reason=f"Preflight failed ({len(failures)}/{len(checks)} checks): {failure_reasons}",
            details=all_details,
        )

    return PreflightResult(
        ok=True,
        reason=f"All {len(checks)} preflight checks passed",
        details=all_details,
    )


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Training pre-flight checker")
    parser.add_argument("--force", action="store_true", help="Bypass training window check")
    parser.add_argument("--evict-inference", action="store_true", dest="evict",
                        help="Unload inference models from Ollama before checking VRAM")
    parser.add_argument("--min-vram", type=float, default=MIN_VRAM_GB, dest="min_vram",
                        help=f"Minimum VRAM (GB) required (default {MIN_VRAM_GB})")
    parser.add_argument("--base-model", default=TRAINING_BASE_SOLVER, dest="base_model",
                        help=f"HuggingFace model ID to verify (default {TRAINING_BASE_SOLVER})")
    args = parser.parse_args()

    result = run_preflight(
        force=args.force,
        evict=args.evict,
        min_vram_gb=args.min_vram,
        base_model=args.base_model,
    )
    print(result)
    if not result.ok:
        import json
        for name, details in result.details.items():
            print(f"  {name}: {json.dumps(details)}")
        sys.exit(1)
    sys.exit(0)
