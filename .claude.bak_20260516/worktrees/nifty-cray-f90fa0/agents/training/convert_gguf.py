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


def _translate_path_for_ollama(host_path: str) -> str:
    """
    Translate agent_runtime's /workspace/training_output/... path
    to Ollama container's /training_output/... mount point.
    """
    host_path = str(host_path)
    if host_path.startswith("/workspace/training_output"):
        return host_path.replace("/workspace/training_output", "/training_output", 1)
    return host_path


def _dir_size_mb(path: str) -> float:
    """Get total size of a directory in MB."""
    total = 0
    p = Path(path)
    if p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    elif p.is_file():
        total = p.stat().st_size
    return total / (1024 * 1024)


def run_convert(
    training_run_id: int,
    base_model: str = TRAINING_BASE_SOLVER,
    system_prompt: Optional[str] = None,
    model_name_prefix: str = "marsrl-solver",
) -> Dict[str, Any]:
    """
    Convert a completed training run's adapter to an Ollama model.

    Steps:
      1. Look up adapter_path from training run metrics
      2. Merge LoRA into base model (timed)
      3. Try GGUF conversion; fall back to safetensors import if llama.cpp missing
      4. Create Ollama model (timed)
      5. Record model version in DB
      6. Return structured report dict

    Returns a detailed report dict.
    """
    import time
    from training.grpo_trainer import _record_training_run, _update_training_run

    report: Dict[str, Any] = {
        "source_run_id": training_run_id,
        "status": "running",
        "method": None,
        "warnings": [],
        "timing": {},
        "model": {},
        "ollama": {},
        "version": {},
        "error": None,
    }

    # Step 0: Look up the source training run
    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT metrics, target_model FROM swarm.training_runs WHERE id = %s",
            (training_run_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        report["status"] = "failed"
        report["error"] = f"Database lookup failed: {e}"
        return report

    if not row or not row[0]:
        report["status"] = "failed"
        report["error"] = f"Training run {training_run_id} not found or has no metrics"
        return report

    metrics = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    adapter_path = metrics.get("adapter_path")
    if not adapter_path:
        report["status"] = "failed"
        report["error"] = "No adapter_path in training run metrics"
        return report

    # Use the base_model from the training run if not overridden
    # Only accept HuggingFace-style IDs (contain '/'), not Ollama tags or placeholders
    db_model = row[1]
    if base_model == TRAINING_BASE_SOLVER and db_model and "/" in db_model and db_model not in ("pending", "unknown"):
        base_model = db_model

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    version_tag = f"v{timestamp}"
    ollama_name = f"{model_name_prefix}:{version_tag}"

    # Record conversion run in DB
    conv_run_id = _record_training_run(
        run_type="conversion",
        target_model=base_model,
        dataset_path=adapter_path,
        dataset_size=0,
        status="running",
        config={
            "source_run_id": training_run_id,
            "ollama_name": ollama_name,
            "system_prompt": system_prompt,
        },
    )

    total_start = time.time()

    try:
        # Check if Unsloth already exported a GGUF during training
        unsloth_gguf = metrics.get("gguf_path")
        if unsloth_gguf and os.path.isdir(unsloth_gguf):
            # Find the actual .gguf file in the directory
            gguf_files = [f for f in os.listdir(unsloth_gguf) if f.endswith(".gguf")]
            if gguf_files:
                gguf_path = os.path.join(unsloth_gguf, gguf_files[0])
                logger.info(f"[Convert] Using pre-built Unsloth GGUF: {gguf_path}")
                report["method"] = "unsloth_gguf"
                report["model"]["gguf_path"] = gguf_path
                report["model"]["gguf_size_mb"] = round(os.path.getsize(gguf_path) / (1024 * 1024), 1)
                report["timing"]["merge_sec"] = 0
                report["timing"]["convert_sec"] = 0
                import_path = gguf_path
            else:
                unsloth_gguf = None  # directory exists but no .gguf files

        if not unsloth_gguf or not import_path:
            # Fallback: traditional LoRA merge → GGUF pipeline
            # Step 1: Merge LoRA
            logger.info(f"[Convert] Step 1: Merging LoRA from {adapter_path}")
            merge_start = time.time()
            merged_dir = merge_lora(adapter_path, base_model)
            merge_sec = time.time() - merge_start
            report["timing"]["merge_sec"] = round(merge_sec, 1)
            report["model"]["merged_dir"] = merged_dir
            report["model"]["merged_size_mb"] = round(_dir_size_mb(merged_dir), 1)
            logger.info(f"[Convert] Merge complete in {merge_sec:.0f}s")

            # Step 2: Try GGUF conversion, fall back to safetensors
            convert_start = time.time()

            try:
                logger.info("[Convert] Step 2: Attempting GGUF conversion...")
                gguf_path = convert_to_gguf(merged_dir)
                report["method"] = "gguf"
                report["model"]["gguf_path"] = gguf_path
                report["model"]["gguf_size_mb"] = round(_dir_size_mb(gguf_path), 1)
                import_path = gguf_path
            except FileNotFoundError as e:
                logger.warning(f"[Convert] GGUF unavailable: {e}")
                report["method"] = "safetensors_direct"
                report["warnings"].append(
                    f"llama.cpp not installed — using Ollama safetensors import. "
                    f"This works but produces larger models. Install llama.cpp for Q4_K_M quantization."
                )
                import_path = merged_dir

            convert_sec = time.time() - convert_start
            report["timing"]["convert_sec"] = round(convert_sec, 1)

        # Step 3: Create Ollama model
        logger.info(f"[Convert] Step 3: Creating Ollama model {ollama_name}")
        ollama_start = time.time()

        # Translate path for Ollama container's volume mount
        ollama_import_path = _translate_path_for_ollama(str(import_path))
        logger.info(f"[Convert] Import path (Ollama view): {ollama_import_path}")

        # Build Modelfile content with translated path
        modelfile_lines = [f"FROM {ollama_import_path}"]
        if system_prompt:
            escaped = system_prompt.replace('"', '\\"')
            modelfile_lines.append(f'SYSTEM "{escaped}"')
        modelfile_lines.extend([
            "PARAMETER temperature 0.7",
            "PARAMETER top_p 0.9",
            "PARAMETER num_ctx 4096",
        ])

        import requests
        resp = requests.post(
            f"{OLLAMA_HOST}/api/create",
            json={"name": ollama_name, "modelfile": "\n".join(modelfile_lines)},
            timeout=600,
            stream=True,
        )
        ollama_status_messages = []
        for line in resp.iter_lines():
            if line:
                try:
                    status = json.loads(line)
                    if "status" in status:
                        ollama_status_messages.append(status["status"])
                        logger.info(f"  Ollama: {status['status']}")
                except json.JSONDecodeError:
                    pass
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama create failed: HTTP {resp.status_code}")

        # Verify model exists
        list_resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        models = [m["name"] for m in list_resp.json().get("models", [])]
        verified = any(ollama_name in m for m in models)

        ollama_sec = time.time() - ollama_start
        report["timing"]["ollama_import_sec"] = round(ollama_sec, 1)
        report["ollama"] = {
            "model_name": ollama_name,
            "host": OLLAMA_HOST,
            "verified": verified,
            "status_log": ollama_status_messages[-5:],  # last 5 status messages
        }

        if not verified:
            report["warnings"].append(
                f"Model {ollama_name} not found in Ollama after creation. "
                "The import may have silently failed."
            )

        # Step 4: Record model version
        version_id = _record_model_version(
            base_model=base_model,
            version_tag=version_tag,
            adapter_path=adapter_path,
            gguf_path=gguf_path,
            ollama_model_name=ollama_name,
            training_run_id=training_run_id,
        )
        report["version"] = {
            "id": version_id,
            "tag": version_tag,
            "status": "candidate",
        }

        # Total timing
        total_sec = time.time() - total_start
        report["timing"]["total_sec"] = round(total_sec, 1)
        report["status"] = "completed"

        # Update conversion run in DB
        if conv_run_id:
            _update_training_run(conv_run_id, "completed", metrics={
                "method": report["method"],
                "ollama_name": ollama_name,
                "total_sec": report["timing"]["total_sec"],
                "merge_sec": report["timing"]["merge_sec"],
                "verified": verified,
                "source_run_id": training_run_id,
                "version_id": version_id,
            })

        # Clean up merged dir (adapter + GGUF/Ollama are the keepers)
        merged_dir = report.get("model", {}).get("merged_dir")
        if merged_dir:
            try:
                shutil.rmtree(merged_dir)
                logger.info(f"Cleaned up merged model dir: {merged_dir}")
            except OSError:
                report["warnings"].append(f"Could not clean up merged dir: {merged_dir}")

        # Prometheus
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="conversion", status="completed").inc()
        except Exception:
            pass

        return report

    except Exception as e:
        total_sec = time.time() - total_start
        report["timing"]["total_sec"] = round(total_sec, 1)
        report["status"] = "failed"
        report["error"] = str(e)
        logger.error(f"[Convert] Failed: {e}", exc_info=True)

        if conv_run_id:
            _update_training_run(conv_run_id, "failed", error=str(e))
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="conversion", status="failed").inc()
        except Exception:
            pass

        return report


