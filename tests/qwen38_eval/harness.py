from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


MODEL = "qwen3.8:27b"
PROVIDER = "ollama"
PROFILES = {"chat": 32768, "project": 65536, "long": 122880}
CASE_DEADLINES_SECONDS = {"review": 600, "build": 1200, "approvals": 600,
                          "vision": 600, "long_context": 1200, "recovery": 600}


@dataclass
class RunIdentity:
    owner_id: str
    session_id: str
    project_id: str

    @classmethod
    def unique(cls, label: str) -> "RunIdentity":
        token = uuid.uuid4().hex[:12]
        return cls(f"qwen38-eval-{label}-{token}", f"session-{token}", f"project-{token}")


@dataclass
class Observation:
    requested_model: str = MODEL
    actual_model: str = MODEL
    provider: str = PROVIDER
    configured_context_tokens: int = PROFILES["chat"]
    effective_context_tokens: int = PROFILES["chat"]
    input_tokens: int = 0
    used_fallback: bool = False
    fallback_model: str | None = None
    owner_id: str = ""
    session_id: str = ""
    project_id: str = ""
    elapsed_ms: int = 0
    approval_wait_ms: int = 0
    status: str = "passed"
    notes: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    name: str
    status: str
    mode: str
    authority: str
    observation: Observation
    assertions: dict[str, bool]
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed" and all(self.assertions.values())


class Provider(Protocol):
    def complete(self, *, prompt: str, profile: str, identity: RunIdentity,
                 image: bytes | None = None) -> tuple[str, Observation]: ...


def _observation(identity: RunIdentity, profile: str, *, input_tokens: int = 0,
                 elapsed_ms: int = 1, **kwargs: Any) -> Observation:
    return Observation(
        configured_context_tokens=PROFILES[profile],
        effective_context_tokens=PROFILES[profile],
        input_tokens=input_tokens,
        owner_id=identity.owner_id,
        session_id=identity.session_id,
        project_id=identity.project_id,
        elapsed_ms=elapsed_ms,
        **kwargs,
    )


class DeterministicProvider:
    """Deterministic stand-in for the eventual Memex provider adapter.

    It returns fixture answers and never contacts Ollama, the GPU queue, a live
    project, or Friday. This makes mock results useful for harness validation but
    never valid evidence of live model quality.
    """

    def __init__(self, *, fail_next: int = 0, fallback_model: str | None = None):
        self.fail_next = fail_next
        self.fallback_model = fallback_model
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, prompt: str, profile: str, identity: RunIdentity,
                 image: bytes | None = None) -> tuple[str, Observation]:
        self.calls.append({"prompt": prompt, "profile": profile, "identity": asdict(identity),
                           "image_bytes": len(image or b"")})
        if self.fail_next:
            self.fail_next -= 1
            raise ConnectionError("deterministic provider transport failure")
        text = prompt
        if prompt.startswith("REVIEW:"):
            text = "FINDING src/auth.py:18 missing issuer validation; FINDING src/cache.py:42 stale key; FINDING src/api.py:77 unchecked status."
        elif prompt.startswith("VISION:"):
            text = "The image contains labels ALPHA, BETA, GAMMA and the plotted values 10, 20, 30."
        elif prompt.startswith("LONG:"):
            text = "FACT-A=violet; FACT-B=quartz; FACT-C=17; FACT-D=harbor; cross-file relation=FACT-A maps to FACT-D."
        elif prompt.startswith("RECOVER:"):
            text = "provider unavailable; no fallback claimed; retry is bounded."
        model = self.fallback_model or MODEL
        used_fallback = model != MODEL
        obs = _observation(identity, profile, input_tokens=max(1, len(prompt) // 4),
                            elapsed_ms=2, actual_model=model, used_fallback=used_fallback,
                            fallback_model=model if used_fallback else None)
        return text, obs


def assert_exact_model(obs: Observation) -> bool:
    return obs.actual_model == MODEL and obs.provider == PROVIDER and not obs.used_fallback


def result(name: str, mode: str, identity: RunIdentity, assertions: dict[str, bool],
           *, observation: Observation | None = None, details: dict[str, Any] | None = None,
           authority: str = "hidden deterministic assertions") -> CaseResult:
    obs = observation or _observation(identity, "chat")
    status = "passed" if all(assertions.values()) else "failed"
    obs.status = status
    return CaseResult(name, status, mode, authority, obs, assertions, details or {})


def write_json_report(path: Path, *, mode: str, results: Iterable[CaseResult]) -> None:
    payload = {
        "suite": "qwen38-evaluation",
        "mode": mode,
        "model": MODEL,
        "provider": PROVIDER,
        "case_deadlines_seconds": CASE_DEADLINES_SECONDS,
        "results": [asdict(item) for item in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

