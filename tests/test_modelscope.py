"""Opt-in ModelScope text-to-speech pipeline smoke test."""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


if os.getenv("RUN_MODELSCOPE_TESTS", "").lower() not in {"1", "true", "yes"}:
    pytest.skip(
        "ModelScope pipeline smoke test is opt-in; set RUN_MODELSCOPE_TESTS=1",
        allow_module_level=True,
    )

modelscope = pytest.importorskip("modelscope")


def test_modelscope_tts_pipeline_loads():
    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    tts_pipeline = modelscope.pipelines.pipeline(
        task=modelscope.utils.constant.Tasks.text_to_speech,
        model=model_id,
    )
    assert tts_pipeline is not None
