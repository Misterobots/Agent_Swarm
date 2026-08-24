"""Opt-in ModelScope TTS pipeline smoke test."""

import os

import pytest


def test_modelscope_tts_pipeline_smoke():
    if os.getenv("RUN_OPTIONAL_MODELSCOPE_TESTS") != "1":
        pytest.skip("optional ModelScope test; set RUN_OPTIONAL_MODELSCOPE_TESTS=1")
    modelscope = pytest.importorskip("modelscope")
    pipeline = modelscope.pipelines.pipeline
    Tasks = modelscope.utils.constant.Tasks
    pipeline(task=Tasks.text_to_speech, model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
