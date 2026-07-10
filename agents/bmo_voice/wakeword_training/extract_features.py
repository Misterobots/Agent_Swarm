"""Feature extraction + augmentation step, run by train.sh before model_train_eval.

microWakeWord doesn't expose this as its own CLI (its training notebook does it inline
in notebook cells) — this is that same logic ported to a standalone script so it's
re-runnable and inspectable outside a notebook. Ported directly from
basic_training_notebook.ipynb cells 5-7 (fetched from
github.com/kahrendt/microWakeWord/notebooks/basic_training_notebook.ipynb and verified
against microwakeword/audio/clips.py, augmentation.py, spectrograms.py source): uses
microWakeWord's own SpectrogramGeneration (slide_frames=10 for train/validation,
slide_frames=1 for test) — this is NOT openWakeWord's mel-spectrogram embedding, the two
are structurally incompatible, and no openWakeWord feature code was reused here.

file_pattern is '**/*.wav' (recursive), not the notebook's flat '*.wav': generate_samples.sh
writes each phrase variant into its own numbered subdirectory (avoiding filename collisions
between variants, since piper-sample-generator always numbers files 0.wav, 1.wav, ... from
zero on every invocation), so feature extraction has to glob recursively to see all of them.
"""

import os
import time
from pathlib import Path

from microwakeword.audio.augmentation import Augmentation
from microwakeword.audio.clips import Clips
from microwakeword.audio.spectrograms import SpectrogramGeneration
from mmap_ninja.ragged import RaggedMmap

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SAMPLES_DIR = DATA_DIR / "generated_samples"
BG_DIR = DATA_DIR / "background_audio"
OUTPUT_DIR = DATA_DIR / "generated_augmented_features"


def log(msg: str) -> None:
    print(f"[extract_features] {msg}", flush=True)


def already_done() -> bool:
    """Idempotency check: a prior successful run leaves a non-empty wakeword_mmap dir
    under every split. Re-running after a partial/interrupted run will re-do all splits
    (cheap relative to sample generation / downloads, so not worth finer-grained resume)."""
    for split in ("training", "validation", "testing"):
        mmap_dir = OUTPUT_DIR / split / "wakeword_mmap"
        if not mmap_dir.exists() or not any(mmap_dir.iterdir()):
            return False
    return True


def main() -> None:
    if already_done():
        log(f"Augmented features already present under {OUTPUT_DIR} — skipping extraction.")
        return

    start = time.time()

    # Parameters below are copied verbatim from microWakeWord's own training notebook
    # (cells 5 and 7) — these are the hyperparameters upstream itself suggests
    # experimenting with to improve model quality; left at defaults here since this
    # pipeline's job is to reproduce the confirmed-working shape, not to tune it.
    clips = Clips(
        input_directory=str(SAMPLES_DIR),
        file_pattern="**/*.wav",
        max_clip_duration_s=None,
        remove_silence=False,
        random_split_seed=10,
        split_count=0.1,
    )

    augmenter = Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.1,
            "TanhDistortion": 0.1,
            "PitchShift": 0.1,
            "BandStopFilter": 0.1,
            "AddColorNoise": 0.1,
            "AddBackgroundNoise": 0.75,
            "Gain": 1.0,
            "RIR": 0.5,
        },
        impulse_paths=[str(BG_DIR / "mit_rirs")],
        background_paths=[str(BG_DIR / "fma_16k"), str(BG_DIR / "audioset_16k")],
        background_min_snr_db=-5,
        background_max_snr_db=10,
        min_jitter_s=0.195,
        max_jitter_s=0.205,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for split in ("training", "validation", "testing"):
        out_dir = OUTPUT_DIR / split
        out_dir.mkdir(parents=True, exist_ok=True)

        if split == "training":
            split_name, repetition, slide_frames = "train", 2, 10
        elif split == "validation":
            split_name, repetition, slide_frames = "validation", 1, 10
        else:  # testing — streaming model, no artificial repetition needed
            split_name, repetition, slide_frames = "test", 1, 1

        spectrograms = SpectrogramGeneration(
            clips=clips,
            augmenter=augmenter,
            slide_frames=slide_frames,
            step_ms=10,
        )

        log(f"Generating '{split}' split (source split='{split_name}', repeat={repetition})...")
        RaggedMmap.from_generator(
            out_dir=str(out_dir / "wakeword_mmap"),
            sample_generator=spectrograms.spectrogram_generator(split=split_name, repeat=repetition),
            batch_size=100,
            verbose=True,
        )

    log(f"Done. Elapsed: {time.time() - start:.0f}s.")


if __name__ == "__main__":
    main()
