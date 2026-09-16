"""Authenticated live Memex adapter for the Qwen 3.8 evaluation suite.

This module performs no requests on import. Credentials are caller supplied via
QWEN38_EVAL_HEADERS_JSON or QWEN38_EVAL_BEARER_TOKEN. It never invents a user
identity and records whether authentication came from configured caller input.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tests.qwen38_eval.harness import MODEL, Observation, PROFILES, Provider, RunIdentity


class LiveAdapterError(RuntimeError):
    pass


@dataclass
class AuthContext:
    headers: dict[str, str]
    source: str
    caller_identity_asserted: bool = False

    @classmethod
    def from_environment(cls) -> "AuthContext":
        raw = os.getenv("QWEN38_EVAL_HEADERS_JSON", "").strip()
        if raw:
            try:
                headers = {str(k): str(v) for k, v in json.loads(raw).items()}
            except (ValueError, AttributeError) as exc:
                raise LiveAdapterError("QWEN38_EVAL_HEADERS_JSON must be a JSON object") from exc
            return cls(headers, "caller_headers", bool(headers))
        token = os.getenv("QWEN38_EVAL_BEARER_TOKEN", "").strip()
        if token:
            return cls({"Authorization": f"Bearer {token}"}, "caller_bearer_token", True)
        raise LiveAdapterError(
            "live mode requires QWEN38_EVAL_HEADERS_JSON or QWEN38_EVAL_BEARER_TOKEN; "
            "the runner will not fabricate an authenticated identity"
        )


@dataclass
class StreamResult:
    text: str
    observation: Observation
    events: list[dict[str, Any]] = field(default_factory=list)
    approval_calls: list[str] = field(default_factory=list)
    auth_source: str = ""
    auth_proof: str = "caller_configured_credentials_only"


class LiveMemexAdapter(Provider):
    def __init__(self, *, base_url: str = "http://127.0.0.1:8009", auth: AuthContext | None = None,
                 timeout_seconds: int = 1200, model: str = MODEL,
                 send_context_profile: bool = True,
                 vision_route: str = "qwen",
                 legacy_vision_models: tuple[str, ...] = ("minicpm-v:latest", "llava:13b", "llava:7b", "llava:latest", "moondream:latest")):
        self.base_url = base_url.rstrip("/")
        self.auth = auth or AuthContext.from_environment()
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.send_context_profile = send_context_profile
        self.vision_route = vision_route
        self.legacy_vision_models = legacy_vision_models
        self.calls: list[dict[str, Any]] = []

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                 query: dict[str, str] | None = None, stream: bool = False):
        url = path if path.startswith(("http://", "https://")) else f"{self.base_url}{path}"
        if query:
            url += "?" + urlencode(query)
        headers = {"Accept": "text/event-stream" if stream else "application/json",
                   **self.auth.headers}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method)
        try:
            return urlopen(req, timeout=self.timeout_seconds)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise LiveAdapterError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LiveAdapterError(f"{method} {path} failed: {exc.reason}") from exc

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        with self._request(method, path, **kwargs) as response:
            raw = response.read().decode("utf-8")
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise LiveAdapterError(f"{method} {path} returned non-JSON data") from exc

    def list_projects(self) -> dict[str, Any]:
        return self._json("GET", "/v1/dev/projects")

    def create_project(self, name: str) -> dict[str, Any]:
        return self._json("POST", "/v1/dev/projects", body={"name": name, "source": "blank"})

    def delete_project(self, project_id: str) -> None:
        with self._request("DELETE", f"/v1/dev/projects/{project_id}"):
            return

    def create_session(self, project_id: str) -> dict[str, Any]:
        return self._json("POST", "/v1/dev/sessions", body={"project_id": project_id})

    def read_file(self, project_id: str, path: str) -> dict[str, Any]:
        return self._json("GET", "/v1/dev/files/content",
                          query={"project_id": project_id, "path": path})

    def write_file(self, project_id: str, path: str, content: str) -> None:
        with self._request("PUT", "/v1/dev/files/content", body={
            "path": path, "content": content, "encoding": "utf8",
        }, query={"project_id": project_id}):
            return

    def tree(self, project_id: str) -> dict[str, Any]:
        return self._json("GET", "/v1/dev/files/tree", query={"project_id": project_id})

    def chat_stream(self, *, prompt: str, identity: RunIdentity, profile: str = "project",
                    session_id: str | None = None, permission_mode: str = "plan",
                    code: bool = True,
                    attachments: list[dict[str, Any]] | None = None,
                    approval_handler: Callable[[str, dict[str, Any]], None] | None = None) -> StreamResult:
        if profile not in PROFILES:
            raise ValueError(f"invalid context profile: {profile}")
        requested_model = self.model
        if attachments and self.vision_route == "legacy":
            # Let the existing vision handler select and report its actual
            # installed VLM. Never force the text baseline into an image call.
            requested_model = "default"
        body: dict[str, Any] = {
            "model": requested_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "session_id": session_id or identity.session_id,
        }
        if self.send_context_profile:
            body["context_profile"] = profile
        if code:
            body.update({"current_project_id": identity.project_id,
                         "dev_mode": True, "dev_permission_mode": permission_mode})
        if attachments:
            body["attachments"] = attachments
        started = time.monotonic()
        response = self._request("POST", "/v1/chat/completions", body=body, stream=True)
        chunks: list[str] = []
        events: list[dict[str, Any]] = []
        approvals: list[str] = []
        metadata: dict[str, Any] = {}
        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                events.append(event)
                for source in (event, event.get("metadata", {}), event.get("delta", {})):
                    if isinstance(source, dict):
                        for key in ("requested_model", "actual_model", "provider", "fallback",
                                    "context_profile", "effective_context_tokens"):
                            if key in source:
                                metadata[key] = source[key]
                if event.get("type") == "tool_approval_needed":
                    call_id = event.get("call_id") or event.get("tool_call_id")
                    if call_id:
                        approvals.append(str(call_id))
                        if approval_handler is not None:
                            approval_handler(str(call_id), event)
                delta = event.get("choices", [{}])[0].get("delta", {}) if event.get("choices") else {}
                content = delta.get("content") if isinstance(delta, dict) else None
                if content:
                    chunks.append(content)
        finally:
            response.close()
        actual_model = metadata.get("actual_model") or requested_model
        provider = metadata.get("provider") or "unknown"
        fallback = bool(metadata.get("fallback", False))
        obs = Observation(
            requested_model=requested_model,
            actual_model=actual_model,
            provider=provider,
            context_profile=str(metadata.get("context_profile") or profile),
            configured_context_tokens=PROFILES[profile],
            effective_context_tokens=int(metadata.get("effective_context_tokens") or 0),
            input_tokens=0,
            fallback=fallback,
            owner_id=identity.owner_id,
            session_id=identity.session_id,
            project_id=identity.project_id,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            notes=[f"auth_source={self.auth.source}", "caller identity was not inferred from response"],
        )
        self.calls.append({"path": "/v1/chat/completions", "profile": profile,
                           "identity": identity.__dict__, "approval_calls": approvals})
        return StreamResult("".join(chunks), obs, events, approvals, self.auth.source)

    def complete(self, *, prompt: str, profile: str, identity: RunIdentity,
                 image: bytes | None = None) -> tuple[str, Observation]:
        attachments = None
        if image is not None:
            attachments = [{"name": "fixture.ppm", "mimeType": "image/x-portable-pixmap",
                            "data": base64.b64encode(image).decode("ascii"), "size": len(image)}]
        result = self.chat_stream(prompt=prompt, identity=identity, profile=profile,
                                  attachments=attachments)
        return result.text, result.observation

    def approve(self, call_id: str, *, auto: str = "none", tool_name: str = "") -> dict[str, Any]:
        return self._json("POST", f"/api/v1/dev/approve/{call_id}",
                          body={"auto": auto, "tool_name": tool_name})

    def deny(self, call_id: str) -> dict[str, Any]:
        return self._json("POST", f"/api/v1/dev/deny/{call_id}")

    def fault_inject(self, *, kind: str, identity: RunIdentity) -> dict[str, Any]:
        """Call the lead-provided isolated fault hook; unset means blocked."""
        endpoint = os.getenv("QWEN38_FAULT_HOOK_URL", "").strip()
        if not endpoint:
            raise LiveAdapterError("recovery blocked: QWEN38_FAULT_HOOK_URL is not configured")
        return self._json("POST", endpoint, body={"kind": kind, "session_id": identity.session_id,
                                                  "project_id": identity.project_id})

    def queue_status(self) -> dict[str, Any]:
        """Read lead-provided queue status; unset means contention is blocked."""
        endpoint = os.getenv("QWEN38_QUEUE_STATUS_URL", "").strip()
        if not endpoint:
            raise LiveAdapterError("contention blocked: QWEN38_QUEUE_STATUS_URL is not configured")
        return self._json("GET", endpoint)


def measure_qwen_tokens(text: str) -> int:
    """Measure with the Qwen tokenizer; fail explicitly if it is unavailable."""
    tokenizer_path = os.getenv("QWEN38_TOKENIZER_PATH", "").strip()
    if not tokenizer_path:
        raise LiveAdapterError("long-context case blocked: QWEN38_TOKENIZER_PATH is not configured")
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        return len(tokenizer.encode(text, add_special_tokens=True))
    except Exception as exc:
        raise LiveAdapterError(f"long-context case blocked: Qwen tokenizer unavailable: {exc}") from exc


def make_context_probe(profile: str, ratio: float) -> tuple[str, int]:
    """Build a deterministic input near 70% or 90% of a usable profile."""
    if profile not in PROFILES or ratio not in (0.7, 0.9):
        raise ValueError("context probes require chat/project/long and ratio 0.7 or 0.9")
    tokenizer_path = os.getenv("QWEN38_TOKENIZER_PATH", "").strip()
    if not tokenizer_path:
        raise LiveAdapterError("context probe blocked: QWEN38_TOKENIZER_PATH is not configured")
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        target = int(PROFILES[profile] * ratio)
        filler = "stable context probe token sequence; "
        ids = tokenizer.encode(filler, add_special_tokens=False)
        repeated = (ids * ((target // max(1, len(ids))) + 2))[:target]
        text = tokenizer.decode(repeated, skip_special_tokens=True)
        return text, len(tokenizer.encode(text, add_special_tokens=True))
    except Exception as exc:
        raise LiveAdapterError(f"context probe blocked: Qwen tokenizer unavailable: {exc}") from exc
