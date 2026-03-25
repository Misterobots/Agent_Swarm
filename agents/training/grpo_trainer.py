"""
QLoRA GRPO training wrapper for MarsRL fine-tuning.

Uses HuggingFace TRL's GRPOTrainer with 4-bit quantization to fit
8B+ models on the RTX 5060 Ti (16GB VRAM).

Training order:
  1. Solver (qwen2.5-coder) — code quality from MarsRL traces
  2. Router (nemotron-orchestrator) — routing accuracy via DPO (future)

Usage:
    python -m training.grpo_trainer --dataset training_data/grpo_traces.jsonl
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
        cur.execute(
            """
            UPDATE swarm.training_runs
            SET status = %s,
                metrics = COALESCE(%s::jsonb, metrics),
                error_message = COALESCE(%s, error_message),
                completed_at = CASE WHEN %s IN ('completed','failed')
                               THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id = %s
            """,
            (status, json.dumps(metrics) if metrics else None, error, status, run_id),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to update training run {run_id}: {e}")


def train_grpo(
    dataset_path: str,
    config: Optional[GRPOTrainingConfig] = None,
) -> Dict[str, Any]:
    """
    Run QLoRA GRPO training on a JSONL dataset.

    Returns dict with: adapter_path, metrics, run_id
    """
    if config is None:
        config = GRPOTrainingConfig()

    # Lazy imports — these are heavy and only needed on Justin-PC
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
        from peft import LoraConfig, get_peft_model, TaskType
        from trl import GRPOConfig, GRPOTrainer

        class PrometheusTrainingCallback(TrainerCallback):
            """Push per-step training metrics to Prometheus gauges."""

            def __init__(self):
                self._metrics = None

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
                            TRAINING_STEP_TIME,
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
                        }
                    except ImportError:
                        logger.warning("Prometheus metrics not available for training callback")
                        self._metrics = {}
                return self._metrics

            def on_train_begin(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("active"):
                    m["active"].set(1)
                logger.info("[PrometheusCallback] Training metrics active")

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

            def on_step_end(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("step"):
                    m["step"].set(state.global_step)

            def on_train_end(self, args, state, control, **kwargs):
                m = self._load_metrics()
                if m.get("active"):
                    m["active"].set(0)
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
            "Run: pip install torch transformers peft trl bitsandbytes"
        )

    # Load dataset
    trajectories = _load_dataset(dataset_path)
    if not trajectories:
        raise ValueError(f"No trajectories found in {dataset_path}")

    reward_fn = MarsRewardFunction()

    # Record training run start
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

        # 4-bit quantization config for QLoRA
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        logger.info(f"Loading base model: {config.base_model}")
        tokenizer = AutoTokenizer.from_pretrained(
            config.base_model, trust_remote_code=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            config.base_model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        # LoRA configuration
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=config.lora_rank,
            lora_alpha=config.lora_alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            bias="none",
        )

        model = get_peft_model(model, lora_config)
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
            gradient_checkpointing=True,
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
            callbacks.append(PrometheusTrainingCallback())
        except Exception as e:
            logger.warning(f"Prometheus training callback unavailable: {e}")

        if time_bounded:
            budget_seconds = config.time_budget_minutes * 60
            callbacks.append(TimeBudgetCallback(budget_seconds))
            logger.info(
                f"[TimeBudget] Budget set: {config.time_budget_minutes:.1f} min "
                f"(timer starts after model load)"
            )

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
        adapter_path = str(run_dir / "adapter")
        model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)
        logger.info(f"LoRA adapter saved to {adapter_path}")

        # Collect metrics
        metrics = {
            "train_loss": train_result.training_loss,
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_samples": len(prompts),
            "trainable_params": trainable_params,
            "total_params": total_params,
            "time_budget_minutes": config.time_budget_minutes,
            "budget_limited": time_bounded,
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
            "metrics": metrics,
            "run_id": run_id,
            "run_dir": str(run_dir),
        }

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        if run_id:
            _update_training_run(run_id, "failed", error=str(e))
        try:
            from metrics import TRAINING_RUNS_TOTAL
            TRAINING_RUNS_TOTAL.labels(run_type="training", status="failed").inc()
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description="Run QLoRA GRPO training")
    parser.add_argument("--dataset", "-d", required=True, help="Path to GRPO JSONL dataset")
    parser.add_argument("--base-model", default=TRAINING_BASE_SOLVER, help="HuggingFace model ID")
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

    config = GRPOTrainingConfig(
        base_model=args.base_model,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        lora_rank=args.lora_rank,
        learning_rate=args.lr,
        time_budget_minutes=args.time_budget,
    )

    result = train_grpo(args.dataset, config)
    print(f"\nTraining complete!")
    print(f"  Adapter: {result['adapter_path']}")
    print(f"  Loss:    {result['metrics'].get('train_loss', 'N/A')}")
    print(f"  Runtime: {result['metrics'].get('train_runtime', 0):.1f}s")
    if args.time_budget:
        print(f"  Budget:  {args.time_budget:.1f} min")


if __name__ == "__main__":
    main()
