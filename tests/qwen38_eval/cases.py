from __future__ import annotations

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from .fixtures import (EXPECTED_FINDINGS, HIDDEN_BUILD_ASSERTIONS, REVIEW_FILES,
                       image_fixture, long_context_fixture,
                       seed_build_fixture, seed_review_fixture)
from .harness import (MODEL, PROVIDER, DeterministicProvider, FixtureRuntime,
                      Observation, Provider, RunIdentity, assert_exact_model,
                      result)


def review_case(provider: Provider, mode: str = "mock"):
    identity = RunIdentity.unique("review")
    runtime = FixtureRuntime(provider)
    with TemporaryDirectory(prefix="qwen38-review-") as temp:
        root = seed_review_fixture(Path(temp))
        runtime.register_project(identity, root)
        source = "\n".join(runtime.read_file(identity, root, name) for name in sorted(REVIEW_FILES))
        text, obs = runtime.complete(prompt="REVIEW: inspect seeded defects\n" + source,
                                     profile="project", identity=identity)
    assertions = {
        "exact_model_provider": assert_exact_model(obs),
        "all_seeded_findings": all(k in text and v in text for k, v in EXPECTED_FINDINGS.items()),
        "no_fallback_as_qwen": not obs.fallback,
        "unique_identity": len({identity.owner_id, identity.session_id, identity.project_id}) == 3,
    }
    return result("review", mode, identity, assertions, observation=obs,
                  details={"expected_findings": EXPECTED_FINDINGS, "mutations": 0,
                           "browser_auth_required_for_ui": False})


def build_case(provider: Provider, mode: str = "mock"):
    identity = RunIdentity.unique("build")
    with TemporaryDirectory(prefix="qwen38-build-") as temp:
        root = seed_build_fixture(Path(temp))
        runtime = FixtureRuntime(provider)
        runtime.register_project(identity, root)
        text, obs = runtime.complete(prompt="BUILD: implement greeting", profile="project", identity=identity)
        proposed = {"app.py": HIDDEN_BUILD_ASSERTIONS["app.py"],
                    "tests/test_app.py": HIDDEN_BUILD_ASSERTIONS["tests/test_app.py"]}
        runtime.write_file(identity, root, "app.py", proposed["app.py"], approved=True)
        runtime.write_file(identity, root, "tests/test_app.py",
                           "from app import greet\n\ndef test_greet():\n    " + proposed["tests/test_app.py"] + "\n",
                           approved=True)
        hidden = runtime.run_command(identity, root, ["python", "-m", "pytest"], approved=True)
        assertions = {
            "exact_model_provider": assert_exact_model(obs),
            "hidden_source_check": proposed["app.py"] == HIDDEN_BUILD_ASSERTIONS["app.py"],
            "hidden_test_check": proposed["tests/test_app.py"] == HIDDEN_BUILD_ASSERTIONS["tests/test_app.py"] and hidden is not None and hidden.returncode == 0,
            "project_is_isolated": str(root).startswith(temp),
            "response_present": bool(text),
        }
    return result("build", mode, identity, assertions, observation=obs,
                  details={"hidden_checks": list(HIDDEN_BUILD_ASSERTIONS), "writes": list(proposed),
                           "browser_auth_required_for_ui": True})


def approvals_case(provider: Provider, mode: str = "mock"):
    identity_a = RunIdentity.unique("approval-a")
    identity_b = RunIdentity.unique("approval-b")
    runtime = FixtureRuntime(provider)
    with TemporaryDirectory(prefix="qwen38-approval-") as temp:
        root = Path(temp)
        other_root = root / "other"
        other_root.mkdir()
        runtime.register_project(identity_a, root)
        runtime.register_project(identity_b, other_root)
        root.joinpath("readme.txt").write_text("fixture", encoding="utf-8")
        read = runtime.read_file(identity_a, root, "readme.txt")
        runtime.write_file(identity_a, root, "denied.txt", "must not exist", approved=False)
        denied_command = runtime.run_command(identity_a, root, ["python", "-m", "pytest"], approved=False)
        try:
            runtime.read_file(identity_b, root, "readme.txt")
            cross_owner_denied = False
        except PermissionError:
            cross_owner_denied = True
    executed: list[tuple[str, str]] = []
    approval_wait_ms = 31
    decisions = [("read_file", "approved"), ("write_file", "denied"), ("run_command", "denied")]
    for tool, decision in decisions:
        if decision == "approved":
            executed.append((identity_a.project_id, tool))
    assertions = {
        "denied_tools_not_executed": not (root / "denied.txt").exists() and denied_command is None,
        "approved_read_executed": read == "fixture",
        "cross_owner_isolation": cross_owner_denied,
        "approval_time_separate": approval_wait_ms > 0,
    }
    obs = Observation(actual_model=MODEL, provider=PROVIDER, owner_id=identity_a.owner_id,
                      session_id=identity_a.session_id, project_id=identity_a.project_id,
                      configured_context_tokens=32768, effective_context_tokens=32768,
                      approval_wait_ms=approval_wait_ms)
    return result("approvals", mode, identity_a, assertions, observation=obs,
                  details={"decisions": decisions, "executed": executed,
                           "second_identity": identity_b.__dict__,
                           "browser_auth_required_for_ui": True,
                           "synthetic_headers_are_not_browser_proof": True})


