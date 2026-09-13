"""Pure, fail-closed resource admission for learning.v1.

This module never queries NVML, Docker, Ollama, Redis, or a host.  A caller
must provide an explicit signed/authorized manifest and a fresh observation.
That separation is intentional: an idle card, a GPU index, or a successful
telemetry call is not proof that a resource belongs to Memex or is isolated
from SaltMedia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any, Mapping


class ResourcePolicyError(ValueError):
    """The resource manifest or observation is malformed."""


@dataclass(frozen=True)
class ResourceManifest:
    manifest_version: str
    allowed_hosts: frozenset[str]
    gpu_hosts: Mapping[str, str]
    enabled_gpu_uuids: frozenset[str]
    denied_gpu_uuids: frozenset[str]
    allowed_consumers: frozenset[str]
    protected_consumer_patterns: frozenset[str]
    max_telemetry_age_seconds: int = 30
    min_free_memory_bytes: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ResourceManifest":
        version = str(data.get("manifest_version") or "").strip()
        if not version:
            raise ResourcePolicyError("manifest_version is required")

        hosts = frozenset(_required_values(data.get("allowed_hosts"), "allowed_hosts"))
        denied = frozenset(str(value).strip() for value in data.get("denied_gpu_uuids", []) if str(value).strip())
        allowed_consumers = frozenset(
            str(value).strip() for value in data.get("allowed_consumers", []) if str(value).strip()
        )
        protected_patterns = frozenset(
            str(value).strip() for value in data.get("protected_consumer_patterns", []) if str(value).strip()
        )

        gpu_hosts: dict[str, str] = {}
        enabled: set[str] = set()
        for entry in data.get("gpus", []):
            if not isinstance(entry, Mapping):
                raise ResourcePolicyError("each gpus entry must be an object")
            gpu_uuid = str(entry.get("uuid") or "").strip()
            host_id = str(entry.get("host_id") or "").strip()
            if not gpu_uuid or not host_id:
                raise ResourcePolicyError("each GPU requires uuid and host_id")
            if host_id not in hosts:
                raise ResourcePolicyError(f"GPU {gpu_uuid} belongs to an unlisted host")
            if gpu_uuid in gpu_hosts:
                raise ResourcePolicyError(f"duplicate GPU UUID: {gpu_uuid}")
            gpu_hosts[gpu_uuid] = host_id
            lane_enabled = entry.get("enabled", False)
            if not isinstance(lane_enabled, bool):
                raise ResourcePolicyError("GPU enabled must be a boolean")
            if lane_enabled:
                enabled.add(gpu_uuid)

        max_age = int(data.get("max_telemetry_age_seconds", 30))
        min_free = int(data.get("min_free_memory_bytes", 0))
        if max_age <= 0:
            raise ResourcePolicyError("max_telemetry_age_seconds must be positive")
        if min_free < 0:
            raise ResourcePolicyError("min_free_memory_bytes cannot be negative")

        return cls(
            manifest_version=version,
            allowed_hosts=hosts,
            gpu_hosts=gpu_hosts,
            enabled_gpu_uuids=frozenset(enabled),
            denied_gpu_uuids=denied,
            allowed_consumers=allowed_consumers,
            protected_consumer_patterns=protected_patterns,
            max_telemetry_age_seconds=max_age,
            min_free_memory_bytes=min_free,
        )


@dataclass(frozen=True)
class GPUObservation:
    host_id: str
    gpu_uuid: str
    total_memory_bytes: int
    free_memory_bytes: int
    telemetry_at: datetime
    consumers: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "GPUObservation":
        host_id = str(data.get("host_id") or "").strip()
        gpu_uuid = str(data.get("gpu_uuid") or data.get("uuid") or "").strip()
        if not host_id or not gpu_uuid:
            raise ResourcePolicyError("GPU observation requires host_id and gpu_uuid")

        telemetry_at = _parse_timestamp(data.get("telemetry_at"))
        total = int(data.get("total_memory_bytes", 0))
        free = int(data.get("free_memory_bytes", 0))
        if total <= 0 or free < 0 or free > total:
            raise ResourcePolicyError("GPU memory observation is invalid")

        consumer_data = data.get("consumers")
        if not isinstance(consumer_data, (list, tuple)) or any(
            not isinstance(value, str) or not value.strip() for value in consumer_data
        ):
            raise ResourcePolicyError("consumers must be an explicit list of non-empty identities")
        consumers = tuple(value.strip() for value in consumer_data)
        return cls(host_id, gpu_uuid, total, free, telemetry_at, consumers)


@dataclass(frozen=True)
class AdmissionDecision:
    eligible: bool
    code: str
    reason: str
    manifest_version: str
    host_id: str
    gpu_uuid: str
    details: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "code": self.code,
            "reason": self.reason,
            "manifest_version": self.manifest_version,
            "host_id": self.host_id,
            "gpu_uuid": self.gpu_uuid,
            "details": dict(self.details),
        }


def admit_gpu(
    manifest: ResourceManifest,
    observation: GPUObservation,
    *,
    now: datetime | None = None,
    min_free_memory_bytes: int | None = None,
) -> AdmissionDecision:
    """Return a decision without claiming or changing the observed resource."""

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    observed_at = observation.telemetry_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age = (now - observed_at).total_seconds()

    base = {
        "telemetry_age_seconds": round(age, 3),
        "free_memory_bytes": observation.free_memory_bytes,
        "total_memory_bytes": observation.total_memory_bytes,
        "consumers": list(observation.consumers),
    }

    def deny(code: str, reason: str, **extra: Any) -> AdmissionDecision:
        return AdmissionDecision(
            False, code, reason, manifest.manifest_version,
            observation.host_id, observation.gpu_uuid, {**base, **extra},
        )

    if observation.host_id not in manifest.allowed_hosts:
        return deny("unknown_host", "host is not in the authorized Memex allowlist")
    if observation.gpu_uuid in manifest.denied_gpu_uuids:
        return deny("protected_gpu", "GPU is explicitly denied by policy")
    if observation.gpu_uuid not in manifest.gpu_hosts:
        return deny("unknown_gpu", "GPU UUID is not in the authorized allowlist")
    if manifest.gpu_hosts[observation.gpu_uuid] != observation.host_id:
        return deny("gpu_host_mismatch", "GPU UUID is assigned to a different host")
    if observation.gpu_uuid not in manifest.enabled_gpu_uuids:
        return deny("gpu_disabled", "GPU lane is not enabled by policy")
    if age < 0 or age > manifest.max_telemetry_age_seconds:
        return deny("stale_telemetry", "per-device telemetry is missing or stale")

    for consumer in observation.consumers:
        if any(fnmatchcase(consumer, pattern) for pattern in manifest.protected_consumer_patterns):
            return deny("protected_consumer", "a protected consumer is present", consumer=consumer)
        if consumer not in manifest.allowed_consumers:
            return deny("unknown_consumer", "an unallowlisted consumer is present", consumer=consumer)

    required = manifest.min_free_memory_bytes if min_free_memory_bytes is None else int(min_free_memory_bytes)
    if required < 0:
        raise ResourcePolicyError("min_free_memory_bytes cannot be negative")
    required = max(manifest.min_free_memory_bytes, required)
    if observation.free_memory_bytes < required:
        return deny(
            "insufficient_free_memory",
            "measured free memory is below the requested floor",
            required_free_memory_bytes=required,
        )

    return AdmissionDecision(
        True,
        "eligible",
        "GPU passed explicit ownership, freshness, consumer, and capacity checks",
        manifest.manifest_version,
        observation.host_id,
        observation.gpu_uuid,
        {**base, "required_free_memory_bytes": required},
    )


def _required_values(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)) or not value:
        raise ResourcePolicyError(f"{field} must be a non-empty list")
    values = [str(item).strip() for item in value if str(item).strip()]
    if not values:
        raise ResourcePolicyError(f"{field} must contain non-empty values")
    return values


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        raw = str(value or "").strip()
        if not raw:
            raise ResourcePolicyError("telemetry_at is required")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ResourcePolicyError("telemetry_at must be RFC3339 or epoch seconds") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
