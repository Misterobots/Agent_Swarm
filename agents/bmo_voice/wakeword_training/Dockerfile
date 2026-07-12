# microWakeWord training pipeline — one-shot batch job, not a long-running service.
# Trains a "Hey Friday" wake-word model for the google-mini-voice ESPHome satellite
# (see ../esphome/google-mini-voice.yaml). Everything this container writes lands on
# the host-bind-mounted /data volume — deliberately, so a container restart/rebuild
# never loses generated samples or downloaded datasets the way the previous Colab
# attempt (ephemeral /content, no Drive mount) lost all of its openWakeWord training
# audio and kept only the final .onnx.
#
# Build (CPU-only TensorFlow — the confirmed-safe default, see the TF_GPU note below):
#   docker build -t wakeword-training agents/bmo_voice/wakeword_training
#
# Run (full pipeline, GPU 1 — the idle 5060 Ti, matching this repo's convention of
# leaving GPU 0 for whatever's already resident there; see README.md):
#   docker run --rm --gpus '"device=1"' \
#     -v "$(pwd)/agents/bmo_voice/wakeword_training/data:/data" \
#     wakeword-training
#
# Run a single step instead of the full chain (CMD is overridable):
#   docker run --rm --gpus '"device=1"' -v ...:/data wakeword-training /opt/wakeword/train.sh

FROM python:3.11-slim
# Python 3.11 chosen deliberately, not just "latest": piper-phonemize-cross==1.2.1 (below)
# ships manylinux wheels only up to cp312 (no cp313 at the time this was written — verified
# against its PyPI file listing), and pymicro-features/ai-edge-litert both cover 3.11
# comfortably. 3.11 sits in the middle of every pinned dependency's supported range instead
# of at either edge of it.

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies:
#   - git: needed at build time to clone/pin piper-sample-generator (below).
#   - espeak-ng + libespeak-ng-dev: piper-tts's EspeakPhonemizer (imported unconditionally
#     by generate_samples.py at the pinned commit, see the note further down) dlopens
#     libespeak-ng at runtime. piper-phonemize-cross bundles its own native espeak build
#     for its own phonemization path, but that does NOT satisfy piper-tts's separate
#     Python-level wrapper — this was already confirmed the hard way in this repo's
#     earlier openWakeWord wake-word pipeline (see the apt-get line in the recovered
#     "Copy of train_wakeword.ipynb" notebook this project's dependency list was
#     cross-referenced against).
#   - ffmpeg + libsndfile1: audio decode for the `datasets` Audio() cast_column step
#     (FMA .mp3 / AudioSet .flac -> 16 kHz PCM WAV) and for audiomentations' background
#     clip loading.
#   - build-essential/cmake/pkg-config: fallback source-build toolchain in case any
#     pinned dependency lacks a manylinux wheel for this exact Python/arch (the versions
#     pinned below were confirmed to have cp311-manylinux wheels, so this should rarely
#     actually trigger a compile — kept as a safety net, not because it's expected to run).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    unzip \
    ffmpeg \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng-dev \
    libsndfile1 \
    build-essential \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/wakeword

RUN pip install --no-cache-dir --upgrade pip

