"""Opt-in ModelScope/Transformers smoke test.

This test downloads a large model and is intentionally excluded from normal
suite runs unless explicitly enabled.
"""

import os

import pytest


def test_hybrid_modelscope_tts_smoke():
    if os.getenv("RUN_OPTIONAL_MODELSCOPE_TESTS") != "1":
        pytest.skip("optional ModelScope test; set RUN_OPTIONAL_MODELSCOPE_TESTS=1")
    snapshot_download = pytest.importorskip("modelscope.hub.snapshot_download").snapshot_download
    transformers = pytest.importorskip("transformers")

    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    model_dir = snapshot_download(model_id)
    transformers.AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    transformers.AutoModel.from_pretrained(model_dir, trust_remote_code=True)
