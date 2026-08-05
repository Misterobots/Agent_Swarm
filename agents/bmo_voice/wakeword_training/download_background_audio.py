"""Companion to download_negatives.sh: fetches raw background/impulse-response audio
used by microwakeword.audio.augmentation.Augmentation (RIR reverb simulation + background
noise mixing). Ported directly from microWakeWord's own training notebook cell 4 (which
itself credits openWakeWord's automatic_model_training.ipynb, "accessed March 4, 2024") —
NOT adapted from any openWakeWord *code*, this is just the download step, identical for
both projects since it's generic background audio, not wake-word-specific.

Idempotent / self-healing: every dataset checks for its target directory's existence
(and, where practical, a minimum expected file count) before re-downloading anything.

LICENSING NOTE, carried over from the source notebook: this audio has a mixture of
licenses and usage restrictions. Treat any model trained with it as appropriate for
non-commercial personal use only.
"""

import os
from pathlib import Path

import numpy as np
import scipy.io.wavfile

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
BG_DIR = DATA_DIR / "background_audio"


def log(msg: str) -> None:
    print(f"[download_background_audio] {msg}", flush=True)


def _dir_has_files(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def download_mit_rirs() -> None:
    """MIT environmental impulse responses — used for reverb ("RIR") augmentation."""
    out_dir = BG_DIR / "mit_rirs"
    if _dir_has_files(out_dir):
        log(f"mit_rirs already present at {out_dir} — skipping.")
        return

    import datasets

    out_dir.mkdir(parents=True, exist_ok=True)
    log("Downloading MIT_environmental_impulse_responses (streaming)...")
    rir_dataset = datasets.load_dataset(
        "davidscripka/MIT_environmental_impulse_responses", split="train", streaming=True
    )
    count = 0
    for row in rir_dataset:
        name = row["audio"]["path"].split("/")[-1]
        scipy.io.wavfile.write(
            str(out_dir / name), 16000, (row["audio"]["array"] * 32767).astype(np.int16)
        )
        count += 1
    log(f"mit_rirs: wrote {count} clips to {out_dir}.")


def download_audioset_part() -> None:
    """AudioSet background noise — DISABLED (upstream source removed).

    This was written against agkphysics/AudioSet's old layout: a single
    `data/bal_train09.tar` of .flac clips (~1 GB, the notebook's minimal-viable sample).
    That dataset has since been restructured to sharded parquet (`data/bal_train/NN.parquet`)
    — the old .tar URL now 404s, and streaming the parquet corpus via `datasets` pulls far
    more than the intended ~1 GB. AudioSet is only ONE of several augmentation background
    sources (FMA music + MIT RIR reverb remain, downloaded above/below), so it's skipped
    here rather than chased. To re-enable: drop 16 kHz WAVs into background_audio/audioset_16k/
    by hand — the "already present" check below will then use them, and extract_features.py's
    background_paths picks up any populated background dir automatically.
    """
    out_dir = BG_DIR / "audioset_16k"
    if _dir_has_files(out_dir):
        log(f"audioset_16k already present at {out_dir} — using it.")
        return
    log("audioset_16k SKIPPED — upstream .tar source removed (restructured to parquet); "
        "see docstring. Augmentation background will use FMA + MIT RIRs.")


def download_fma_xs() -> None:
    """Free Music Archive extra-small subset (third-party mirror), resampled to 16kHz."""
    zip_dir = BG_DIR / "fma_raw"
    out_dir = BG_DIR / "fma_16k"
    if _dir_has_files(out_dir):
        log(f"fma_16k already present at {out_dir} — skipping.")
        return

    import datasets
    import urllib.request
    import zipfile

    zip_dir.mkdir(parents=True, exist_ok=True)
    fname = "fma_xs.zip"
    zip_path = zip_dir / fname
    if not zip_path.exists() or zip_path.stat().st_size < 50_000_000:
        log(f"Downloading {fname}...")
        url = f"https://huggingface.co/datasets/mchl914/fma_xsmall/resolve/main/{fname}"
        urllib.request.urlretrieve(url, str(zip_path))
    else:
        log(f"{fname} already downloaded ({zip_path.stat().st_size} bytes).")

    log(f"Extracting {fname}...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(str(zip_dir))

    out_dir.mkdir(parents=True, exist_ok=True)
    mp3_files = [str(p) for p in zip_dir.glob("**/*.mp3")]
    log(f"Resampling {len(mp3_files)} FMA clips to 16kHz WAV...")
    fma_dataset = datasets.Dataset.from_dict({"audio": mp3_files})
    fma_dataset = fma_dataset.cast_column("audio", datasets.Audio(sampling_rate=16000))
    for row in fma_dataset:
        name = row["audio"]["path"].split("/")[-1].replace(".mp3", ".wav")
        scipy.io.wavfile.write(
            str(out_dir / name), 16000, (row["audio"]["array"] * 32767).astype(np.int16)
        )
    log(f"fma_16k: wrote {len(mp3_files)} clips to {out_dir}.")


if __name__ == "__main__":
    BG_DIR.mkdir(parents=True, exist_ok=True)
    download_mit_rirs()
    download_audioset_part()
    download_fma_xs()
    log("All background audio sources ready.")
