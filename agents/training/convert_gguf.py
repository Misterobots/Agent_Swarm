"""
LoRA merge → GGUF conversion → Ollama import pipeline.

Takes a QLoRA adapter from grpo_trainer, merges it into the base model,
converts to GGUF (Q4_K_M quantization), and creates an Ollama model.

Usage:
    python -m training.convert_gguf --adapter training_output/grpo_*/adapter
"""

import json
import os
import sys
import logging
import argparse
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    TRAINING_OUTPUT_DIR,
    TRAINING_BASE_SOLVER,
    TEMPLATE_DB_URL,
    OLLAMA_HOST,
)

logger = logging.getLogger("ConvertGGUF")

# llama.cpp convert script — expected to be cloned alongside the repo
LLAMA_CPP_DIR = os.getenv("LLAMA_CPP_DIR", "/opt/llama.cpp")
CONVERT_SCRIPT = os.path.join(LLAMA_CPP_DIR, "convert_hf_to_gguf.py")
QUANTIZE_BIN = os.path.join(LLAMA_CPP_DIR, "build", "bin", "llama-quantize")


def merge_lora(
    adapter_path: str,
    base_model: str = TRAINING_BASE_SOLVER,
    output_dir: Optional[str] = None,
) -> str:
    """
    Merge LoRA adapter weights into the base model.

    Returns path to the merged HuggingFace model directory.
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as e:
        raise RuntimeError(f"Missing dependencies: {e}. pip install torch transformers peft")

    if output_dir is None:
        output_dir = str(Path(adapter_path).parent / "merged")

    logger.info(f"Merging LoRA adapter into {base_model}...")

    # Load base model in float16 for merge
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="cpu",  # merge on CPU to save VRAM
        trust_remote_code=True,
    )

    # Load and merge LoRA
    model = PeftModel.from_pretrained(model, adapter_path)
    model = model.merge_and_unload()

    # Save merged model
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info(f"Merged model saved to {output_dir}")
    return output_dir


def convert_to_gguf(
    model_dir: str,
    output_path: Optional[str] = None,
    quantization: str = "Q4_K_M",
) -> str:
    """
    Convert a HuggingFace model to GGUF format using llama.cpp.

    Steps:
      1. convert_hf_to_gguf.py → F16 GGUF
      2. llama-quantize → Q4_K_M (or specified quant)

    Returns path to the quantized GGUF file.
    """
    model_dir = Path(model_dir)
    if output_path is None:
        output_path = str(model_dir.parent / f"model-{quantization}.gguf")

    f16_path = str(model_dir.parent / "model-f16.gguf")

    # Step 1: HF → F16 GGUF
    if not Path(CONVERT_SCRIPT).exists():
        raise FileNotFoundError(
            f"llama.cpp convert script not found at {CONVERT_SCRIPT}. "
            f"Set LLAMA_CPP_DIR env var or clone llama.cpp to {LLAMA_CPP_DIR}"
        )

    logger.info("Converting HF model to F16 GGUF...")
    result = subprocess.run(
        [sys.executable, CONVERT_SCRIPT, str(model_dir), "--outfile", f16_path, "--outtype", "f16"],
        capture_output=True,
        text=True,
        timeout=1800,  # 30min timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"GGUF conversion failed: {result.stderr}")
    logger.info(f"F16 GGUF written to {f16_path}")

    # Step 2: Quantize F16 → Q4_K_M
    if not Path(QUANTIZE_BIN).exists():
        # Try alternative location
        alt_quantize = shutil.which("llama-quantize")
        if alt_quantize:
            quantize_bin = alt_quantize
        else:
            raise FileNotFoundError(
                f"llama-quantize not found at {QUANTIZE_BIN}. "
                "Build llama.cpp or install it system-wide."
            )
    else:
        quantize_bin = QUANTIZE_BIN

    logger.info(f"Quantizing to {quantization}...")
    result = subprocess.run(
        [quantize_bin, f16_path, output_path, quantization],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Quantization failed: {result.stderr}")

    # Clean up F16 intermediate
    try:
        os.remove(f16_path)
    except OSError:
        pass

    gguf_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info(f"Quantized GGUF: {output_path} ({gguf_size_mb:.0f} MB)")
    return output_path


def create_ollama_model(
    gguf_path: str,
    model_name: str,
    system_prompt: Optional[str] = None,
    ollama_host: str = OLLAMA_HOST,
) -> str:
    """
    Import a GGUF model into Ollama.

    Creates a Modelfile and runs `ollama create`.
    Returns the Ollama model name.
    """
    import requests

    gguf_path = Path(gguf_path).resolve()
    modelfile_path = gguf_path.parent / "Modelfile"

    # Build Modelfile
    lines = [f'FROM {gguf_path}']

    if system_prompt:
        # Escape quotes in system prompt
        escaped = system_prompt.replace('"', '\\"')
        lines.append(f'SYSTEM "{escaped}"')

    # Reasonable defaults for inference
    lines.extend([
        'PARAMETER temperature 0.7',
        'PARAMETER top_p 0.9',
        'PARAMETER num_ctx 4096',
    ])

    modelfile_path.write_text("\n".join(lines))
    logger.info(f"Modelfile written to {modelfile_path}")

    # Create model via Ollama API
    logger.info(f"Creating Ollama model: {model_name}")
    resp = requests.post(
        f"{ollama_host}/api/create",
        json={"name": model_name, "modelfile": "\n".join(lines)},
        timeout=600,
        stream=True,
    )

    # Stream the creation progress
    for line in resp.iter_lines():
        if line:
            try:
                status = json.loads(line)
                if "status" in status:
                    logger.info(f"  Ollama: {status['status']}")
            except json.JSONDecodeError:
                pass

    if resp.status_code != 200:
        raise RuntimeError(f"Ollama create failed: HTTP {resp.status_code}")

    # Verify model exists
    list_resp = requests.get(f"{ollama_host}/api/tags", timeout=10)
    models = [m["name"] for m in list_resp.json().get("models", [])]
    if not any(model_name in m for m in models):
        raise RuntimeError(f"Model {model_name} not found after creation")

    logger.info(f"Ollama model '{model_name}' created successfully")
    return model_name


def _record_model_version(
    base_model: str,
    version_tag: str,
    adapter_path: str,
    gguf_path: Optional[str],
    ollama_model_name: Optional[str],
    training_run_id: Optional[int],
) -> Optional[int]:
    """Record model version in swarm.model_versions table."""
    try:
        import psycopg2

        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO swarm.model_versions
                (base_model, version_tag, adapter_path, gguf_path,
                 ollama_model_name, training_run_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'candidate')
            RETURNING id
            """,
            (base_model, version_tag, adapter_path, gguf_path,
             ollama_model_name, training_run_id),
        )
        version_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Recorded model version {version_id}: {version_tag}")
        return version_id
    except Exception as e:
        logger.warning(f"Failed to record model version: {e}")
        return None


