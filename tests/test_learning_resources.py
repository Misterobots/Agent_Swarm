"""Fail-closed resource admission tests; no hardware or host access."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from learning_resources import (  # noqa: E402
    GPUObservation,
    ResourceManifest,
    ResourcePolicyError,
    admit_gpu,
)


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
GPU = "GPU-memex-16-a"


def manifest(**overrides):
    value = {
        "manifest_version": "2026-09-13-test-1",
        "allowed_hosts": ["memex-lovelace"],
        "gpus": [{"uuid": GPU, "host_id": "memex-lovelace", "enabled": True}],
        "allowed_consumers": ["memex:ollama", "memex:training"],
        "protected_consumer_patterns": ["saltmedia:*", "saltbox:*"],
        "max_telemetry_age_seconds": 30,
        "min_free_memory_bytes": 8,
    }
    value.update(overrides)
    return ResourceManifest.from_mapping(value)


def observation(**overrides):
    value = {
        "host_id": "memex-lovelace",
        "gpu_uuid": GPU,
        "total_memory_bytes": 16,
        "free_memory_bytes": 12,
        "telemetry_at": NOW,
        "consumers": ["memex:ollama"],
    }
    value.update(overrides)
    return GPUObservation.from_mapping(value)


def test_admits_only_explicitly_owned_fresh_gpu():
    decision = admit_gpu(manifest(), observation(), now=NOW)
    assert decision.eligible is True
    assert decision.code == "eligible"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"host_id": "unknown-host"}, "unknown_host"),
        ({"gpu_uuid": "GPU-unknown"}, "unknown_gpu"),
        ({"consumers": ["saltmedia:transcoder"]}, "protected_consumer"),
        ({"consumers": ["unknown:consumer"]}, "unknown_consumer"),
        ({"telemetry_at": NOW - timedelta(seconds=31)}, "stale_telemetry"),
        ({"free_memory_bytes": 7}, "insufficient_free_memory"),
    ],
)
def test_admission_fails_closed(change, code):
    decision = admit_gpu(manifest(), observation(**change), now=NOW)
    assert decision.eligible is False
    assert decision.code == code


def test_explicit_denied_gpu_wins_over_other_checks():
    decision = admit_gpu(
        manifest(denied_gpu_uuids=[GPU]),
        observation(),
        now=NOW,
    )
    assert decision.code == "protected_gpu"


def test_manifest_rejects_gpu_on_unlisted_host():
    with pytest.raises(ResourcePolicyError):
        manifest(gpus=[{"uuid": GPU, "host_id": "saltmedia-host", "enabled": True}])


def test_no_most_free_or_index_fallback_exists():
    decision = admit_gpu(
        manifest(gpus=[{"uuid": GPU, "host_id": "memex-lovelace", "enabled": False}]),
        observation(),
        now=NOW,
    )
    assert decision.code == "gpu_disabled"


@pytest.mark.parametrize("enabled", ["false", "true", 1, None])
def test_manifest_rejects_non_boolean_lane_enablement(enabled):
    with pytest.raises(ResourcePolicyError):
        manifest(gpus=[{"uuid": GPU, "host_id": "memex-lovelace", "enabled": enabled}])


@pytest.mark.parametrize("consumers", [None, "", "memex:ollama", [""]])
def test_observation_rejects_unknown_consumer_inventory(consumers):
    with pytest.raises(ResourcePolicyError):
        observation(consumers=consumers)


def test_request_cannot_lower_manifest_memory_floor():
    decision = admit_gpu(
        manifest(), observation(free_memory_bytes=7), now=NOW, min_free_memory_bytes=0,
    )
    assert decision.code == "insufficient_free_memory"