# -----------------------------------------------------------------------------------
# TensorFlow — microWakeWord's actual training/quantization/export engine. Its own
# setup.py declares `tensorflow>=2.18` with no upper bound; 2.21.0 is the latest stable
# release on PyPI as of when this was written (2026-07), and the one pinned here.
#
# BLACKWELL (sm_120 / RTX 50-series) GPU SUPPORT — VERIFIED AS *NOT* RELIABLE, NOT
# ASSUMED. Live-checked across four independent sources before writing this:
#   1. github.com/tensorflow/tensorflow issue #89272 — TF nightly on an RTX 5090
#      (compute capability 12.0) hits CUDA_ERROR_INVALID_PTX / CUDA_ERROR_INVALID_HANDLE.
#      Still open, "stat:awaiting tensorflower", no fix landed.
#   2. github.com/tensorflow/tensorflow issue #90291 — same failure class on an RTX
#      5070 Ti with TF 2.18. Also open, no fix landed.
#   3. NVIDIA's own TensorFlow NGC container line (nvcr.io/nvidia/tensorflow) was
#      DISCONTINUED after the 25.02 release (Feb 2025) — there is no newer NGC TF build
#      to fall back on. Its final release, despite being marketed as "Blackwell-optimized,"
#      still logs `'+ptx85' is not a recognized feature for this target` on an RTX 5080
#      per a live Google AI Developer Forum thread, with no confirmed community fix.
#   4. TF's PyPI "tested build configuration" for the 2.20/2.21 line targets CUDA 12.5 —
#      Blackwell (sm_120) requires CUDA 12.8+ at the toolkit level, so even the tested
#      config predates the hardware.
# This is the same *class* of bug already hit and fixed for CTranslate2 on this exact
# GPU (see services/wyoming_whisper_gpu/Dockerfile, ctranslate2>=4.7.0) — but unlike
# CTranslate2, no equivalent "fixed in version X" TensorFlow release exists yet.
#
# Given that, the DEFAULT build installs plain `tensorflow` (no `[and-cuda]` extra).
# Without and-cuda's pip-packaged cuDNN/cuBLAS, TF has no CUDA backend to even attempt
# to load and cleanly runs CPU-only — confirmed-safe, not a compromise taken lightly.
# microWakeWord's mixednet model is tiny (a handful of depthwise-separable MixConv
# blocks, tens of thousands of params, 10k training steps) so CPU training is genuinely
# viable here, just slower than a working GPU path would be.
#
# To attempt GPU anyway (UNVERIFIED — may hard-fail per the issues above; test small
# before committing multi-hour GPU time to it):
#   docker build --build-arg TF_GPU=1 -t wakeword-training-gpu agents/bmo_voice/wakeword_training
# No different base image is needed for this either way: neither the official
# tensorflow/tensorflow:-gpu Docker Hub image nor an nvidia/cuda base changes the
# underlying fact that the TF *binary* lacks sm_120 SASS kernels — only upstream
# actually shipping Blackwell kernels fixes this, not a different base image, which is
# why this Dockerfile does not follow the "prefer an nvidia/cuda-based image" default
# suggestion for the GPU path.
ARG TF_GPU=0
ARG TF_VERSION=2.21.0
RUN if [ "$TF_GPU" = "1" ]; then \
        echo "[Dockerfile] Installing tensorflow[and-cuda]==${TF_VERSION} — UNVERIFIED on Blackwell/sm_120, see the comment block above."; \
        pip install --no-cache-dir "tensorflow[and-cuda]==${TF_VERSION}"; \
    else \
        echo "[Dockerfile] Installing CPU-only tensorflow==${TF_VERSION} (confirmed-safe default)."; \
        pip install --no-cache-dir "tensorflow==${TF_VERSION}"; \
    fi

# -----------------------------------------------------------------------------------
# microWakeWord itself, pinned to a specific commit rather than floating `main` — the
# HEAD of main as of 2026-07-06 ("Pin dependencies", the commit this whole pipeline was
# verified against). Its setup.py declares: numpy>=2.0, pymicro-features, pyyaml,
# webrtcvad-wheels, ai-edge-litert, audiomentations, audio_metadata, datasets,
# mmap_ninja — all pulled in transitively by this one install. (The upstream training
# notebook additionally installs audio_metadata from a Jupyter-specific attrs-conflict
# fork; that conflict is a Jupyter-kernel problem only and does not apply to this
# non-interactive container, so plain PyPI audio_metadata is used here instead.)
ARG MICROWAKEWORD_SHA=4665173cd35f1cff9a61e06fc427f124766c488e
RUN pip install --no-cache-dir "microwakeword @ git+https://github.com/kahrendt/microWakeWord@${MICROWAKEWORD_SHA}"

