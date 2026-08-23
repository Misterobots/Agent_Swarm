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

Two positive sources are extracted independently into two output feature sets:
  - generated_samples/  ->  generated_augmented_features/   (synthetic TTS positives — always)
  - real_samples/       ->  real_augmented_features/        (OPTIONAL real recordings)
Both get the IDENTICAL augmentation chain, so real clips also pick up simulated noise/reverb
on top of whatever room they were actually recorded in. Each real recording must be ONE
utterance per WAV (16 kHz mono) — Clips reads each file as a single clip and windows it to
clip_duration_ms, so a continuous multi-utterance file would collapse to one usable clip.
The real source is skipped silently when real_samples/ is absent or empty, so this stays a
no-op for a fresh clone / anyone who hasn't added real recordings.

training_parameters.yaml lists the two as SEPARATE feature sets with their own
sampling_weight — that's what keeps a few dozen real clips from being drowned by the ~4000
synthetic ones (sampling_weight sets how often a set is drawn per batch, INDEPENDENT of its
file count) and, deliberately kept at parity rather than higher, keeps them from DOMINATING
either — so the synthetic set's broad speaker diversity still carries guests / unseen voices.
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
REAL_SAMPLES_DIR = DATA_DIR / "real_samples"
BG_DIR = DATA_DIR / "background_audio"
OUTPUT_DIR = DATA_DIR / "generated_augmented_features"
REAL_OUTPUT_DIR = DATA_DIR / "real_augmented_features"
# Optional household HARD-NEGATIVES: your rooms' ambient audio (TV / conversation / music) that has
# been FALSE-triggering the wake word, pre-sliced into ~1.5 s clips (see slice_negatives.sh and
# RECORDING_NEGATIVES.md). Featurized with the SAME augmentation chain as the positives — it is the
# `truth: false` flag in training_parameters.yaml, NOT the extraction, that makes them negatives.
# Inert until household_negatives/ is populated (extract is a no-op on an empty/absent dir).
HOUSEHOLD_NEG_DIR = DATA_DIR / "household_negatives"
HOUSEHOLD_NEG_OUTPUT_DIR = DATA_DIR / "household_negative_features"


def log(msg: str) -> None:
    print(f"[extract_features] {msg}", flush=True)


def already_done(output_dir: Path) -> bool:
    """Idempotency check: a prior successful run leaves a non-empty wakeword_mmap dir
    under every split. Re-running after a partial/interrupted run will re-do all splits
    (cheap relative to sample generation / downloads, so not worth finer-grained resume).

    NOTE: to pick up newly-added real recordings you must delete the corresponding
    *_augmented_features/ directory first, or this check will short-circuit re-extraction."""
    for split in ("training", "validation", "testing"):
        mmap_dir = output_dir / split / "wakeword_mmap"
        if not mmap_dir.exists() or not any(mmap_dir.iterdir()):
            return False
    return True


def _existing_bg_dirs() -> list:
    """Background-noise source dirs that actually populated. AudioSet is optional (its
    upstream source was removed — see download_background_audio.py), so include only dirs
    that exist and are non-empty; audiomentations' AddBackgroundNoise errors on a
    missing/empty path. Falls back to mit_rirs if no dedicated background source downloaded,
    so AddBackgroundNoise always has at least one non-empty source to draw from."""
    candidates = [BG_DIR / "fma_16k", BG_DIR / "audioset_16k"]
    dirs = [str(d) for d in candidates if d.exists() and any(d.iterdir())]
    if not dirs:
        rirs = BG_DIR / "mit_rirs"
        if rirs.exists() and any(rirs.iterdir()):
            dirs = [str(rirs)]
    log(f"augmentation background_paths: {dirs or '(none found)'}")
    return dirs


def _build_augmenter() -> Augmentation:
    # Parameters below are copied verbatim from microWakeWord's own training notebook
    # (cells 5 and 7) — these are the hyperparameters upstream itself suggests
    # experimenting with to improve model quality; left at defaults here since this
    # pipeline's job is to reproduce the confirmed-working shape, not to tune it.
    return Augmentation(
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
        background_paths=_existing_bg_dirs(),
        background_min_snr_db=-5,
        background_max_snr_db=10,
        min_jitter_s=0.195,
        max_jitter_s=0.205,
    )


def _extract_source(name: str, samples_dir: Path, output_dir: Path,
                    augmenter: Augmentation) -> None:
    """Featurize every *.wav (recursively) under samples_dir into output_dir's
    training/validation/testing RaggedMmap splits. Shared by the synthetic and real
    positive sets — same augmentation chain for both. A missing/empty samples_dir is a
    no-op (the real set is optional)."""
    if already_done(output_dir):
        log(f"[{name}] augmented features already present under {output_dir} — skipping.")
        return

    wav_count = sum(1 for _ in samples_dir.glob("**/*.wav")) if samples_dir.exists() else 0
    if wav_count == 0:
        log(f"[{name}] no .wav files under {samples_dir} — skipping this source.")
        return

    log(f"[{name}] extracting {wav_count} wav file(s) from {samples_dir} -> {output_dir}")

    clips = Clips(
        input_directory=str(samples_dir),
        file_pattern="**/*.wav",
        max_clip_duration_s=None,
        remove_silence=False,
        random_split_seed=10,
        split_count=0.1,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    for split in ("training", "validation", "testing"):
        out_dir = output_dir / split
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

        log(f"[{name}] generating '{split}' split (source split='{split_name}', repeat={repetition})...")
        RaggedMmap.from_generator(
            out_dir=str(out_dir / "wakeword_mmap"),
            sample_generator=spectrograms.spectrogram_generator(split=split_name, repeat=repetition),
            batch_size=100,
            verbose=True,
        )


def main() -> None:
    start = time.time()
    augmenter = _build_augmenter()

    # Synthetic TTS positives — always present (produced by generate_samples.sh).
    _extract_source("synthetic", SAMPLES_DIR, OUTPUT_DIR, augmenter)

    # Optional real recordings dropped into real_samples/ (one utterance per 16 kHz mono
    # WAV). Inert if that directory is absent/empty. When you DO add clips, also uncomment
    # the real_augmented_features block in training_parameters.yaml so training actually
    # uses them (see that file's comment for the weighting rationale).
    _extract_source("real", REAL_SAMPLES_DIR, REAL_OUTPUT_DIR, augmenter)

    # Optional household hard-negatives — your rooms' false-triggering ambient audio, pre-sliced
    # to ~1.5 s clips in household_negatives/. Inert if that dir is absent/empty. When you add
    # clips, also uncomment the household_negative_features block in training_parameters.yaml
    # (truth: false) so training actually learns to reject them.
    _extract_source("household_neg", HOUSEHOLD_NEG_DIR, HOUSEHOLD_NEG_OUTPUT_DIR, augmenter)

    log(f"Done. Elapsed: {time.time() - start:.0f}s.")


if __name__ == "__main__":
    main()
