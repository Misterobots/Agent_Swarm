from __future__ import annotations

import json
import subprocess
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
    context_profile: str = "chat"
    configured_context_tokens: int = PROFILES["chat"]
    effective_context_tokens: int = PROFILES["chat"]
    input_tokens: int = 0
    fallback: bool = False
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
        context_profile=profile,
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
                            elapsed_ms=2, actual_model=model, fallback=used_fallback,
                            fallback_model=model if used_fallback else None)
        return text, obs


def assert_exact_model(obs: Observation) -> bool:
    return obs.actual_model == MODEL and obs.provider == PROVIDER and not obs.fallback


class FixtureRuntime:
    """Local runtime for end-to-end fixture execution.

    It owns only temporary projects and models the contract's project boundary,
    approval decisions, tool execution, and completion metadata. It never
    contacts Memex, Ollama, a browser, or a live repository.
    """

    def __init__(self, provider: Provider):
        self.provider = provider
        self.projects: dict[str, tuple[str, Path]] = {}
        self.events: list[dict[str, Any]] = []

    def register_project(self, identity: RunIdentity, root: Path) -> None:
        self.projects[identity.owner_id] = (identity.project_id, root.resolve())

    def _root(self, identity: RunIdentity, root: Path) -> Path:
        registered = self.projects.get(identity.owner_id)
        if registered is None or registered[0] != identity.project_id or registered[1] != root.resolve():
            raise PermissionError("project is not owned by this evaluation identity")
        return registered[1]

    def read_file(self, identity: RunIdentity, root: Path, relative: str) -> str:
        base = self._root(identity, root)
        target = (base / relative).resolve()
        if base not in target.parents:
            raise PermissionError("path escapes fixture project")
        self.events.append({"type": "tool", "tool": "read_file", "project_id": identity.project_id})
        return target.read_text(encoding="utf-8")

    def write_file(self, identity: RunIdentity, root: Path, relative: str, content: str,
                   *, approved: bool) -> None:
        base = self._root(identity, root)
        if not approved:
            self.events.append({"type": "approval_denied", "tool": "write_file"})
            return
        target = (base / relative).resolve()
        if base not in target.parents:
            raise PermissionError("path escapes fixture project")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.events.append({"type": "tool", "tool": "write_file", "project_id": identity.project_id})

    def run_command(self, identity: RunIdentity, root: Path, command: list[str],
                    *, approved: bool) -> subprocess.CompletedProcess[str] | None:
        base = self._root(identity, root)
        if not approved:
            self.events.append({"type": "approval_denied", "tool": "run_command"})
            return None
        if command[:3] != ["python", "-m", "pytest"]:
            raise ValueError("fixture runtime only permits its hidden pytest command")
        self.events.append({"type": "tool", "tool": "run_command", "project_id": identity.project_id})
        return subprocess.run(command + ["-q"], cwd=base, text=True,
                              capture_output=True, timeout=30, check=False)

    def complete(self, **kwargs: Any):
        text, obs = self.provider.complete(**kwargs)
        self.events.append({"type": "completion", "requested_model": obs.requested_model,
                            "actual_model": obs.actual_model, "provider": obs.provider,
                            "fallback": obs.fallback,
                            "effective_context_tokens": obs.effective_context_tokens})
        return text, obs


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
