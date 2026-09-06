"""Durable, user-scoped model and feature permissions.

An absent policy deliberately preserves the historical Memex behaviour.  Admins
can then opt a user into explicit restrictions without a migration that might
lock existing users out during deployment.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional


FEATURES: dict[str, str] = {
    "chat": "Chat",
    "code": "Code and workspace tools",
    "research": "Research",
    "grounding_web": "Web grounding",
    "grounding_docs": "Document grounding",
    "grounding_files": "File grounding",
    "planning": "Planning",
    "swarm": "Swarm coordination",
    "memory": "Memory",
    "routines": "Routines and scheduled work",
    "design": "Design",
    "art": "Art",
    "eval": "Evaluation tools",
    "model_selection": "Model selection",
}


class UserPermissionStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or os.getenv("USER_PERMISSIONS_PATH", "/workspace/user_permissions.json"))
        self._lock = threading.RLock()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "users": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("users", {}), dict):
                raise ValueError("invalid permissions document")
            data.setdefault("version", 1)
            data.setdefault("users", {})
            return data
        except (OSError, ValueError, json.JSONDecodeError):
            return {"version": 1, "users": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _normalize(owner_id: str, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        configured = raw is not None
        raw = raw or {}
        allowed = raw.get("allowed_models")
        if allowed is not None:
            allowed = sorted({str(model).strip() for model in allowed if str(model).strip()})
        supplied_features = raw.get("features") if isinstance(raw.get("features"), dict) else {}
        features = {key: bool(supplied_features.get(key, True)) for key in FEATURES}
        return {
            "owner_id": owner_id,
            "configured": configured,
            "allowed_models": allowed,
            "features": features,
        }

    def get(self, owner_id: str) -> dict[str, Any]:
        owner = owner_id.strip()
        with self._lock:
            raw = self._load()["users"].get(owner)
            return self._normalize(owner, deepcopy(raw) if raw is not None else None)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            users = self._load()["users"]
            return [self._normalize(owner, deepcopy(raw)) for owner, raw in sorted(users.items())]

    def set(self, owner_id: str, allowed_models: Optional[list[str]], features: dict[str, bool]) -> dict[str, Any]:
        owner = owner_id.strip()
        if not owner:
            raise ValueError("owner_id is required")
        unknown = sorted(set(features) - set(FEATURES))
        if unknown:
            raise ValueError(f"Unknown features: {', '.join(unknown)}")
        normalized = self._normalize(owner, {"allowed_models": allowed_models, "features": features})
        with self._lock:
            data = self._load()
            data["users"][owner] = {
                "allowed_models": normalized["allowed_models"],
                "features": normalized["features"],
            }
            self._save(data)
        return normalized

    def delete(self, owner_id: str) -> bool:
        owner = owner_id.strip()
        with self._lock:
            data = self._load()
            existed = data["users"].pop(owner, None) is not None
            if existed:
                self._save(data)
            return existed

    def model_allowed(self, owner_id: str, model: str) -> bool:
        allowed = self.get(owner_id)["allowed_models"]
        return allowed is None or model in allowed

    def feature_allowed(self, owner_id: str, feature: str) -> bool:
        if feature not in FEATURES:
            return False
        return bool(self.get(owner_id)["features"][feature])


user_permissions = UserPermissionStore()
