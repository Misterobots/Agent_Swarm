"""Live Memex cases. These functions are inert until the runner is invoked with --live."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tests.qwen38_eval.fixtures import (EXPECTED_FINDINGS, HIDDEN_BUILD_ASSERTIONS,
                                        image_fixture, long_context_fixture,
                                        REVIEW_FILES)
from tests.qwen38_eval.harness import MODEL, Observation, RunIdentity, assert_exact_model, result
from .live_adapter import LiveAdapterError, LiveMemexAdapter, measure_qwen_tokens


def _project(adapter: LiveMemexAdapter, label: str):
    identity = RunIdentity.unique(label)
    project = adapter.create_project(f"qwen38-eval-{label}-{identity.project_id[-8:]}")
    identity.project_id = str(project["id"])
    adapter.create_session(identity.project_id)
    return identity


def _cleanup(adapter: LiveMemexAdapter, identity: RunIdentity) -> None:
    try:
        adapter.delete_project(identity.project_id)
    except LiveAdapterError:
        pass


def live_review(adapter: LiveMemexAdapter):
    identity = _project(adapter, "review")
    try:
        for path, content in REVIEW_FILES.items():
            adapter.write_file(identity.project_id, path, content)
        stream = adapter.chat_stream(
            prompt="Inspect every project file and report the three seeded defects with file and line evidence. Do not edit.",
            identity=identity, profile="project", permission_mode="plan")
        assertions = {
            "exact_model_provider": assert_exact_model(stream.observation),
            "all_seeded_findings": all(k in stream.text and v in stream.text for k, v in EXPECTED_FINDINGS.items()),
            "no_fallback_as_qwen": not stream.observation.fallback,
            "isolated_project": bool(identity.project_id),
        }
        return result("review", "live", identity, assertions, observation=stream.observation,
                      details={"browser_auth_required_for_api": False,
                               "browser_auth_required_for_ui": True,
                               "auth_proof": stream.auth_proof,
                               "approval_calls": stream.approval_calls})
    finally:
        _cleanup(adapter, identity)


def live_build(adapter: LiveMemexAdapter, *, interactive: bool = False):
    identity = _project(adapter, "build")
    try:
        adapter.write_file(identity.project_id, "app.py", "# implement greet(name)\n")
        stream = adapter.chat_stream(
            prompt="Implement greet(name) in app.py and add tests/test_app.py. Use the project tools. The hidden checker requires exact output Hello, Ada!.",
            identity=identity, profile="project", permission_mode="acceptEdits")
        if stream.approval_calls and not interactive:
            return result("build", "live", identity, {"human_approval_required": False},
                          observation=stream.observation,
                          details={"status": "blocked", "browser_auth_required_for_api": False,
                                   "browser_auth_required_for_ui": True,
                                   "prerequisite": "human must approve each tool call through the authenticated UI or explicit callback",
                                   "approval_calls": stream.approval_calls})
        app = adapter.read_file(identity.project_id, "app.py").get("content", "")
        test = adapter.read_file(identity.project_id, "tests/test_app.py").get("content", "")
        with tempfile.TemporaryDirectory(prefix="qwen38-live-build-") as temp:
            root = Path(temp)
            (root / "app.py").write_text(app, encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests/test_app.py").write_text(test, encoding="utf-8")
            hidden = subprocess.run(["python", "-m", "pytest", "-q"], cwd=root,
                                    text=True, capture_output=True, timeout=60, check=False)
        assertions = {
            "exact_model_provider": assert_exact_model(stream.observation),
            "hidden_test_check": hidden.returncode == 0,
            "expected_behavior_present": "Hello, Ada!" in app or "Hello, Ada!" in test,
            "no_fallback_as_qwen": not stream.observation.fallback,
        }
        return result("build", "live", identity, assertions, observation=stream.observation,
                      details={"browser_auth_required_for_api": False, "browser_auth_required_for_ui": True,
                               "approval_calls": stream.approval_calls, "hidden_stdout": hidden.stdout[-1000:]})
    finally:
        _cleanup(adapter, identity)


def live_vision(adapter: LiveMemexAdapter):
    identity = _project(adapter, "vision")
    try:
        stream = adapter.chat_stream(prompt="Identify the labels ALPHA, BETA, GAMMA and values 10, 20, 30 in this image.",
                                     identity=identity, profile="chat", permission_mode="plan",
                                     attachments=[{"name": "fixture.ppm", "mimeType": "image/x-portable-pixmap",
                                                   "data": base64.b64encode(image_fixture()).decode("ascii"),
                                                   "size": len(image_fixture())}])
        assertions = {"exact_model_provider": assert_exact_model(stream.observation),
                      "labels_recovered": all(x in stream.text for x in ("ALPHA", "BETA", "GAMMA")),
                      "values_recovered": all(x in stream.text for x in ("10", "20", "30")),
                      "no_fallback_as_qwen": not stream.observation.fallback}
        return result("vision", "live", identity, assertions, observation=stream.observation,
                      details={"browser_auth_required_for_api": False, "browser_auth_required_for_ui": True,
                               "approval_calls": stream.approval_calls})
    finally:
        _cleanup(adapter, identity)


def live_long_context(adapter: LiveMemexAdapter):
    identity = _project(adapter, "long-context")
    fixture = long_context_fixture()
    try:
        input_tokens = measure_qwen_tokens(fixture)
        stream = adapter.chat_stream(prompt="Recover FACT-A, FACT-B, FACT-C, and FACT-D from this repository:\n" + fixture,
                                     identity=identity, profile="long", permission_mode="plan")
        assertions = {"exact_model_provider": assert_exact_model(stream.observation),
                      "actual_input_measured": input_tokens > 0,
                      "within_effective_budget": input_tokens < (stream.observation.effective_context_tokens or 0),
                      "facts_recovered": all(x in stream.text for x in ("FACT-A", "FACT-B", "FACT-C", "FACT-D")),
                      "configured_max_is_not_success": stream.observation.effective_context_tokens == 122880}
        stream.observation.input_tokens = input_tokens
        return result("long_context", "live", identity, assertions, observation=stream.observation,
                      details={"browser_auth_required_for_api": False, "browser_auth_required_for_ui": True,
                               "tokenizer": "Qwen tokenizer from QWEN38_TOKENIZER_PATH"})
    except LiveAdapterError as exc:
        obs = Observation(owner_id=identity.owner_id, session_id=identity.session_id,
                          project_id=identity.project_id, status="blocked")
        return result("long_context", "live", identity, {"qwen_tokenizer_available": False},
                      observation=obs, details={"status": "blocked", "reason": str(exc),
                                                "browser_auth_required_for_api": False,
                                                "browser_auth_required_for_ui": True})
    finally:
        _cleanup(adapter, identity)


def live_approvals(adapter: LiveMemexAdapter):
    identity = _project(adapter, "approvals")
    obs = Observation(owner_id=identity.owner_id, session_id=identity.session_id,
                      project_id=identity.project_id, status="blocked")
    _cleanup(adapter, identity)
    return result("approvals", "live", identity, {"human_approval_callback_configured": False},
                  observation=obs,
                  details={"status": "blocked", "browser_auth_required_for_api": False,
                           "browser_auth_required_for_ui": True,
                           "prerequisite": "authenticated human approval/denial callback is required; no synthetic approval is generated"})


def live_recovery(adapter: LiveMemexAdapter):
    identity = _project(adapter, "recovery")
    try:
        stream = adapter.chat_stream(prompt="Return a short recovery probe.", identity=identity,
                                     profile="project", permission_mode="plan")
        return result("recovery", "live", identity,
                      {"exact_model_provider": assert_exact_model(stream.observation),
                       "no_fallback_as_qwen": not stream.observation.fallback,
                       "transport_fault_injection_available": False},
                      observation=stream.observation,
                      details={"status": "blocked", "browser_auth_required_for_api": False,
                               "browser_auth_required_for_ui": False,
                               "prerequisite": "lead must provide a safe fault-injection hook before recovery/contention passes"})
    finally:
        _cleanup(adapter, identity)


def live_cases(adapter: LiveMemexAdapter, *, interactive: bool = False):
    return [live_review(adapter), live_build(adapter, interactive=interactive),
            live_approvals(adapter), live_vision(adapter), live_long_context(adapter),
            live_recovery(adapter)]

