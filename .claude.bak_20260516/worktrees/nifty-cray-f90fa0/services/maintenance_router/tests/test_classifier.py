"""Classifier + manifest tests.

Uses the real production manifest at config/maintenance/manifest.yaml
(copied into tmp_path by the manifest_path fixture) so tests double as
manifest-validation tests.
"""

from __future__ import annotations

import yaml

from maintenance_router.classifier import Classifier, cooldown_key
from tests.conftest import InMemoryCooldowns, make_alert


def test_manifest_loads_with_real_rules(classifier):
    assert len(classifier._rules) > 0
    # All loaded rules must have an alert name.
    assert all(r.alert for r in classifier._rules)


def test_agent_safe_postgres_servicedown_routes_to_agent(classifier):
    alert = make_alert("ServiceDown", job="postgres", severity="critical")
    decision = classifier.classify(alert)
    assert decision.route == "agent"
    assert decision.action == "restart_container"
    assert decision.action_args == {"node": "hopper", "container": "postgres"}
    assert decision.agent_safe is True


def test_servicedown_unknown_job_falls_through_to_human_catchall(classifier):
    # The catch-all ServiceDown rule (agent_safe: false) handles unknown jobs.
    alert = make_alert("ServiceDown", job="some-other-service")
    decision = classifier.classify(alert)
    assert decision.route == "human"
    assert decision.agent_safe is False


def test_high_memory_routes_to_human(classifier):
    alert = make_alert("ContainerHighMemory", name="agent_runtime")
    decision = classifier.classify(alert)
    assert decision.route == "human"
    assert decision.runbook == "runbooks/high-memory.md"


def test_unknown_alert_routes_to_unmatched(classifier):
    alert = make_alert("SomeAlertNobodyDefined")
    decision = classifier.classify(alert)
    assert decision.route == "unmatched"


def test_alert_without_alertname_is_unmatched(classifier):
    from maintenance_router.models import AlertmanagerAlert
    alert = AlertmanagerAlert(status="firing", labels={}, annotations={})
    decision = classifier.classify(alert)
    assert decision.route == "unmatched"


def test_cooldown_blocks_second_dispatch(classifier, cooldowns):
    alert = make_alert("ServiceDown", job="postgres")

    first = classifier.classify(alert)
    assert first.route == "agent"
    classifier.mark_dispatched(first)

    second = classifier.classify(alert)
    assert second.route == "suppressed_cooldown"
    assert second.cooldown_remaining_seconds is not None
    assert second.cooldown_remaining_seconds > 0


def test_cooldown_expires_after_advance(classifier, cooldowns):
    alert = make_alert("ServiceDown", job="postgres")
    decision = classifier.classify(alert)
    classifier.mark_dispatched(decision)

    # Postgres rule has cooldown_seconds: 300. Advance past it.
    cooldowns.advance(301)

    decision_after = classifier.classify(alert)
    assert decision_after.route == "agent"


def test_cooldown_key_is_stable_across_arg_order():
    # The classifier sorts args, so key must be order-independent.
    a = cooldown_key("restart_container", {"node": "hopper", "container": "postgres"})
    b = cooldown_key("restart_container", {"container": "postgres", "node": "hopper"})
    assert a == b


def test_first_match_wins_for_servicedown_specific_before_catchall(classifier):
    # Specific (job=redis) should win over the catch-all ServiceDown rule.
    alert = make_alert("ServiceDown", job="redis")
    decision = classifier.classify(alert)
    assert decision.route == "agent"
    assert decision.action_args["container"] == "redis"


def test_invalid_manifest_version_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"version": 99, "rules": []}))
    cooldowns = InMemoryCooldowns()
    try:
        Classifier(bad, cooldowns)
    except ValueError as exc:
        assert "version must be 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_agent_safe_rule_without_action_fails_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({
        "version": 1,
        "rules": [{"alert": "X", "agent_safe": True}],  # missing 'action'
    }))
    # Pydantic accepts the rule (action is Optional in the model), but the
    # classifier should still treat it as non-agent at classify time because
    # action is None. So no exception at load — but classify routes to human.
    cooldowns = InMemoryCooldowns()
    classifier = Classifier(bad, cooldowns)
    alert = make_alert("X")
    decision = classifier.classify(alert)
    assert decision.route == "human"
