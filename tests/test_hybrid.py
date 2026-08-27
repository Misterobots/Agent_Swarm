"""Opt-in ModelScope/Transformers hybrid-model smoke test.

The model download is intentionally never performed during normal pytest
collection. Set ``RUN_MODELSCOPE_TESTS=1`` to run this network- and
GPU-dependent check explicitly.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


if os.getenv("RUN_MODELSCOPE_TESTS", "").lower() not in {"1", "true", "yes"}:
    pytest.skip(
        "ModelScope hybrid-model smoke test is opt-in; set RUN_MODELSCOPE_TESTS=1",
        allow_module_level=True,
    )

snapshot_download = pytest.importorskip("modelscope.hub.snapshot_download").snapshot_download
transformers = pytest.importorskip("transformers")


def test_hybrid_model_loads():
    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    model_dir = snapshot_download(model_id)
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    model = transformers.AutoModel.from_pretrained(model_dir, trust_remote_code=True)
    assert tokenizer is not None
    assert model is not None