# -----------------------------------------------------------------------------------
# piper-sample-generator, pinned to commit 1a8c49bd^ (the parent of "Move to package").
# This is the exact commit already battle-tested in this repo's earlier openWakeWord
# wake-word work (cross-referenced against the recovered
# "G:\My Drive\Colab Notebooks\Copy of train_wakeword.ipynb" notebook) — reused
# deliberately, not re-derived. It is the last revision with a flat-layout
# generate_samples.py at the repo root using the CLI microWakeWord's own training
# notebook expects:
#   generate_samples.py "text" --max-samples N --batch-size B --output-dir D
# The very next commit ("Move to package") restructured the repo to a
# `python -m piper_sample_generator` package layout, which breaks that invocation
# entirely — confirmed live: generate_samples.py 404s on both current main and master.
#
# IMPORTANT — a real, confirmed gap in microWakeWord's own upstream training notebook,
# not something to silently work around without saying so: as fetched from
# github.com/kahrendt/microWakeWord/notebooks/basic_training_notebook.ipynb, cells 2-3
# clone piper-sample-generator and invoke generate_samples.py WITHOUT `--model`, and
# never install `piper-tts`. Verified from source that even at this exact pin,
# generate_samples.py unconditionally imports `from piper import PiperVoice,
# SynthesisConfig` at module load time — so the notebook's own cell, run as literally
# written today, fails immediately with `ModuleNotFoundError: No module named 'piper'`,
# before it would ever reach the missing --model problem. This Dockerfile installs
# piper-tts explicitly (below) and generate_samples.sh always passes --model, to work
# around both gaps.
RUN git clone --quiet https://github.com/rhasspy/piper-sample-generator /opt/wakeword/piper-sample-generator \
    && cd /opt/wakeword/piper-sample-generator \
    && git checkout --quiet 1a8c49bd29b3a132721086ee88f2253f788594a8^

# torch/torchaudio: piper-sample-generator's own pyproject.toml at the pinned commit
# declares torch>=2,<3. Stable-PyTorch Blackwell/sm_120 support is ALSO unconfirmed as
# of this writing (github.com/pytorch/pytorch issues #159207 and #164342, both open) —
# but unlike TensorFlow this is not defaulted to CPU-only here, because torch's CUDA
# detection + per-op failure mode is more forgiving in practice (a missing kernel errors
# on that one op rather than silently corrupting output), and generate_samples.sh has a
# PSG_FORCE_CPU escape hatch that sidesteps it entirely if the GPU path errors out.
RUN pip install --no-cache-dir "torch>=2,<3" torchaudio

# piper-phonemize-cross: Python 3.11/3.12-compatible fork of piper-phonemize (upstream
# piper-phonemize has no recent manylinux wheels for these Python versions). Pinned to
# the exact version already validated by this repo's earlier voice pipeline work.
RUN pip install --no-cache-dir "piper-phonemize-cross==1.2.1"

# piper-tts installed LAST, via --no-deps: it's the actual runtime dependency
# generate_samples.py needs for `from piper import PiperVoice, SynthesisConfig` (see the
# note above), but its own transitive deps (onnxruntime, its own numpy pin, etc.) are
# not needed for the .pt/LibriTTS-generator code path this pipeline actually exercises,
# and installing them WITH deps has previously been observed (same earlier openWakeWord
# work) to downgrade/clobber the pins above. --no-deps, installed last, avoids that.
RUN pip install --no-cache-dir --no-deps "piper-tts>=1.3.0,<2"

# onnxruntime is a piper-tts IMPORT-time dependency: piper/voice.py does `import onnxruntime`
# unconditionally, so generate_samples.py's `from piper import PiperVoice` (a top-level import)
# fails with ModuleNotFoundError without it — even though the .pt/LibriTTS-generator code path
# this pipeline actually runs never executes an ONNX model. The --no-deps piper-tts install
# above skipped it: the comment there reasoned "not used at runtime == not needed", but the
# import happens regardless of the code path taken. Confirmed live — a first end-to-end run
# crashed here at Stage 1. numpy is pinned to the version TensorFlow/microWakeWord already
# resolved so onnxruntime's own numpy requirement can't downgrade it (the exact pin-clobber
# the --no-deps strategy exists to prevent).
RUN pip install --no-cache-dir onnxruntime "numpy==2.4.6"