def full_pipeline(
    adapter_path: str,
    base_model: str = TRAINING_BASE_SOLVER,
    model_name_prefix: str = "marsrl-solver",
    training_run_id: Optional[int] = None,
    quantization: str = "Q4_K_M",
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    End-to-end: LoRA merge → GGUF → Ollama import → DB record.

    Returns dict with merged_dir, gguf_path, ollama_name, version_id.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    version_tag = f"v{timestamp}"
    ollama_name = f"{model_name_prefix}:{version_tag}"

    # Record conversion run
    from training.grpo_trainer import _record_training_run, _update_training_run

    run_id = _record_training_run(
        run_type="conversion",
        target_model=base_model,
        dataset_path=adapter_path,
        dataset_size=0,
        status="running",
        config={"quantization": quantization, "ollama_name": ollama_name},
    )

    try:
        # Step 1: Merge LoRA
        merged_dir = merge_lora(adapter_path, base_model)

        # Step 2: Convert to GGUF
        gguf_path = convert_to_gguf(merged_dir, quantization=quantization)

        # Step 3: Import into Ollama
        ollama_name = create_ollama_model(gguf_path, ollama_name, system_prompt)

        # Step 4: Record in DB
        version_id = _record_model_version(
            base_model=base_model,
            version_tag=version_tag,
            adapter_path=adapter_path,
            gguf_path=gguf_path,
            ollama_model_name=ollama_name,
            training_run_id=training_run_id,
        )

        if run_id:
            _update_training_run(run_id, "completed", metrics={
                "gguf_size_mb": Path(gguf_path).stat().st_size / (1024 * 1024),
                "quantization": quantization,
            })

        # Update Prometheus
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="conversion", status="completed").inc()
        except Exception:
            pass

        # Clean up merged model to save disk (adapter + GGUF are the keepers)
        try:
            shutil.rmtree(merged_dir)
            logger.info(f"Cleaned up merged model dir: {merged_dir}")
        except OSError:
            pass

        return {
            "gguf_path": gguf_path,
            "ollama_name": ollama_name,
            "version_id": version_id,
            "version_tag": version_tag,
        }

    except Exception as e:
        logger.error(f"Conversion pipeline failed: {e}", exc_info=True)
        if run_id:
            _update_training_run(run_id, "failed", error=str(e))
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="conversion", status="failed").inc()
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description="LoRA → GGUF → Ollama pipeline")
    parser.add_argument("--adapter", "-a", required=True, help="Path to LoRA adapter directory")
    parser.add_argument("--base-model", default=TRAINING_BASE_SOLVER, help="HuggingFace model ID")
    parser.add_argument("--name", default="marsrl-solver", help="Ollama model name prefix")
    parser.add_argument("--quantization", "-q", default="Q4_K_M", help="GGUF quantization type")
    parser.add_argument("--run-id", type=int, help="Training run ID to link")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

    result = full_pipeline(
        adapter_path=args.adapter,
        base_model=args.base_model,
        model_name_prefix=args.name,
        training_run_id=args.run_id,
        quantization=args.quantization,
    )

    print(f"\nConversion complete!")
    print(f"  GGUF:   {result['gguf_path']}")
    print(f"  Ollama: {result['ollama_name']}")
    print(f"  DB ID:  {result.get('version_id', 'N/A')}")


if __name__ == "__main__":
    main()
