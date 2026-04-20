"""
Grounding Permissions Store

Lightweight JSON-backed store that tracks per-user grounding permission grants.
Permissions are written here when an admin approves a GROUNDING_WEB or
GROUNDING_DOCS governance request.

Structure of /workspace/grounding_permissions.json:
{
  "<owner_id>": {
    "web_grounding": true,
    "docs_grounding": true,
    "granted_at": "2025-01-01T00:00:00"
  }
}
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger("GroundingPermissions")

GROUNDING_PERMISSIONS_PATH = os.getenv(
    "GROUNDING_PERMISSIONS_PATH", "/workspace/grounding_permissions.json"
)


class GroundingPermissionsStore:
    def __init__(self, path: str = GROUNDING_PERMISSIONS_PATH) -> None:
        self._path = path
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            self._data = {}
            return
        try:
            with open(self._path, "r") as fh:
                self._data = json.load(fh)
        except Exception as exc:
            logger.error("[GroundingPermissions] Failed to load %s: %s", self._path, exc)
            self._data = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w") as fh:
                json.dump(self._data, fh, indent=2)
        except Exception as exc:
            logger.error("[GroundingPermissions] Failed to save %s: %s", self._path, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_permitted(self, owner_id: str, permission: str) -> bool:
        """Return True if *owner_id* has been granted *permission*.

        Args:
            owner_id:   The user/session owner identifier.
            permission: "web_grounding" or "docs_grounding".
        """
        if not owner_id:
            return False
        entry = self._data.get(owner_id, {})
        return bool(entry.get(permission, False))

    def grant(self, owner_id: str, permission: str) -> None:
        """Grant *permission* to *owner_id*."""
        if owner_id not in self._data:
            self._data[owner_id] = {}
        self._data[owner_id][permission] = True
        self._data[owner_id]["granted_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save()
        logger.info("[GroundingPermissions] Granted %s → %s", permission, owner_id)

    def revoke(self, owner_id: str, permission: str) -> None:
        """Revoke *permission* from *owner_id*."""
        if owner_id in self._data:
            self._data[owner_id].pop(permission, None)
            self._save()
            logger.info("[GroundingPermissions] Revoked %s ← %s", permission, owner_id)

    def get_status(self, owner_id: str) -> dict:
        """Return the full permission record for *owner_id*."""
        return {
            "owner_id": owner_id,
            "web_grounding": self.is_permitted(owner_id, "web_grounding"),
            "docs_grounding": self.is_permitted(owner_id, "docs_grounding"),
        }

    def reload(self) -> None:
        """Force a reload from disk (useful in long-running processes)."""
        self._load()


# Singleton used by router.py and main.py
grounding_permissions = GroundingPermissionsStore()
