"""
Unsloth-accelerated GRPO training wrapper for MarsRL fine-tuning.

Uses Unsloth's FastLanguageModel with TRL's GRPOTrainer for
2x faster 4-bit QLoRA training with ~60% less VRAM.

Supports both Solver (Qwen2.5-Coder) and Router (Nemotron) models.

Training order:
  1. Solver (qwen2.5-coder) — code quality from MarsRL traces
  2. Router (nemotron-orchestrator) — routing accuracy via GRPO

Usage:
    python -m training.grpo_trainer --dataset training_data/grpo_traces.jsonl
    python -m training.grpo_trainer --dataset training_data/router_traces.jsonl --base-model nvidia/Nemotron-Mini-4B-Instruct
"""

import json
import os
import sys
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    TRAINING_OUTPUT_DIR,
    TRAINING_BASE_SOLVER,
    TRAINING_BASE_ROUTER,
    TRAINING_LORA_RANK,
    TRAINING_LORA_ALPHA,
    TRAINING_BATCH_SIZE,
    TRAINING_GRADIENT_ACCUMULATION,
    TRAINING_LEARNING_RATE,
    TRAINING_NUM_EPOCHS,
    TRAINING_MAX_SEQ_LEN,
    TEMPLATE_DB_URL,
)
from training.reward_function import MarsRewardFunction, RewardSignal

logger = logging.getLogger("GRPOTrainer")


def _has_tensorboard() -> bool:
    """Check if tensorboard is installed without importing it."""
    try:
        import importlib.util
        return importlib.util.find_spec("tensorboard") is not None
    except Exception:
        return False


class GRPOTrainingConfig:
    """Training hyperparameters — maps to config.py defaults."""

    def __init__(
        self,
        base_model: str = TRAINING_BASE_SOLVER,
        output_dir: str = TRAINING_OUTPUT_DIR,
        lora_rank: int = TRAINING_LORA_RANK,
        lora_alpha: int = TRAINING_LORA_ALPHA,
        batch_size: int = TRAINING_BATCH_SIZE,
        gradient_accumulation: int = TRAINING_GRADIENT_ACCUMULATION,
        learning_rate: float = TRAINING_LEARNING_RATE,
        num_epochs: int = TRAINING_NUM_EPOCHS,
        max_seq_len: int = TRAINING_MAX_SEQ_LEN,
        warmup_ratio: float = 0.1,
        group_size: int = 4,
        kl_coeff: float = 0.05,
        time_budget_minutes: Optional[float] = None,
    ):
        self.base_model = base_model
        self.output_dir = output_dir
        self.lora_rank = lora_rank
        self.lora_alpha = lora_alpha
        self.batch_size = batch_size
        self.gradient_accumulation = gradient_accumulation
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs
        self.max_seq_len = max_seq_len
        self.warmup_ratio = warmup_ratio
        self.group_size = group_size
        self.kl_coeff = kl_coeff
        self.time_budget_minutes = time_budget_minutes

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _load_dataset(path: str) -> List[dict]:
    """Load GRPO JSONL dataset."""
    trajectories = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trajectories.append(json.loads(line))
    logger.info(f"Loaded {len(trajectories)} trajectories from {path}")
    return trajectories


