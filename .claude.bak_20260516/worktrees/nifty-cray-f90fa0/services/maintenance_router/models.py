"""Pydantic models for the maintenance router.

The Alertmanager webhook payload schema is documented at
https://prometheus.io/docs/alerting/latest/configuration/#webhook_config —
we model the subset we actually use.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Route = Literal["agent", "human", "suppressed_cooldown", "unmatched"]
QueueStatus = Literal["pending", "acked", "escalated", "resolved"]
BlastRadius = Literal["low", "medium", "high"]


class AlertmanagerAlert(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    fingerprint: str | None = None


class AlertmanagerWebhook(BaseModel):
    """The shape Alertmanager POSTs to a webhook receiver."""

    version: str | None = None
    groupKey: str | None = None
    status: Literal["firing", "resolved"]
    receiver: str | None = None
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str | None = None
    alerts: list[AlertmanagerAlert]


class ManifestRule(BaseModel):
    alert: str
    match: dict[str, str] = Field(default_factory=dict)
    action: str | None = None
    action_args: dict[str, str] = Field(default_factory=dict)
    agent_safe: bool = False
    blast_radius: BlastRadius = "medium"
    cooldown_seconds: int = 600
    runbook: str | None = None


class Decision(BaseModel):
    """Result of classifying one alert against the manifest."""

    route: Route
    rule_index: int | None = None
    action: str | None = None
    action_args: dict[str, str] = Field(default_factory=dict)
    agent_safe: bool = False
    blast_radius: BlastRadius = "medium"
    cooldown_seconds: int = 600
    runbook: str | None = None
    cooldown_remaining_seconds: int | None = None


class QueueItem(BaseModel):
    """A row in the human-pickup queue, returned to the UI."""

    id: int
    created_at: datetime
    alert_name: str
    alert_labels: dict[str, str]
    severity: str | None = None
    summary: str | None = None
    description: str | None = None
    blast_radius: BlastRadius
    runbook: str | None = None
    status: QueueStatus
    acked_at: datetime | None = None
    acked_by: str | None = None
    note: str | None = None


class AckRequest(BaseModel):
    by: str
    status: QueueStatus = "acked"
    note: str | None = None


class AuditRow(BaseModel):
    id: int
    ts: datetime
    alert_name: str
    route: Route
    action: str | None = None
    rule_index: int | None = None
    queue_item_id: int | None = None