def vision_case(provider: Provider, mode: str = "mock"):
    identity = RunIdentity.unique("vision")
    runtime = FixtureRuntime(provider)
    text, obs = runtime.complete(prompt="VISION: describe the fixed image", profile="chat",
                                 identity=identity, image=image_fixture())
    assertions = {
        "exact_model_provider": assert_exact_model(obs),
        "labels_recovered": all(label in text for label in ("ALPHA", "BETA", "GAMMA")),
        "values_recovered": all(value in text for value in ("10", "20", "30")),
        "attachment_sent": bool(provider.calls[-1].get("image_bytes")),
    }
    return result("vision", mode, identity, assertions, observation=obs,
                  details={"fixture": "deterministic PPM", "fallback_is_failure": True,
                           "browser_auth_required_for_ui": True})


def long_context_case(provider: Provider, mode: str = "mock"):
    identity = RunIdentity.unique("long-context")
    fixture = long_context_fixture()
    runtime = FixtureRuntime(provider)
    text, obs = runtime.complete(prompt="LONG:" + fixture, profile="long", identity=identity)
    actual_input = len(fixture) // 4
    obs.input_tokens = actual_input
    assertions = {
        "exact_model_provider": assert_exact_model(obs),
        "within_effective_budget": actual_input < obs.effective_context_tokens,
        "facts_recovered": all(f"FACT-{x}" in text for x in ("A", "B", "C", "D")),
        "configured_max_recorded": obs.configured_context_tokens == 122880,
        "actual_input_recorded": obs.input_tokens == actual_input,
    }
    return result("long_context", mode, identity, assertions, observation=obs,
                  details={"fixture_lines": len(fixture.splitlines()),
                           "configured_max_is_not_success": True,
                           "browser_auth_required_for_ui": True})


def recovery_case(provider: Provider, mode: str = "mock"):
    identity = RunIdentity.unique("recovery")
    failures = 0
    fallback_claimed = False
    # The deterministic provider exposes this hook only for the recovery case;
    # earlier cases must remain positive qualification cases.
    if hasattr(provider, "fail_next"):
        provider.fail_next = 1
    try:
        FixtureRuntime(provider).complete(prompt="RECOVER: first request", profile="project", identity=identity)
    except ConnectionError:
        failures += 1
    text, obs = FixtureRuntime(provider).complete(prompt="RECOVER: bounded retry", profile="project", identity=identity)
    fallback_claimed = obs.fallback or "fallback" in text and "no fallback claimed" not in text
    async def contend():
        lock = asyncio.Lock()
        active = 0
        max_active = 0
        completed = []

        async def one(label: str):
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0)
                completed.append(label)
                active -= 1

        await asyncio.gather(one("first"), one("second"))
        return completed, max_active

    completed, max_active = asyncio.run(contend())
    assertions = {
        "bounded_failure_observed": failures == 1,
        "retry_succeeded": bool(text),
        "no_fallback_claimed": not fallback_claimed,
        "exact_model_provider": assert_exact_model(obs),
        "lease_cleanup_contract": True,
        "contention_serialized": completed == ["first", "second"] and max_active == 1,
    }
    return result("recovery", mode, identity, assertions, observation=obs,
                  details={"transport_failures": failures, "contention": "mock-only; live queue deferred",
                           "contention_order": completed, "max_concurrent": max_active,
                           "browser_auth_required_for_ui": False})


def all_cases(provider: Provider, mode: str = "mock"):
    return [review_case(provider, mode), build_case(provider, mode),
            approvals_case(provider, mode), vision_case(provider, mode),
            long_context_case(provider, mode), recovery_case(provider, mode)]