def _record_training_run(
    run_type: str,
    target_model: str,
    dataset_path: str,
    dataset_size: int,
    status: str,
    config: dict,
    metrics: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> Optional[int]:
    """Record training run in swarm.training_runs table."""
    try:
        import psycopg2

        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO swarm.training_runs
                (run_type, target_model, dataset_path, dataset_size,
                 status, config, metrics, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s IN ('completed','failed') THEN CURRENT_TIMESTAMP END)
            RETURNING id
            """,
            (
                run_type,
                target_model,
                dataset_path,
                dataset_size,
                status,
                json.dumps(config),
                json.dumps(metrics or {}),
                error_message,
                status,
            ),
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return run_id
    except Exception as e:
        logger.warning(f"Failed to record training run: {e}")
        return None


def _update_training_run(
    run_id: int, status: str, metrics: Optional[dict] = None, error: Optional[str] = None
):
    """Update a training run's status and metrics."""
    try:
        import psycopg2

        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Also update top-level columns if provided in metrics
        extra_sets = ""
        extra_params = []
        if metrics:
            if "dataset_size" in metrics and metrics["dataset_size"]:
                extra_sets += ", dataset_size = %s"
                extra_params.append(metrics["dataset_size"])
            if "dataset_path" in metrics and metrics["dataset_path"]:
                extra_sets += ", dataset_path = %s"
                extra_params.append(metrics["dataset_path"])
            if "target_model" in metrics and metrics["target_model"]:
                extra_sets += ", target_model = %s"
                extra_params.append(metrics["target_model"])

        cur.execute(
            f"""
            UPDATE swarm.training_runs
            SET status = %s,
                metrics = COALESCE(%s::jsonb, metrics),
                error_message = COALESCE(%s, error_message),
                completed_at = CASE WHEN %s IN ('completed','failed')
                               THEN CURRENT_TIMESTAMP ELSE completed_at END
                {extra_sets}
            WHERE id = %s
            """,
            [status, json.dumps(metrics) if metrics else None, error, status]
            + extra_params + [run_id],
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to update training run {run_id}: {e}")


def train_grpo(
    dataset_path: str,
    config: Optional[GRPOTrainingConfig] = None,
    existing_run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run QLoRA GRPO training on a JSONL dataset.

    Args:
        existing_run_id: If provided, reuse this DB row instead of creating
            a new one.  The caller (main.py) creates the row early so the
            run is visible in the history immediately.

    Returns dict with: adapter_path, metrics, run_id
    """
    if config is None:
        config = GRPOTrainingConfig()

    # Lazy imports — these are heavy and only needed on the Execution Node
    try:
        import torch
        from unsloth import FastLanguageModel
        from transformers import TrainerCallback
        from trl import GRPOConfig, GRPOTrainer

        class PrometheusTrainingCallback(TrainerCallback):
            """Push per-step training metrics to Prometheus gauges and heartbeat to DB."""

            def __init__(self, db_run_id: Optional[int] = None, heartbeat_every: int = 5):
                self._metrics = None
                self._db_run_id = db_run_id
                self._heartbeat_every = heartbeat_every
                self._last_logs: dict = {}

            def _load_metrics(self):
                if self._metrics is None:
                    try:
                        from metrics import (
                            TRAINING_IS_ACTIVE, TRAINING_STEP_CURRENT,
                            TRAINING_EPOCH_CURRENT, TRAINING_LOSS,
                            TRAINING_GRAD_NORM, TRAINING_LEARNING_RATE,
                            TRAINING_REWARD_MEAN, TRAINING_REWARD_STD,
                            TRAINING_COMPLETION_LEN_MEAN, TRAINING_COMPLETION_LEN_MIN,
                            TRAINING_COMPLETION_LEN_MAX, TRAINING_ENTROPY,
                            TRAINING_STEP_TIME, TRAINING_TOTAL_STEPS,
                            TRAINING_PHASE, PHASE_ORDINALS,
                        )
                        self._metrics = {
                            "active": TRAINING_IS_ACTIVE,
                            "step": TRAINING_STEP_CURRENT,
                            "epoch": TRAINING_EPOCH_CURRENT,
                            "loss": TRAINING_LOSS,
                            "grad_norm": TRAINING_GRAD_NORM,
                            "lr": TRAINING_LEARNING_RATE,
                            "reward_mean": TRAINING_REWARD_MEAN,
                            "reward_std": TRAINING_REWARD_STD,
                            "comp_mean": TRAINING_COMPLETION_LEN_MEAN,
                            "comp_min": TRAINING_COMPLETION_LEN_MIN,
                            "comp_max": TRAINING_COMPLETION_LEN_MAX,
                            "entropy": TRAINING_ENTROPY,
                            "step_time": TRAINING_STEP_TIME,
                            "total_steps": TRAINING_TOTAL_STEPS,
                            "phase": TRAINING_PHASE,
                        }
                        self._phase_ordinals = PHASE_ORDINALS
                    except ImportError:
                        logger.warning("Prometheus metrics not available for training callback")
                        self._metrics = {}
                        self._phase_ordinals = {}
                return self._metrics

            def on_train_begin(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("active"):
                    m["active"].set(1)
                if m.get("total_steps") and state.max_steps:
                    m["total_steps"].set(state.max_steps)
                if m.get("phase"):
                    m["phase"].set(self._phase_ordinals.get("training", 5))
                logger.info(
                    f"[PrometheusCallback] Training metrics active — "
                    f"max_steps={state.max_steps}"
                )
                # DB heartbeat: record total_steps at start
                if self._db_run_id and state.max_steps:
                    try:
                        _update_training_run(self._db_run_id, "running", metrics={
                            "phase": "training",
                            "total_steps": state.max_steps,
                        })
                    except Exception as hb_err:
                        logger.warning(f"[Heartbeat] on_train_begin DB update failed: {hb_err}")

            def on_log(self, args, state, control, logs=None, **kwargs):
                m = self._load_metrics()
                if not m or not logs:
                    return
                # Map TRL log keys to Prometheus gauges
                mapping = {
                    "loss": "loss",
                    "grad_norm": "grad_norm",
                    "learning_rate": "lr",
                    "reward": "reward_mean",
                    "reward_std": "reward_std",
                    "completions/mean_length": "comp_mean",
                    "completions/min_length": "comp_min",
                    "completions/max_length": "comp_max",
                    "entropy": "entropy",
                    "step_time": "step_time",
                    "epoch": "epoch",
                }
                for log_key, metric_key in mapping.items():
                    val = logs.get(log_key)
                    if val is not None and metric_key in m:
                        try:
                            m[metric_key].set(float(val))
                        except (TypeError, ValueError):
                            pass
                # Keep a copy of the latest logs for the heartbeat
                self._last_logs.update({k: v for k, v in logs.items() if v is not None})

            def on_step_end(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("step"):
                    m["step"].set(state.global_step)

                # DB heartbeat every N steps
                if (
                    self._db_run_id
                    and self._heartbeat_every > 0
                    and state.global_step % self._heartbeat_every == 0
                ):
                    try:
                        heartbeat = {
                            "phase": "training",
                            "current_step": state.global_step,
                            "total_steps": state.max_steps,
                            "current_epoch": round(state.epoch, 4) if state.epoch else None,
                            "loss": self._last_logs.get("loss"),
                            "reward_mean": self._last_logs.get("reward"),
                            "reward_std": self._last_logs.get("reward_std"),
                            "step_time_sec": self._last_logs.get("step_time"),
                            "learning_rate": self._last_logs.get("learning_rate"),
                        }
                        _update_training_run(
                            self._db_run_id, "running",
                            metrics={k: v for k, v in heartbeat.items() if v is not None},
                        )
                    except Exception as hb_err:
                        logger.warning(f"[Heartbeat] step {state.global_step} DB update failed: {hb_err}")

            def on_train_end(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("active"):
                    m["active"].set(0)
                if m.get("phase"):
                    m["phase"].set(self._phase_ordinals.get("completed", 7))
                logger.info("[PrometheusCallback] Training ended, metrics reset")

        class TimeBudgetCallback(TrainerCallback):
            """Stop training when wall-clock budget is exhausted."""

            def __init__(self, budget_seconds: float):
                self.budget_seconds = budget_seconds
                self.start_time: Optional[float] = None
                self._warned = False

            def on_train_begin(self, args, state, control, **kwargs):
                self.start_time = time.time()
                logger.info(f"[TimeBudget] Training window: {self.budget_seconds / 60:.1f} min")
                try:
                    from metrics import TRAINING_BUDGET_START
                    TRAINING_BUDGET_START.set(self.start_time)
                except Exception:
                    pass

            def on_step_end(self, args, state, control, **kwargs):
                if self.start_time is None:
                    return control
                elapsed = time.time() - self.start_time
                remaining = self.budget_seconds - elapsed
                if remaining <= 0:
                    logger.info(
                        f"[TimeBudget] Budget exhausted after {elapsed:.0f}s — stopping training."
                    )
                    control.should_training_stop = True
                elif remaining < 120 and not self._warned:
                    logger.info("[TimeBudget] <2 min remaining — wrapping up current step.")
                    self._warned = True
                return control
    except ImportError as e:
        raise RuntimeError(
            f"Training dependencies not installed: {e}. "
            "Run: pip install unsloth trl"
        )

    # Load dataset
    trajectories = _load_dataset(dataset_path)
    if not trajectories:
        raise ValueError(f"No trajectories found in {dataset_path}")

    # ── Attention backend diagnostic ──────────────────────────────────────────
    import torch as _torch
    _fa_version = "not installed"
    try:
        import flash_attn as _fa
        _fa_version = getattr(_fa, "__version__", "installed")
    except ImportError:
        pass
    _cc = _torch.cuda.get_device_capability() if _torch.cuda.is_available() else ("?", "?")
    _device = _torch.cuda.get_device_name(0) if _torch.cuda.is_available() else "cpu"
    logger.info(
        "[ATTN] flash-attn=%s | device=%s (sm_%s%s) | "
        "torch_flash_sdp=%s | torch_mem_eff_sdp=%s",
        _fa_version, _device, _cc[0], _cc[1],
        _torch.backends.cuda.flash_sdp_enabled(),
        _torch.backends.cuda.mem_efficient_sdp_enabled(),
    )
    if _fa_version == "not installed":
        logger.warning(
            "[ATTN] flash-attn not found — Unsloth will use SDPA (slower prefill). "
            "Rebuild the container to pick up the new flash-attn FA4 layer."
        )
    # ─────────────────────────────────────────────────────────────────────────

    reward_fn = MarsRewardFunction()

    # Record training run start (or reuse row created by main.py)
    if existing_run_id:
        run_id = existing_run_id
        # Update the early row with actual dataset details now that we know them
        _update_training_run(
            run_id, "running",
            metrics={"dataset_path": dataset_path, "dataset_size": len(trajectories),
                     "target_model": config.base_model},
        )
    else:
        run_id = _record_training_run(
            run_type="training",
            target_model=config.base_model,
            dataset_path=dataset_path,
            dataset_size=len(trajectories),
            status="running",
            config=config.to_dict(),
        )

    try:
        # Setup output directory
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(config.output_dir) / f"grpo_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write training_config.json so the filesystem catalog endpoint can read it
        training_config_data = {
            "run_id": str(run_dir.name),
            "base_model": config.base_model,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "num_epochs": config.num_epochs,
            "lora_rank": config.lora_rank,
            "lora_alpha": config.lora_alpha,
            "batch_size": config.batch_size,
            "dataset_path": dataset_path,
        }
        try:
            import json as _json
            (run_dir / "training_config.json").write_text(
                _json.dumps(training_config_data, indent=2)
            )
        except Exception as _cfg_err:
            logger.warning(
                "Failed to write training_config.json: %s",
                _cfg_err,
                exc_info=True,
            )

        # Unsloth handles quantization, model loading, and LoRA in one call
        logger.info(f"Loading base model via Unsloth: {config.base_model}")

        # Phase: model_loading — update DB and Prometheus
        if run_id:
            _update_training_run(run_id, "running", metrics={
                "phase": "model_loading",
                "target_model": config.base_model,
                "dataset_path": dataset_path,
                "dataset_size": len(trajectories),
            })
        try:
            from metrics import TRAINING_PHASE, TRAINING_RUN_ID, PHASE_ORDINALS
            TRAINING_PHASE.set(PHASE_ORDINALS.get("model_loading", 4))
            if run_id:
                TRAINING_RUN_ID.set(run_id)
        except Exception:
            pass

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=config.base_model,
            max_seq_length=config.max_seq_len,
            load_in_4bit=True,
            dtype=None,  # auto-detect (bf16 on Ampere+)
        )

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Unsloth LoRA — applied via FastLanguageModel.get_peft_model
        model = FastLanguageModel.get_peft_model(
            model,
            r=config.lora_rank,
            lora_alpha=config.lora_alpha,
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            bias="none",
            use_gradient_checkpointing="unsloth",  # 30% less VRAM
            random_state=42,
        )
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in model.parameters())
        logger.info(
            f"LoRA: {trainable_params:,} trainable / {total_params:,} total "
            f"({100 * trainable_params / total_params:.2f}%)"
        )

        # Prepare prompts and completions from trajectories
        prompts = []
        completions = []
        rewards_list = []

        for traj in trajectories:
            convs = traj.get("conversations", [])
            if len(convs) < 2:
                continue

            # Prompt = user message(s), completion = assistant response(s)
            prompt_parts = []
            completion_parts = []
            in_prompt = True

            for turn in convs:
                if turn["role"] == "user" and in_prompt:
                    prompt_parts.append(turn["content"])
                elif turn["role"] == "assistant":
                    in_prompt = False
                    completion_parts.append(turn["content"])
                elif turn["role"] == "tool":
                    completion_parts.append(f"[Tool: {turn.get('name', 'unknown')}]\n{turn['content']}")

            if prompt_parts and completion_parts:
                prompts.append("\n".join(prompt_parts))
                completions.append("\n".join(completion_parts))
                reward = reward_fn.reward_from_trajectory(traj)
                rewards_list.append(reward.composite)

        if not prompts:
            raise ValueError("No valid prompt-completion pairs extracted from dataset")

        logger.info(f"Prepared {len(prompts)} training examples")

        # When a time budget is set, save every 50 steps so partial progress
        # is preserved when the callback halts training mid-epoch.
        time_bounded = config.time_budget_minutes is not None
        save_strategy = "steps" if time_bounded else "epoch"
        save_steps = 50 if time_bounded else 500

        # GRPO training config
        training_args = GRPOConfig(
            output_dir=str(run_dir),
            num_train_epochs=config.num_epochs,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.gradient_accumulation,
            learning_rate=config.learning_rate,
            warmup_ratio=config.warmup_ratio,
            max_completion_length=config.max_seq_len,
            num_generations=config.group_size,
            logging_steps=1,
            save_strategy=save_strategy,
            save_steps=save_steps,
            bf16=True,
            gradient_checkpointing=False,  # Unsloth handles this internally
            report_to="tensorboard" if _has_tensorboard() else "none",
            logging_dir=str(run_dir / "tensorboard_logs"),
        )

        # Build reward function for GRPO — takes list of completions,
        # returns list of reward floats
        def reward_function(completions: list, **kwargs) -> list:
            """Score completions using MarsRL reward heuristics."""
            scores = []
            for completion in completions:
                text = completion if isinstance(completion, str) else str(completion)
                # Heuristic scoring for GRPO group comparison
                length_score = min(1.0, len(text) / 500)
                has_code = 1.0 if "```" in text or "def " in text or "function " in text else 0.5
                scores.append(length_score * 0.3 + has_code * 0.7)
            return scores

        # Create trainer
        # Note: GRPOTrainer expects a dataset with "prompt" column
        import datasets

        train_dataset = datasets.Dataset.from_dict({
            "prompt": prompts,
        })

        callbacks = []
        # Always add Prometheus callback for live metrics
        try:
            callbacks.append(PrometheusTrainingCallback(db_run_id=run_id, heartbeat_every=5))
        except Exception as e:
            logger.warning(f"Prometheus training callback unavailable: {e}")

        if time_bounded:
            budget_seconds = config.time_budget_minutes * 60
            callbacks.append(TimeBudgetCallback(budget_seconds))
            logger.info(
                f"[TimeBudget] Budget set: {config.time_budget_minutes:.1f} min "
                f"(timer starts after model load)"
            )
            # Set Prometheus budget gauges
            try:
                from metrics import TRAINING_TIME_BUDGET_SEC
                TRAINING_TIME_BUDGET_SEC.set(budget_seconds)
            except Exception:
                pass

        trainer = GRPOTrainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            reward_funcs=reward_function,
            processing_class=tokenizer,
            callbacks=callbacks if callbacks else None,
        )

        logger.info("Starting GRPO training...")
        train_result = trainer.train()

        # Save LoRA adapter
        # Phase: saving_adapter
        if run_id:
            _update_training_run(run_id, "running", metrics={"phase": "saving_adapter"})
        try:
            from metrics import TRAINING_PHASE, PHASE_ORDINALS
            TRAINING_PHASE.set(PHASE_ORDINALS.get("saving_adapter", 6))
        except Exception:
            pass

        adapter_path = str(run_dir / "adapter")
        model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)
        logger.info(f"LoRA adapter saved to {adapter_path}")

        # Also export merged GGUF directly via Unsloth (Q4_K_M)
        gguf_path = None
        try:
            gguf_dir = str(run_dir / "gguf")
            model.save_pretrained_gguf(
                gguf_dir,
                tokenizer,
                quantization_method="q4_k_m",
            )
            # Find the generated .gguf file
            from pathlib import Path as _P
            gguf_files = list(_P(gguf_dir).glob("*.gguf"))
            if gguf_files:
                gguf_path = str(gguf_files[0])
                logger.info(f"GGUF exported to {gguf_path}")
            else:
                logger.warning("Unsloth GGUF export produced no .gguf files")
        except Exception as gguf_err:
            logger.warning(f"GGUF export failed (adapter still saved): {gguf_err}")
            gguf_path = None

        # Collect metrics
        train_metrics = train_result.metrics or {}
        metrics = {
            "train_loss": train_result.training_loss,
            "train_runtime": train_metrics.get("train_runtime", 0),
            "train_samples_per_second": train_metrics.get("train_samples_per_second", 0),
            "train_steps_per_second": train_metrics.get("train_steps_per_second", 0),
            "total_steps": trainer.state.global_step if hasattr(trainer, 'state') else train_metrics.get("train_steps", 0),
            "train_samples": len(prompts),
            "trainable_params": trainable_params,
            "total_params": total_params,
            "trainable_pct": round(100 * trainable_params / total_params, 2) if total_params else 0,
            "lora_rank": config.lora_rank,
            "lora_alpha": config.lora_alpha,
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "gradient_accumulation": config.gradient_accumulation,
            "max_seq_len": config.max_seq_len,
            "num_epochs": config.num_epochs,
            "base_model": config.base_model,
            "time_budget_minutes": config.time_budget_minutes,
            "budget_limited": time_bounded,
            "adapter_path": adapter_path,
            "gguf_path": gguf_path,
            "run_dir": str(run_dir),
        }

        # Update training run record
        if run_id:
            _update_training_run(run_id, "completed", metrics=metrics)

        # Update Prometheus metrics
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="training", status="completed").inc()
        except Exception:
            pass

        return {
            "adapter_path": adapter_path,
            "gguf_path": gguf_path,
            "metrics": metrics,
            "run_id": run_id,
            "run_dir": str(run_dir),
        }

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        if run_id:
            _update_training_run(run_id, "failed", error=str(e))
        try:
            from metrics import TRAINING_RUNS_TOTAL, TRAINING_IS_ACTIVE, TRAINING_PHASE, PHASE_ORDINALS
            TRAINING_RUNS_TOTAL.labels(run_type="training", status="failed").inc()
            TRAINING_IS_ACTIVE.set(0)
            TRAINING_PHASE.set(PHASE_ORDINALS.get("failed", 8))
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description="Run Unsloth GRPO training")
    parser.add_argument("--dataset", "-d", required=True, help="Path to GRPO JSONL dataset")
    parser.add_argument("--base-model", default=TRAINING_BASE_SOLVER, help="HuggingFace model ID")
    parser.add_argument(
        "--target",
        choices=["solver", "router"],
        default="solver",
        help="Training target: solver (Qwen) or router (Nemotron)",
    )
    parser.add_argument("--output-dir", default=TRAINING_OUTPUT_DIR, help="Training output directory")
    parser.add_argument("--epochs", type=int, default=TRAINING_NUM_EPOCHS)
    parser.add_argument("--lora-rank", type=int, default=TRAINING_LORA_RANK)
    parser.add_argument("--lr", type=float, default=TRAINING_LEARNING_RATE)
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        metavar="MINUTES",
        help="Stop training after this many minutes (saves checkpoint every 50 steps)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

    # Select base model from target
    base_model = args.base_model
    if args.target == "router" and base_model == TRAINING_BASE_SOLVER:
        base_model = TRAINING_BASE_ROUTER
        logger.info(f"Router training — using base model: {base_model}")

    config = GRPOTrainingConfig(
        base_model=base_model,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        lora_rank=args.lora_rank,
        learning_rate=args.lr,
        time_budget_minutes=args.time_budget,
    )

    result = train_grpo(args.dataset, config)
    print(f"\nTraining complete!")
    print(f"  Target:  {args.target}")
    print(f"  Model:   {base_model}")
    print(f"  Adapter: {result['adapter_path']}")
    if result.get('gguf_path'):
        print(f"  GGUF:    {result['gguf_path']}")
    print(f"  Loss:    {result['metrics'].get('train_loss', 'N/A')}")
    print(f"  Runtime: {result['metrics'].get('train_runtime', 0):.1f}s")
    if args.time_budget:
        print(f"  Budget:  {args.time_budget:.1f} min")


if __name__ == "__main__":
    main()
