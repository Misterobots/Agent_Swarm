#!/usr/bin/env python3
"""
recover_training_runs.py — Backfill swarm.training_runs for completed-on-disk runs
that were never recorded (e.g. due to DB connection failure during training).

Usage:
    python scripts/recover_training_runs.py [--dry-run] [--training-dir /path]

Logic:
1. Scan TRAINING_OUTPUT_DIR for grpo_YYYYMMDD_HHMMSS directories.
2. Parse started_at from the directory name timestamp.
3. Read adapter/adapter_config.json for target_model (base_model_name_or_path).
4. Optionally read training_config.json written by grpo_trainer.py.
5. Check existing DB records keyed by started_at (within a 5-second window).
6. Infer status from filesystem artifacts.
7. Insert missing records with metrics = {"recovered": true}.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

try:
    from config import TRAINING_OUTPUT_DIR, TEMPLATE_DB_URL
except ImportError:
    TRAINING_OUTPUT_DIR = os.getenv("TRAINING_OUTPUT_DIR", "/workspace/training_output")
    TEMPLATE_DB_URL = os.getenv(
        "TEMPLATE_DB_URL",
        "postgresql://langfuse:langfuseshively@192.168.2.102:5432/langfuse",
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_run_timestamp(dir_name: str) -> datetime | None:
    """Parse started_at from grpo_YYYYMMDD_HHMMSS directory name."""
    try:
        ts_part = dir_name.removeprefix("grpo_")
        return datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
    except ValueError:
        logger.warning("Cannot parse timestamp from dir name: %s", dir_name)
        return None


def _infer_status(run_dir: Path) -> str:
    """Infer run status from on-disk artifacts."""
    # GGUF conversion complete → definitely completed
    if list(run_dir.glob("*.gguf")):
        return "completed"
    # PEFT adapter weights present → training completed
    adapter_dir = run_dir / "adapter"
    if adapter_dir.is_dir():
        if (
            (adapter_dir / "adapter_model.safetensors").exists()
            or (adapter_dir / "adapter_model.bin").exists()
        ):
            return "completed"
    # training_config.json present but no adapter weights → likely failed
    if (run_dir / "training_config.json").exists():
        return "failed"
    return "failed"


def _read_adapter_config(run_dir: Path) -> dict:
    """Read HuggingFace PEFT adapter_config.json if present."""
    adapter_config_path = run_dir / "adapter" / "adapter_config.json"
    if adapter_config_path.exists():
        try:
            return json.loads(adapter_config_path.read_text())
        except Exception as exc:
            logger.warning("Failed to read adapter_config.json in %s: %s", run_dir, exc)
    return {}


def _read_training_config(run_dir: Path) -> dict:
    """Read training_config.json written by grpo_trainer.py if present."""
    tc_path = run_dir / "training_config.json"
    if tc_path.exists():
        try:
            return json.loads(tc_path.read_text())
        except Exception as exc:
            logger.warning("Failed to read training_config.json in %s: %s", run_dir, exc)
    return {}


def _get_existing_started_ats(conn) -> set:
    """Fetch all existing started_at values from swarm.training_runs."""
    cur = conn.cursor()
    cur.execute("SELECT started_at FROM swarm.training_runs")
    rows = cur.fetchall()
    cur.close()
    return {row[0] for row in rows if row[0] is not None}


def _run_dir_already_recorded(started_at: datetime, existing_ats: set) -> bool:
    """Return True if a DB record exists within 5 seconds of this started_at."""
    window = timedelta(seconds=5)
    for existing in existing_ats:
        # existing may be a datetime already (psycopg2 returns datetime for TIMESTAMP)
        if abs(existing.replace(tzinfo=None) - started_at) <= window:
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scan_and_recover(training_dir: Path, dry_run: bool) -> None:
    import psycopg2

    run_dirs = sorted(
        [d for d in training_dir.iterdir() if d.is_dir() and d.name.startswith("grpo_")]
    )
    if not run_dirs:
        logger.info("No grpo_* directories found in %s", training_dir)
        return

    logger.info("Found %d grpo_* directories to inspect.", len(run_dirs))

    try:
        conn = psycopg2.connect(TEMPLATE_DB_URL)
    except Exception as exc:
        logger.error(
            "Cannot connect to DB (%s): %s — aborting recovery.", TEMPLATE_DB_URL, exc
        )
        sys.exit(1)

    existing_ats = _get_existing_started_ats(conn)
    logger.info("DB already has %d training_runs records.", len(existing_ats))

    inserted = 0
    skipped = 0

    for run_dir in run_dirs:
        started_at = _parse_run_timestamp(run_dir.name)
        if started_at is None:
            skipped += 1
            continue

        if _run_dir_already_recorded(started_at, existing_ats):
            logger.debug("SKIP %s — already in DB", run_dir.name)
            skipped += 1
            continue

        adapter_cfg = _read_adapter_config(run_dir)
        training_cfg = _read_training_config(run_dir)

        target_model = (
            adapter_cfg.get("base_model_name_or_path")
            or training_cfg.get("base_model")
            or "unknown"
        )
        dataset_path = training_cfg.get("dataset_path") or ""
        status = _infer_status(run_dir)

        config_payload = {
            "recovered_from": str(run_dir),
            **{k: v for k, v in training_cfg.items() if k not in ("run_id",)},
        }
        if adapter_cfg:
            config_payload["adapter_config"] = {
                k: adapter_cfg[k]
                for k in ("peft_type", "r", "lora_alpha", "target_modules")
                if k in adapter_cfg
            }

        metrics_payload = {
            "recovered": True,
            "recovered_at": datetime.utcnow().isoformat() + "Z",
        }

        completed_at = None
        if status == "completed":
            # Use mtime of adapter weights as a proxy for completion time
            for candidate in [
                run_dir / "adapter" / "adapter_model.safetensors",
                run_dir / "adapter" / "adapter_model.bin",
                *list(run_dir.glob("*.gguf")),
            ]:
                if candidate.exists():
                    completed_at = datetime.fromtimestamp(candidate.stat().st_mtime)
                    break

        logger.info(
            "%s dir=%s  target_model=%s  status=%s  completed_at=%s",
            "[DRY-RUN]" if dry_run else "[INSERT]",
            run_dir.name,
            target_model,
            status,
            completed_at,
        )

        if not dry_run:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO swarm.training_runs
                        (run_type, target_model, dataset_path, dataset_size,
                         status, config, metrics, started_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        "training",
                        target_model,
                        dataset_path,
                        0,
                        status,
                        json.dumps(config_payload),
                        json.dumps(metrics_payload),
                        started_at,
                        completed_at,
                    ),
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                cur.close()
                logger.info("  → inserted as run id=%d", new_id)
                inserted += 1
            except Exception as exc:
                conn.rollback()
                logger.error(
                    "  → DB insert failed for %s: %s",
                    run_dir.name,
                    exc,
                    exc_info=True,
                )
                skipped += 1

    conn.close()

    logger.info(
        "Recovery complete. inserted=%d  skipped/already-present=%d",
        inserted,
        skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill swarm.training_runs for on-disk grpo_* run directories."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without writing to DB.",
    )
    parser.add_argument(
        "--training-dir",
        default=TRAINING_OUTPUT_DIR,
        help=f"Path to training output directory (default: {TRAINING_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    training_dir = Path(args.training_dir)
    if not training_dir.is_dir():
        logger.error("Training directory not found: %s", training_dir)
        sys.exit(1)

    logger.info(
        "Scanning %s  (dry_run=%s)", training_dir, args.dry_run
    )
    scan_and_recover(training_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