# tensorboard: microwakeword/train.py's training loop calls tf.summary.scalar() to log
# loss/accuracy each step, which requires tensorboard — a separate package the tensorflow
# install above did not pull in. Symptom: the model builds and the initial validation pass
# runs, then training dies at the first tf.summary.scalar with TBNotInstalledError. Confirmed
# tensorboard 2.21.0 restores the call. Placed late so the heavy pip layers above stay cached.
RUN pip install --no-cache-dir tensorboard

# Pin datasets to the 3.x line. microwakeword (above) pulls datasets in transitively
# unpinned -> resolves to 5.x, whose Audio feature returns a torchcodec.AudioDecoder object
# instead of the {"array","path","sampling_rate"} dict that download_background_audio.py
# (ported from microWakeWord's pre-4.0 notebook) indexes into -> "'AudioDecoder' object is
# not subscriptable" at Stage 2. The 3.x line keeps that dict API and decodes wav/flac/mp3
# via soundfile + the image's libsndfile1 (>=1.1 has mp3) — no torchcodec needed. Confirmed
# on 3.6.0: row["audio"] is the expected dict. Placed after onnxruntime so heavier layers
# stay cached; the numpy==2.4.6 pin above is preserved (datasets 3.x accepts numpy 2.x).
RUN pip install --no-cache-dir "datasets>=3.0,<4.0"

# microWakeWord's SUBPACKAGES (microwakeword.audio for extract_features.py; microwakeword.layers
# for the training entrypoint: model_train_eval -> utils -> layers; possibly others) are NOT
# shipped by the pip package: those dirs have no __init__.py, so the package's find_packages()
# skips them and pip installs only the TOP-LEVEL modules (data/mixednet/model_train_eval/utils/...).
# At runtime they load fine as implicit namespace subpackages once the source is present, and their
# deps are already installed transitively above. Vendor them ALL in one shot by merging the pinned
# repo's microwakeword/ tree into the installed package — cp -rn adds the missing subdirs without
# clobbering pip's own files. SITE is resolved from WORKDIR (not the clone) so it points at
# site-packages. Placed late so the heavy torch/piper pip layers above stay cached.
RUN git clone --quiet https://github.com/kahrendt/microWakeWord /tmp/mww \
    && git -C /tmp/mww checkout --quiet ${MICROWAKEWORD_SHA} \
    && SITE="$(python -c 'import microwakeword, os; print(os.path.dirname(microwakeword.__file__))')" \
    && cp -rn /tmp/mww/microwakeword/. "$SITE/" \
    && rm -rf /tmp/mww \
    && python -c 'from microwakeword.audio.augmentation import Augmentation; from microwakeword.audio.clips import Clips; from microwakeword.audio.spectrograms import SpectrogramGeneration; from microwakeword.layers import modes, stream, strided_drop; print("microwakeword subpackages vendored OK")'

# The LibriTTS-R generator weights (~200 MB, same v2.0.0 release asset the microWakeWord
# notebook itself downloads) are deliberately NOT baked into the image here — they are
# fetched once into the persistent /data mount by generate_samples.sh, so a container
# rebuild never re-downloads them.

COPY generate_samples.sh /opt/wakeword/generate_samples.sh
COPY download_negatives.sh /opt/wakeword/download_negatives.sh
COPY download_background_audio.py /opt/wakeword/download_background_audio.py
COPY extract_features.py /opt/wakeword/extract_features.py
COPY train.sh /opt/wakeword/train.sh
COPY build_manifest.py /opt/wakeword/build_manifest.py
COPY training_parameters.yaml /opt/wakeword/training_parameters.yaml.template
COPY run_all.sh /opt/wakeword/run_all.sh

# Defensive: strip any CRLF this repo's files may carry from being authored on Windows —
# a stray \r on a shebang line breaks "bad interpreter" in Linux (same fix applied in
# services/wyoming_whisper_gpu/Dockerfile for the same reason).
RUN sed -i 's/\r$//' /opt/wakeword/*.sh /opt/wakeword/*.py /opt/wakeword/*.template \
    && chmod +x /opt/wakeword/*.sh

VOLUME ["/data"]
WORKDIR /data

ENTRYPOINT []
CMD ["/opt/wakeword/run_all.sh"]
