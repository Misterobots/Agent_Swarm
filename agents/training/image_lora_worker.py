import json
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import TRAINING_DATASET_DIR, TRAINING_OUTPUT_DIR
from media_job_store import pop_image_training_run, update_image_training_run
from specialized.image_gen import list_available_models, resolve_generation_target
from workspace_paths import resolve_workspace_path


logger = logging.getLogger("ImageLoRAWorker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
RUNS_ROOT = Path(TRAINING_OUTPUT_DIR) / "image_lora"
DATASET_ROOT = Path(TRAINING_DATASET_DIR) / "image_lora"
REGISTRY_PATH = RUNS_ROOT / "adapter_registry.json"


def _load_sidecar(image_path: Path) -> dict:
    meta_path = image_path.with_name(image_path.name + ".json")
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        logger.warning("Failed to load sidecar for %s: %s", image_path, exc)
        return {}


def _iter_images(dataset_dir: Path, max_images: int):
    count = 0
    for candidate in sorted(dataset_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
            yield candidate
            count += 1
            if count >= max_images:
                break


def _caption_for_image(image_path: Path, sidecar: dict, trigger_word: str | None) -> str:
    prompt = sidecar.get("prompt") or image_path.stem.replace("_", " ")
    if trigger_word and trigger_word not in prompt:
        return f"{trigger_word}, {prompt}"
    return prompt


def _append_registry_record(record: dict):
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    if REGISTRY_PATH.exists():
        try:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            registry = []
    else:
        registry = []
    registry.append(record)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _prepare_dataset(run: dict) -> tuple[Path, list[dict], dict]:
    payload = run["payload"]
    dataset_dir = Path(resolve_workspace_path(payload["dataset_dir"]))
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    available_ckpts = list_available_models()
    resolved_target = resolve_generation_target(payload["base_profile"], available_ckpts)

    run_dataset_dir = DATASET_ROOT / run["run_id"]
    run_dataset_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dataset_dir / "dataset_manifest.jsonl"

    manifest_rows: list[dict] = []
    for image_path in _iter_images(dataset_dir, int(payload.get("max_images", 250))):
        sidecar = _load_sidecar(image_path)
        manifest_rows.append({
            "image_path": str(image_path),
            "caption": _caption_for_image(image_path, sidecar, payload.get("trigger_word")),
            "metadata": sidecar,
        })

    if not manifest_rows:
        raise RuntimeError(f"No images found in dataset directory: {dataset_dir}")

    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    plan = {
        "run_id": run["run_id"],
        "name": payload["name"],
        "base_profile": payload["base_profile"],
        "resolved_checkpoint": resolved_target["checkpoint"],
        "resolved_profile": resolved_target["profile_id"],
        "dataset_manifest": str(manifest_path),
        "output_dir": str(RUNS_ROOT / run["run_id"]),
        "trainer_mode": payload.get("trainer_mode", "plan-only"),
        "trigger_word": payload.get("trigger_word"),
        "learning_rate": payload.get("learning_rate", 1e-4),
        "steps": payload.get("steps", 1000),
        "max_images": payload.get("max_images", 250),
    }
    return manifest_path, manifest_rows, plan


def _run_optional_trainer(plan: dict) -> tuple[str, dict]:
    output_dir = Path(plan["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "training_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    trainer_template = os.getenv("IMAGE_LORA_TRAINER_COMMAND", "").strip()
    if not trainer_template:
        return (
            "planned",
            {
                "training_plan": str(plan_path),
                "message": "Training plan created. Set IMAGE_LORA_TRAINER_COMMAND to execute actual LoRA training.",
            },
        )

    command = trainer_template.format(
        dataset_manifest=plan["dataset_manifest"],
        output_dir=plan["output_dir"],
        base_checkpoint=plan["resolved_checkpoint"],
        trigger_word=plan.get("trigger_word") or "",
        steps=plan["steps"],
        learning_rate=plan["learning_rate"],
    )
    logger.info("Executing image LoRA trainer command: %s", command)
    completed = subprocess.run(command, shell=True, capture_output=True, text=True)

    artifacts = {
        "training_plan": str(plan_path),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(f"Image LoRA trainer failed with exit code {completed.returncode}: {completed.stderr[-400:]}" )

    adapter_candidates = sorted(output_dir.glob("*.safetensors"))
    if adapter_candidates:
        artifacts["adapter_path"] = str(adapter_candidates[0])
        _append_registry_record({
            "run_id": plan["run_id"],
            "name": plan["name"],
            "base_profile": plan["base_profile"],
            "resolved_checkpoint": plan["resolved_checkpoint"],
            "adapter_path": str(adapter_candidates[0]),
            "trigger_word": plan.get("trigger_word"),
            "created_at": time.time(),
        })
    return ("completed", artifacts)


def process_run(run: dict):
    run_id = run["run_id"]

    try:
        from utils.gpu_queue import request_lock as _gpu_lock
        _gpu_ctx = _gpu_lock("training", timeout=7200)
    except Exception:
        from contextlib import nullcontext
        _gpu_ctx = nullcontext()

    with _gpu_ctx:
        _process_run_inner(run)


def _process_run_inner(run: dict):
    run_id = run["run_id"]
    update_image_training_run(run_id, status="preparing", started_at=time.time())

    manifest_path, manifest_rows, plan = _prepare_dataset(run)
    update_image_training_run(
        run_id,
        status="dataset_ready",
        result=f"Prepared {len(manifest_rows)} image-caption pairs.",
        artifacts={"dataset_manifest": str(manifest_path)},
    )

    final_status, trainer_artifacts = _run_optional_trainer(plan)
    update_image_training_run(
        run_id,
        status=final_status,
        finished_at=time.time(),
        result=trainer_artifacts.get("message", f"Image LoRA run {final_status}."),
        artifacts={
            "dataset_manifest": str(manifest_path),
            **trainer_artifacts,
        },
    )


def main():
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info("Image LoRA worker started. Waiting for queued runs...")
    while True:
        run = pop_image_training_run(block_seconds=5)
        if not run:
            continue
        run_id = run.get("run_id", "unknown")
        try:
            logger.info("Processing image LoRA run %s", run_id)
            process_run(run)
        except Exception as exc:
            logger.exception("Image LoRA run failed: %s", run_id)
            update_image_training_run(
                run_id,
                status="error",
                finished_at=time.time(),
                result=str(exc),
            )


if __name__ == "__main__":
    main()