def run_deploy(
    training_run_id: int,
    template_id: str,
    traffic_split: float = 0.2,
    min_invocations: int = 100,
) -> Dict[str, Any]:
    """
    Start an A/B test for a converted model.

    Looks up the model version for the given training run, finds the
    template's current default_model as baseline, and starts the test.

    Returns a structured deploy report dict.
    """
    from training.ab_test import ABTestManager

    report: Dict[str, Any] = {
        "source_run_id": training_run_id,
        "status": "pending",
        "config": {},
        "test": {},
        "warnings": [],
        "error": None,
    }

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Find model version for this training run
        cur.execute(
            """
            SELECT id, ollama_model_name, version_tag, status
            FROM swarm.model_versions
            WHERE training_run_id = %s
            ORDER BY id DESC LIMIT 1
            """,
            (training_run_id,),
        )
        mv = cur.fetchone()
        if not mv:
            report["status"] = "failed"
            report["error"] = (
                f"No model version found for training run {training_run_id}. "
                "Run Convert first."
            )
            cur.close()
            conn.close()
            return report

        version_id, candidate_model, version_tag, mv_status = mv
        if not candidate_model:
            report["status"] = "failed"
            report["error"] = "Model version has no Ollama model name"
            cur.close()
            conn.close()
            return report

        # Get template's current default_model as baseline
        cur.execute(
            "SELECT default_model, intent FROM swarm.expertise_templates WHERE id = %s",
            (template_id,),
        )
        tmpl = cur.fetchone()
        if not tmpl:
            report["status"] = "failed"
            report["error"] = f"Template '{template_id}' not found"
            cur.close()
            conn.close()
            return report

        base_model, intent = tmpl
        cur.close()
        conn.close()

        if candidate_model == base_model:
            report["warnings"].append(
                "Candidate and baseline are the same model — test will not produce meaningful results"
            )

        # Start the A/B test
        mgr = ABTestManager()
        test_id = mgr.start_test(
            template_id=template_id,
            candidate_model=candidate_model,
            base_model=base_model,
            traffic_split=traffic_split,
            min_invocations=min_invocations,
        )

        # Update model version status to ab_testing
        try:
            conn2 = psycopg2.connect(TEMPLATE_DB_URL)
            cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE swarm.model_versions SET status = 'ab_testing' WHERE id = %s",
                (version_id,),
            )
            conn2.commit()
            cur2.close()
            conn2.close()
        except Exception as e:
            report["warnings"].append(f"Could not update model version status: {e}")

        report["status"] = "active"
        report["config"] = {
            "template_id": template_id,
            "template_intent": intent,
            "candidate_model": candidate_model,
            "base_model": base_model,
            "traffic_split": traffic_split,
            "min_invocations": min_invocations,
            "version_tag": version_tag,
        }
        report["test"] = {
            "id": test_id,
            "status": "active",
            "result_count": 0,
            "candidate_avg_score": None,
            "base_avg_score": None,
        }

        logger.info(
            f"[Deploy] A/B test {test_id} started: {candidate_model} vs {base_model} "
            f"on {template_id} ({traffic_split*100:.0f}% candidate)"
        )
        return report

    except ValueError as e:
        # ABTestManager raises ValueError if active test already exists
        report["status"] = "failed"
        report["error"] = str(e)
        return report
    except Exception as e:
        report["status"] = "failed"
        report["error"] = str(e)
        logger.error(f"[Deploy] Failed: {e}", exc_info=True)
        return report


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
