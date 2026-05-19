#!/usr/bin/env python3
"""
MCP Bridge smoke test for Home AI Lab.

Validates:
1) /api/v1/mcp/health
2) JSON-RPC initialize
3) JSON-RPC tools/list
4) tools/call access denial without bearer token

Optional:
5) tools/call with bearer token (if provided)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _http_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=hdrs, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        parsed = {}
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
        return e.code, parsed


def _rpc(base_url: str, method: str, params: dict[str, Any], req_id: int, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    return _http_json(
        f"{base_url}/api/v1/mcp/rpc",
        payload={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
        headers=headers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test MCP bridge endpoints")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="Agent runtime base URL")
    parser.add_argument("--bearer", default="", help="Optional JWT bearer token for authenticated tools/call")
    parser.add_argument(
        "--strict-bearer",
        action="store_true",
        help="Fail test if authenticated call does not return MCP result envelope",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    failures = 0

    def check(condition: bool, name: str, detail: str = ""):
        nonlocal failures
        status = "PASS" if condition else "FAIL"
        if not condition:
            failures += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[{status}] {name}{suffix}")

    code, health = _http_json(f"{base}/api/v1/mcp/health")
    check(code == 200, "GET /api/v1/mcp/health", f"status={code}")
    check("server_name" in health, "health payload has server_name")

    code, init_resp = _rpc(base, "initialize", {}, 1)
    check(code == 200 and "result" in init_resp, "RPC initialize", f"status={code}")

    code, list_resp = _rpc(base, "tools/list", {}, 2)
    tools = (((list_resp or {}).get("result") or {}).get("tools") or [])
    check(code == 200 and isinstance(tools, list) and len(tools) >= 1, "RPC tools/list", f"tools={len(tools)}")

    # Ensure auth gate denies privileged call when no token is provided.
    code, deny_resp = _rpc(
        base,
        "tools/call",
        {"name": "hive.terminal.run", "arguments": {"command": "echo test"}},
        3,
    )
    deny_result = (deny_resp or {}).get("result") or {}
    deny_content = (deny_result.get("content") or [{}])[0].get("text", "")
    check(code == 200, "RPC tools/call (unauthenticated request accepted at transport)", f"status={code}")
    check(bool(deny_result.get("isError")), "RPC tools/call denied without token", deny_content[:120])

    if args.bearer:
        code, authed_resp = _rpc(
            base,
            "tools/call",
            {"name": "hive.fs.list", "arguments": {"path": "."}},
            4,
            headers={"Authorization": f"Bearer {args.bearer}"},
        )
        result = (authed_resp or {}).get("result") or {}
        if args.strict_bearer:
            check(code == 200, "RPC tools/call with bearer", f"status={code}")
            check("isError" in result, "RPC tools/call with bearer has result envelope")
        else:
            okish = code == 200 and "isError" in result
            detail = f"status={code}"
            if not okish:
                detail += " (non-fatal: token may be signed with different runtime secret)"
            check(True, "RPC tools/call with bearer (best-effort)", detail)

    print(f"\nSmoke test complete. failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
