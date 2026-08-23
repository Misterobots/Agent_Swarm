"""Safety-gated bridge client for Friday's local Bambu print service.

The bridge itself runs on the Windows workstation where Bambu Studio and
the P1S are reachable.  Agent_Swarm never stores the printer LAN access code
and never receives a shell command or arbitrary file path.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

BRIDGE_URL = os.getenv("BAMBU_BRIDGE_URL", "http://host.docker.internal:8791").rstrip("/")
BRIDGE_TOKEN = os.getenv("BAMBU_BRIDGE_TOKEN", "")


def _request(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if BRIDGE_TOKEN:
        headers["Authorization"] = f"Bearer {BRIDGE_TOKEN}"
    try:
        response = requests.request(method, f"{BRIDGE_URL}{path}", headers=headers,
                                    json=payload, timeout=15)
        data = response.json()
        if not response.ok:
            return {"ok": False, "error": data.get("detail", response.text), "status_code": response.status_code}
        return data
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Bambu bridge unavailable: {exc}"}
    except ValueError:
        return {"ok": False, "error": "Bambu bridge returned non-JSON response"}


def bambu_print_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run an allow-listed printer action through the local bridge."""
    action = str(args.get("action") or "status").lower()
    allowed = {"status", "list_jobs", "preflight", "request_approval", "start", "cancel"}
    if action not in allowed:
        return {"isError": True, "content": [{"type": "text", "text": f"Unsupported Bambu action: {action}"}]}

    payload = {key: args[key] for key in ("job_id", "approval_token", "confirmed") if key in args}
    result = _request("GET" if action in {"status", "list_jobs"} else "POST",
                      f"/{action}", payload or None)
    return {"isError": not result.get("ok", False),
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
