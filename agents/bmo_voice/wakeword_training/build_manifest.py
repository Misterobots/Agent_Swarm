"""Step 6 of the pipeline: package the trained quantized TFLite model into the
manifest.json ESPHome's micro_wake_word component actually expects.

Schema verified against REAL manifests fetched live from
github.com/esphome/micro-wake-word-models (models/v2/okay_nabu.json and
models/v2/hey_jarvis.json) — NOT the flattened field layout described in the original
task brief. The real schema nests the ESPHome-specific numeric fields under a "micro"
object:

    {
      "type": "micro",
      "wake_word": "Hey Jarvis",
      "author": "...",
      "website": "...",
      "model": "hey_jarvis.tflite",
      "trained_languages": ["en"],
      "version": 2,
      "micro": {
        "probability_cutoff": 0.97,
        "feature_step_size": 10,
        "sliding_window_size": 5,
        "tensor_arena_size": 22860,
        "minimum_esphome_version": "2024.7.0"
      }
    }

Both fetched real examples used identical probability_cutoff (0.97), feature_step_size
(10), sliding_window_size (5), and minimum_esphome_version (2024.7.0) despite being
different wake words — those are treated as safe defaults below. tensor_arena_size is
the one field that's genuinely model-architecture-dependent (the two real examples
differ: 22860 vs 26080) and is NOT independently confirmed correct for the mixednet
config this pipeline trains (--pointwise_filters "64,64,64,64", different from whatever
config okay_nabu/hey_jarvis were themselves trained with) — see the --tensor-arena-size
default and comment below.

Output lands under /data/models/hey_friday/ (inside the persistent, bind-mounted /data
volume — NOT baked into the image, NOT auto-committed to git). Per the TODO already
left in ../esphome/google-mini-voice.yaml, the final step (manual, outside this
container) is copying data/models/hey_friday/ into
agents/bmo_voice/wakeword_training/models/hey_friday/ and committing it, then adding a
`micro_wake_word: models:` entry there pointing at its raw.githubusercontent.com URL —
mirroring the existing `kenobi` entry's pattern, not the `hey_jarvis` bare-name pattern
(which only works for models built into the component itself).
"""

import argparse
import json
import os
import shutil
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DEFAULT_TFLITE = (
    DATA_DIR
    / "trained_models"
    / "wakeword"
    / "tflite_stream_state_internal_quant"
    / "stream_state_internal_quant.tflite"
)
DEFAULT_OUTPUT_DIR = DATA_DIR / "models" / "hey_friday"


def build_manifest(args: argparse.Namespace) -> dict:
    return {
        "type": "micro",
        "wake_word": args.wake_word,
        "author": args.author,
        "website": args.website,
        "model": args.model_filename,
        "trained_languages": ["en"],
        "version": 2,
        "micro": {
            "probability_cutoff": args.probability_cutoff,
            "feature_step_size": args.feature_step_size,
            "sliding_window_size": args.sliding_window_size,
            "tensor_arena_size": args.tensor_arena_size,
            "minimum_esphome_version": args.minimum_esphome_version,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tflite-path",
        type=Path,
        default=DEFAULT_TFLITE,
        help="Path to the trained quantized streaming TFLite model (train.sh's output).",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--wake-word", default="Hey Friday")
    parser.add_argument("--model-id", default="hey_friday", help="Base filename (no extension) for the .tflite/.json pair.")
    parser.add_argument("--author", default="")
    parser.add_argument("--website", default="")
    parser.add_argument(
        "--probability-cutoff",
        type=float,
        default=0.97,
        help="Detection threshold. 0.97 matches both real ESPHome examples fetched as "
        "ground truth (okay_nabu, hey_jarvis) — start here, then tune down if the model "
        "under-triggers or up if it false-triggers, per real-device testing.",
    )
    parser.add_argument(
        "--feature-step-size",
        type=int,
        default=10,
        help="Spectrogram step size in ms. MUST match training_parameters.yaml's "
        "window_step_ms (also 10) — these describe the same quantity from two sides of "
        "the training/inference boundary, kept in sync deliberately, not coincidentally.",
    )
    parser.add_argument("--sliding-window-size", type=int, default=5)
    parser.add_argument(
        "--tensor-arena-size",
        type=int,
        default=26000,
        help="UNCONFIRMED for this exact model architecture — see module docstring. "
        "The two real examples fetched as ground truth (okay_nabu, hey_jarvis) used "
        "22860 and 26080 for a *different* mixednet config than this pipeline trains "
        "(--pointwise_filters '64,64,64,64'), so this default is an interpolated guess, "
        "not a verified value. If the device fails to load the model, ESPHome's own "
        "boot log reports the actually-required arena size — set this to that reported "
        "value and redeploy.",
    )
    parser.add_argument("--minimum-esphome-version", default="2024.7.0")
    args = parser.parse_args()

    if not args.tflite_path.exists():
        raise SystemExit(
            f"[build_manifest] Trained model not found at {args.tflite_path} — run train.sh first."
        )

    args.model_filename = f"{args.model_id}.tflite"
    manifest = build_manifest(args)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tflite_dest = args.output_dir / args.model_filename
    shutil.copyfile(args.tflite_path, tflite_dest)

    manifest_path = args.output_dir / f"{args.model_id}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"[build_manifest] Wrote {tflite_dest} ({tflite_dest.stat().st_size} bytes)")
    print(f"[build_manifest] Wrote {manifest_path}:")
    print(json.dumps(manifest, indent=2))
    print(
        "\n[build_manifest] NEXT STEP (manual, outside this container): copy "
        f"{args.output_dir} into agents/bmo_voice/wakeword_training/models/{args.model_id}/ "
        "in the repo, commit it, then add a `micro_wake_word: models:` entry in "
        "../esphome/google-mini-voice.yaml pointing at its raw.githubusercontent.com URL "
        "(see the TODO already left in that file, mirroring the `kenobi` entry's pattern)."
    )


if __name__ == "__main__":
    main()
