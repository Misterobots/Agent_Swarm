from __future__ import annotations

from .cases import all_cases
from .harness import DeterministicProvider


def test_all_six_cases_pass_in_explicit_mock_mode():
    results = all_cases(DeterministicProvider(), mode="mock")
    assert [r.name for r in results] == ["review", "build", "approvals", "vision", "long_context", "recovery"]
    assert all(r.passed for r in results), [r.details for r in results if not r.passed]


def test_mock_results_are_marked_as_mock_and_never_live_evidence():
    result = all_cases(DeterministicProvider(), mode="mock")[0]
    assert result.mode == "mock"
    assert result.authority == "hidden deterministic assertions"
    assert result.observation.provider == "ollama"
    assert result.observation.actual_model == "qwen3.8:27b"
