"""Focused tests for the Qwen 3.8 role snapshot contract."""

from types import SimpleNamespace

import pytest

import role_model_resolver as resolver
import team_builder
from coordination import session as session_module
from coordination.session import CoordinatorSession


def test_snapshot_is_owner_scoped_and_preserves_swarm_architect_default(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "get_model_for_role",
        lambda uid, role, default=None: "qwen3.8:27b" if role == "coder" else default,
    )

    snapshot = resolver.snapshot_role_models("owner-a")

    assert snapshot.owner_id == "owner-a"
    assert snapshot.for_role("coder").requested_model == "qwen3.8:27b"
    assert snapshot.for_role("architect").requested_model == resolver.SWARM_ARCHITECT_MODEL
    assert snapshot.for_role("technical").requested_model == resolver.RESEARCHER_MODEL
    with pytest.raises(TypeError):
        snapshot.models["coder"] = snapshot.for_role("coder")


def test_role_snapshot_checkpoint_survives_team_builder_change(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)
    first = resolver.RoleModelSnapshot(
        "owner-a",
        {
            "coder": resolver.RoleModelBinding("qwen3.8:27b", "qwen3.8:27b"),
            "researcher": resolver.RoleModelBinding("qwen3:14b", "qwen3:14b"),
        },
    )
    second = resolver.RoleModelSnapshot(
        "owner-a",
        {
            "coder": resolver.RoleModelBinding("gemma4:31b", "gemma4:31b"),
            "researcher": resolver.RoleModelBinding("qwen3:8b", "qwen3:8b"),
        },
    )
    calls = iter([first, second])
    monkeypatch.setattr(session_module, "snapshot_role_models", lambda uid: next(calls))

    session1 = CoordinatorSession("session-a", "owner-a", coordination_id="coord-a")
    worker_id = session1.register_worker("technical", "inspect", "research")
    assert session1.model_for_role("coder") == "qwen3.8:27b"
    assert session1.workers[worker_id].model_binding.requested_model == "qwen3:14b"

    session2 = CoordinatorSession("session-a", "owner-a", coordination_id="coord-a")
    assert session2.model_for_role("coder") == "qwen3.8:27b"
    assert session2.model_for_role("researcher") == "qwen3:14b"


def test_actual_model_metadata_can_record_provider_fallback():
    snapshot = resolver.RoleModelSnapshot(
        "owner-a",
        {"coder": resolver.RoleModelBinding("qwen3.8:27b", "qwen3.8:27b")},
    )
    fallback = snapshot.with_actual_model(
        "coder", "qwen3:14b", provider="ollama", fallback=True,
    )

    assert fallback.for_role("coder").to_dict() == {
        "requested_model": "qwen3.8:27b",
        "actual_model": "qwen3:14b",
        "provider": "ollama",
        "fallback": True,
    }
    assert snapshot.for_role("coder").actual_model == "qwen3.8:27b"


def test_team_vram_advisory_counts_unique_large_models(monkeypatch):
    specs = {
        "qwen3.8:27b": SimpleNamespace(vram_gb=17.0),
        "gemma4:31b": SimpleNamespace(vram_gb=17.0),
    }
    monkeypatch.setattr(
        "model_registry.validate_role_model",
        lambda role, model: (True, ""),
    )
    monkeypatch.setattr("model_registry.get_model", specs.get)

    one_model = {role: "qwen3.8:27b" for role in team_builder.VALID_ROLES}
    valid, errors, warnings = team_builder.validate_team_config(one_model)
    assert valid and not errors
    assert not any("multiple large models" in warning for warning in warnings)

    two_models = dict(one_model)
    two_models["verifier"] = "gemma4:31b"
    _, _, warnings = team_builder.validate_team_config(two_models)
    assert any("multiple large models" in warning for warning in warnings)
