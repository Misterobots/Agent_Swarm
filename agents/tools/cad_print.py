"""Client for Friday's shared workstation CAD + print bridge.

Both Memex Desktop and Friday voice use this same service.  It is not a
voice-only control surface, and it never exposes raw OpenSCAD or printer
credentials to Agent_Swarm.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

BRIDGE_URL = os.getenv("CAD_PRINT_BRIDGE_URL", "http://host.docker.internal:8790").rstrip("/")
BRIDGE_TOKEN = os.getenv("CAD_PRINT_BRIDGE_TOKEN", "")


def _call(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if BRIDGE_TOKEN:
        headers["Authorization"] = f"Bearer {BRIDGE_TOKEN}"
    try:
        response = requests.request(method, f"{BRIDGE_URL}{path}", headers=headers,
                                    json=payload, timeout=20)
        data = response.json()
        if not response.ok:
            return {"ok": False, "error": data.get("detail", response.text), "status_code": response.status_code}
        return data
    except requests.RequestException as exc:
        return {"ok": False, "error": f"CAD/print bridge unavailable: {exc}"}
    except ValueError:
        return {"ok": False, "error": "CAD/print bridge returned non-JSON response"}


def cad_print_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    action = str(args.get("action") or "parts").lower()
    routes = {
        "health": ("GET", "/health"),
        "parts": ("GET", "/cad/parts"),
        "render": ("POST", "/cad/render"),
        "artifacts": ("GET", "/cad/artifacts"),
        "print_status": ("GET", "/print/status"),
        "print_jobs": ("GET", "/print/jobs"),
        "preflight": ("POST", "/print/preflight"),
        "request_approval": ("POST", "/print/request-approval"),
        "start": ("POST", "/print/start"),
    }
    if action not in routes:
        return {"isError": True, "content": [{"type": "text", "text": f"Unsupported CAD/print action: {action}"}]}
    method, path = routes[action]
    allowed = {"part", "format", "job_id", "approval_token", "confirmed"}
    payload = {key: args[key] for key in allowed if key in args}
    result = _call(method, path, payload if method == "POST" else None)
    return {"isError": not result.get("ok", False),
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
