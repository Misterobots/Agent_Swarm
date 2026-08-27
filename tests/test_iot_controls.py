import os
import sys
from unittest.mock import MagicMock

import pytest


WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

AGENTS_DIR = os.path.join(WORKSPACE_ROOT, "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)

def test_get_states_mock_returns_filtered_domain(monkeypatch):
    from agents.tools import iot_ops

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)

    lights_json = iot_ops.get_states("light")

    assert "light.studio_main" in lights_json
    assert "light.kitchen_strip" in lights_json
    assert "switch.3d_printer" not in lights_json


def test_call_service_mock_updates_entity_state(monkeypatch):
    from agents.tools import iot_ops

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)
    monkeypatch.setitem(
        iot_ops.MOCK_DB,
        "light.test_fixture",
        {"state": "off", "attributes": {"friendly_name": "Test Fixture"}},
    )

    result = iot_ops.call_service("light", "turn_on", "light.test_fixture", brightness=128)

    assert "SUCCESS" in result
    assert iot_ops.MOCK_DB["light.test_fixture"]["state"] == "on"
    assert iot_ops.MOCK_DB["light.test_fixture"]["attributes"]["brightness"] == 128


def test_sensitive_lock_control_should_require_confirmation(monkeypatch):
    from agents.tools import iot_ops

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)

    result = iot_ops.call_service("lock", "unlock", "lock.front_door")

    assert "confirmation" in result.lower()


def test_sensitive_lock_attempt_emits_audit_log(monkeypatch, caplog):
    from agents.tools import iot_ops

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)

    with caplog.at_level("INFO"):
        iot_ops.call_service("lock", "unlock", "lock.front_door")

    assert any("[IoT-AUDIT]" in message for message in caplog.messages)


def test_sensitive_action_metrics_increment(monkeypatch):
    from agents.tools import iot_ops

    total_metric = MagicMock()
    blocked_metric = MagicMock()
    monkeypatch.setattr(iot_ops, "IOT_SENSITIVE_ACTIONS_TOTAL", total_metric)
    monkeypatch.setattr(iot_ops, "IOT_SENSITIVE_ACTIONS_BLOCKED_TOTAL", blocked_metric)

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)

    iot_ops.call_service("lock", "unlock", "lock.front_door")

    total_metric.labels.assert_called_once_with(
        domain="lock",
        service="unlock",
        outcome="blocked_missing_confirmation",
    )
    total_metric.labels.return_value.inc.assert_called_once_with()
    blocked_metric.labels.assert_called_once_with(domain="lock", service="unlock")
    blocked_metric.labels.return_value.inc.assert_called_once_with()


def test_sensitive_lock_control_succeeds_after_confirmation(monkeypatch):
    from agents.tools import iot_ops

    monkeypatch.setattr(iot_ops, "MOCK_MODE", True)

    result = iot_ops.call_service("lock", "unlock", "lock.front_door", confirmed=True)

    assert "SUCCESS" in result
    assert iot_ops.MOCK_DB["lock.front_door"]["state"] == "unlocked"
