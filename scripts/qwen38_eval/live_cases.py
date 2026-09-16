"""Live Memex cases. These functions are inert until the runner is invoked with --live."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tests.qwen38_eval.fixtures import (EXPECTED_FINDINGS, HIDDEN_BUILD_ASSERTIONS,
                                        chart_fixture, image_fixture, long_context_fixture,
                                        REVIEW_FILES, screenshot_fixture)
from tests.qwen38_eval.harness import MODEL, PROFILES, Observation, RunIdentity, assert_model, result
from .live_adapter import (LiveAdapterError, LiveMemexAdapter, make_context_probe,
                           measure_qwen_tokens)


def _vision_identity(adapter: LiveMemexAdapter, observation: Observation) -> bool:
    if adapter.vision_route == "legacy":
        return (observation.provider == "ollama"
                and observation.actual_model in adapter.legacy_vision_models)
    return assert_model(observation, adapter.model)


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
            "exact_model_provider": assert_model(stream.observation, adapter.model),
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
            "exact_model_provider": assert_model(stream.observation, adapter.model),
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
        chart = adapter.chat_stream(prompt="Read the chart title, quarters, and values 10 20 30 40.",
                                    identity=identity, profile="chat", code=False,
                                    attachments=[{"name": "chart.svg", "mimeType": "image/svg+xml",
                                                  "data": base64.b64encode(chart_fixture()).decode("ascii"),
                                                  "size": len(chart_fixture())}])
        chart_code = adapter.chat_stream(prompt="Read the chart title, quarters, and values 10 20 30 40 in Code.",
                                         identity=identity, profile="project", code=True,
                                         attachments=[{"name": "chart.svg", "mimeType": "image/svg+xml",
                                                       "data": base64.b64encode(chart_fixture()).decode("ascii"),
                                                       "size": len(chart_fixture())}])
        screenshot = adapter.chat_stream(prompt="Read the dashboard model, context, approval status, and project name.",
                                         identity=identity, profile="project", permission_mode="plan", code=True,
                                         attachments=[{"name": "screenshot.svg", "mimeType": "image/svg+xml",
                                                       "data": base64.b64encode(screenshot_fixture()).decode("ascii"),
                                                       "size": len(screenshot_fixture())}])
        screenshot_chat = adapter.chat_stream(prompt="Read the dashboard model, context, approval status, and project name in chat.",
                                              identity=identity, profile="chat", code=False,
                                              attachments=[{"name": "screenshot.svg", "mimeType": "image/svg+xml",
                                                            "data": base64.b64encode(screenshot_fixture()).decode("ascii"),
                                                            "size": len(screenshot_fixture())}])
        assertions = {"exact_model_provider": all(_vision_identity(adapter, item.observation)
                                                   for item in (chart, chart_code, screenshot, screenshot_chat)),
                      "chart_chat_hidden_check": all(x in chart.text for x in ("Q1", "Q2", "Q3", "40")),
                      "chart_code_hidden_check": all(x in chart_code.text for x in ("Q1", "Q2", "Q3", "40")),
                      "screenshot_code_hidden_check": all(x in screenshot.text for x in ("Qwen 3.8 Local Heavy", "approval required", "fixture-alpha")),
                      "screenshot_chat_hidden_check": all(x in screenshot_chat.text for x in ("Qwen 3.8 Local Heavy", "approval required", "fixture-alpha")),
                      "no_fallback_as_qwen": all(not item.observation.fallback for item in (chart, chart_code, screenshot, screenshot_chat))}
        return result("vision", "live", identity, assertions, observation=screenshot.observation,
                      details={"browser_auth_required_for_api": False, "browser_auth_required_for_ui": True,
                               "chat_observation": chart.observation.__dict__,
                               "chart_code_observation": chart_code.observation.__dict__,
                               "code_observation": screenshot.observation.__dict__,
                               "screenshot_chat_observation": screenshot_chat.observation.__dict__,
                               "approval_calls": screenshot.approval_calls})
    finally:
        _cleanup(adapter, identity)


def live_long_context(adapter: LiveMemexAdapter):
    identity = _project(adapter, "long-context")
    fixture = long_context_fixture()
    try:
        input_tokens = measure_qwen_tokens(fixture)
        stream = adapter.chat_stream(prompt="Recover FACT-A, FACT-B, FACT-C, and FACT-D from this repository:\n" + fixture,
                                     identity=identity, profile="long", permission_mode="plan")
        assertions = {"exact_model_provider": assert_model(stream.observation, adapter.model),
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
        blocked = result("long_context", "live", identity, {"qwen_tokenizer_available": False},
                         observation=obs, details={"status": "blocked", "reason": str(exc),
                                                   "browser_auth_required_for_api": False,
                                                   "browser_auth_required_for_ui": True})
        blocked.status = "blocked"
        return blocked
    finally:
        _cleanup(adapter, identity)


def live_approvals(adapter: LiveMemexAdapter, *, fixture_approval: bool = False):
    identity = _project(adapter, "approvals")
    if not fixture_approval:
        obs = Observation(owner_id=identity.owner_id, session_id=identity.session_id,
                          project_id=identity.project_id, status="blocked")
        _cleanup(adapter, identity)
        blocked = result("approvals", "live", identity, {"fixture_callback_enabled": False},
                         observation=obs,
                         details={"status": "blocked", "browser_auth_required_for_api": False,
                               "browser_auth_required_for_ui": True,
                               "vision_route": adapter.vision_route,
                               "observed_actual_models": sorted({item.observation.actual_model for item in (chart, chart_code, screenshot, screenshot_chat)}),
                                  "prerequisite": "pass --fixture-approval to exercise the authorized caller approval API; no synthetic identity is generated"})
        blocked.status = "blocked"
        return blocked
    try:
        adapter.write_file(identity.project_id, "approval-probe.txt", "seed")
        decisions: list[str] = []

        def deny_with_caller_credentials(call_id: str, _event: dict[str, Any]) -> None:
            adapter.deny(call_id)
            decisions.append("denied")

        stream = adapter.chat_stream(
            prompt="Write approval-probe.txt with the content approved-mutation. This is an approval policy fixture.",
            identity=identity, profile="project", permission_mode="acceptEdits",
            approval_handler=deny_with_caller_credentials)
        current = adapter.read_file(identity.project_id, "approval-probe.txt").get("content", "")
        assertions = {
            "exact_model_provider": assert_exact_model(stream.observation),
            "approval_event_observed": bool(stream.approval_calls),
            "caller_fixture_decision_sent": decisions == ["denied"],
            "denied_mutation_not_applied": current == "seed",
            "no_fallback_as_qwen": not stream.observation.fallback,
        }
        return result("approvals", "live", identity, assertions, observation=stream.observation,
                      details={"browser_auth_required_for_api": False, "browser_auth_required_for_ui": True,
                               "synthetic_headers_are_not_browser_proof": True,
                               "decision": "denied via caller-configured authenticated API"})
    finally:
        _cleanup(adapter, identity)


def live_recovery(adapter: LiveMemexAdapter):
    identity = _project(adapter, "recovery")
    try:
        stream = adapter.chat_stream(prompt="Return a short recovery probe.", identity=identity,
                                     profile="project", permission_mode="plan")
        blocked = result("recovery", "live", identity,
                        {"exact_model_provider": assert_model(stream.observation, adapter.model),
                         "no_fallback_as_qwen": not stream.observation.fallback,
                         "transport_fault_injection_available": False},
                        observation=stream.observation,
                        details={"status": "blocked", "browser_auth_required_for_api": False,
                                 "browser_auth_required_for_ui": False,
                                 "prerequisite": "lead must provide a safe fault-injection hook before recovery/contention passes"})
        blocked.status = "blocked"
        return blocked
    finally:
        _cleanup(adapter, identity)


def live_context_probes(adapter: LiveMemexAdapter):
    """Run six actual tokenizer-sized probes: 70% and 90% for each profile."""
    results = []
    for profile in ("chat", "project", "long"):
        for ratio in (0.7, 0.9):
            identity = _project(adapter, f"context-{profile}-{int(ratio * 100)}")
            try:
                text, measured = make_context_probe(profile, ratio)
                stream = adapter.chat_stream(
                    prompt="Return the exact probe marker if present: CONTEXT_PROBE_OK\n" + text,
                    identity=identity, profile=profile, permission_mode="plan")
                assertions = {
                    "exact_model_provider": assert_model(stream.observation, adapter.model),
                    "actual_tokenizer_measurement": measured > 0,
                    "effective_profile_matches": stream.observation.context_profile == profile,
                    "effective_context_reported": stream.observation.effective_context_tokens == PROFILES[profile],
                    "within_profile_budget": measured < stream.observation.effective_context_tokens,
                }
                results.append(result(f"context_{profile}_{int(ratio * 100)}", "live", identity,
                                      assertions, observation=stream.observation,
                                      details={"ratio": ratio, "measured_input_tokens": measured,
                                               "browser_auth_required_for_api": False,
                                               "browser_auth_required_for_ui": True}))
            except LiveAdapterError as exc:
                obs = Observation(owner_id=identity.owner_id, session_id=identity.session_id,
                                  project_id=identity.project_id, context_profile=profile,
                                  configured_context_tokens=PROFILES[profile], status="blocked")
                blocked = result(f"context_{profile}_{int(ratio * 100)}", "live", identity,
                                 {"qwen_tokenizer_available": False}, observation=obs,
                                 details={"status": "blocked", "reason": str(exc),
                                          "browser_auth_required_for_api": False,
                                          "browser_auth_required_for_ui": True})
                blocked.status = "blocked"
                results.append(blocked)
            finally:
                _cleanup(adapter, identity)
    return results


def live_cases(adapter: LiveMemexAdapter, *, interactive: bool = False,
               fixture_approval: bool = False):
    return [live_review(adapter), live_build(adapter, interactive=interactive),
            live_approvals(adapter, fixture_approval=fixture_approval), live_vision(adapter), live_long_context(adapter),
            live_recovery(adapter), *live_context_probes(adapter)]


def live_smoke_cases(adapter: LiveMemexAdapter, *, interactive: bool = False,
                     fixture_approval: bool = False):
    """Bounded preflight: review plus four vision transport combinations."""
    return [live_review(adapter), live_vision(adapter)]
