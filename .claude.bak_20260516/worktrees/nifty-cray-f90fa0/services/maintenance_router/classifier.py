"""Manifest loading + alert classification.

The manifest (config/maintenance/manifest.yaml) is the single source of truth
mapping Prometheus alert names to repair actions. Routing rules:

  1. The first rule whose `alert` matches the alertname AND whose `match`
     labels are all satisfied wins.
  2. If `agent_safe: true` AND `action` is set AND not in cooldown → "agent".
  3. Otherwise → "human" (or "suppressed_cooldown" if agent path was blocked
     only by cooldown).
  4. No matching rule → "unmatched" → human queue.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import yaml

from .models import AlertmanagerAlert, Decision, ManifestRule

logger = logging.getLogger(__name__)


class CooldownStore(Protocol):
    """Anything that can answer 'how many seconds left on this cooldown'.

    Production: Redis-backed (TTL key per (action, args_hash)). Tests: in-memory.
    """

    def remaining(self, key: str) -> int: ...
    def set(self, key: str, ttl_seconds: int) -> None: ...


def cooldown_key(action: str, action_args: dict[str, str]) -> str:
    if not action_args:
        return f"cooldown:{action}"
    args = ",".join(f"{k}={v}" for k, v in sorted(action_args.items()))
    return f"cooldown:{action}:{args}"


class Classifier:
    def __init__(self, manifest_path: Path | str, cooldowns: CooldownStore):
        self.manifest_path = Path(manifest_path)
        self.cooldowns = cooldowns
        self._rules: list[ManifestRule] = []
        self._defaults: dict = {}
        self.reload()

    def reload(self) -> None:
        raw = yaml.safe_load(self.manifest_path.read_text())
        if not raw or raw.get("version") != 1:
            raise ValueError(f"manifest version must be 1, got {raw and raw.get('version')!r}")
        self._defaults = raw.get("defaults", {}) or {}
        rules: list[ManifestRule] = []
        for i, rule in enumerate(raw.get("rules") or []):
            merged = {**self._defaults, **rule}
            try:
                rules.append(ManifestRule(**merged))
            except Exception as exc:
                raise ValueError(f"manifest rule #{i} invalid: {exc}") from exc
        self._rules = rules
        logger.info("manifest loaded: %d rules from %s", len(rules), self.manifest_path)

    def classify(self, alert: AlertmanagerAlert) -> Decision:
        alertname = alert.labels.get("alertname")
        if not alertname:
            return Decision(route="unmatched", blast_radius="medium")

        matched_index, matched_rule = self._first_match(alertname, alert.labels)
        if matched_rule is None:
            return Decision(route="unmatched", blast_radius="medium")

        if not matched_rule.agent_safe or not matched_rule.action:
            return Decision(
                route="human",
                rule_index=matched_index,
                agent_safe=False,
                blast_radius=matched_rule.blast_radius,
                runbook=matched_rule.runbook,
            )

        # Agent-safe path: cooldown gate.
        key = cooldown_key(matched_rule.action, matched_rule.action_args)
        remaining = self.cooldowns.remaining(key)
        if remaining > 0:
            return Decision(
                route="suppressed_cooldown",
                rule_index=matched_index,
                action=matched_rule.action,
                action_args=matched_rule.action_args,
                agent_safe=True,
                blast_radius=matched_rule.blast_radius,
                cooldown_seconds=matched_rule.cooldown_seconds,
                cooldown_remaining_seconds=remaining,
            )

        return Decision(
            route="agent",
            rule_index=matched_index,
            action=matched_rule.action,
            action_args=matched_rule.action_args,
            agent_safe=True,
            blast_radius=matched_rule.blast_radius,
            cooldown_seconds=matched_rule.cooldown_seconds,
        )

    def mark_dispatched(self, decision: Decision) -> None:
        """Call after a successful agent dispatch to start the cooldown."""
        if decision.route != "agent" or not decision.action:
            return
        self.cooldowns.set(
            cooldown_key(decision.action, decision.action_args),
            decision.cooldown_seconds,
        )

    def _first_match(
        self, alertname: str, labels: dict[str, str]
    ) -> tuple[int | None, ManifestRule | None]:
        for i, rule in enumerate(self._rules):
            if rule.alert != alertname:
                continue
            if all(labels.get(k) == v for k, v in rule.match.items()):
                return i, rule
        return None, None
