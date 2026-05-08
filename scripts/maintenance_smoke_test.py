#!/usr/bin/env python3
"""
End-to-end smoke test for the alert → maintenance_router → Redis/Postgres path.

Posts synthetic Alertmanager webhook payloads against the live router (default
http://192.168.2.103:9095) and verifies:

  • An agent_safe alert (ServiceDown / postgres) shows up in the audit log with
    route=agent and lands a JSON message on the Redis queue.
  • A human-path alert (ContainerHighMemory) creates a row in the
    maintenance_dispatch audit log with route=human plus a queue item.
  • A second agent_safe ServiceDown within the cooldown window comes back with
    route=suppressed_cooldown.

This is a black-box check — it does NOT consume the Redis message, so
auto_repair_daemon will pick it up if it is running. Pass --consume to drain
the queue at the end.

Usage:
    python scripts/maintenance_smoke_test.py
    python scripts/maintenance_smoke_test.py --router http://192.168.2.103:9095 --consume

Requires: requests, redis (already in maintenance_router/requirements.txt).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_payload(alertname: str, status: str = "firing", **labels: str) -> dict[str, Any]:
    """Build a minimal Alertmanager v4 webhook payload."""
    common_labels = {"alertname": alertname, **labels}
    return {
        "version": "4",
        "groupKey": f"{{}}:{{alertname={alertname!r}}}",
        "status": status,
        "receiver": "maintenance-router",
        "groupLabels": {"alertname": alertname},
        "commonLabels": common_labels,
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": status,
                "labels": common_labels,
                "annotations": {
                    "summary": f"smoke-test: {alertname}",
                    "description": f"synthetic {alertname} from maintenance_smoke_test.py",
                },
                "startsAt": now_iso(),
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090",
                "fingerprint": f"smoke-{alertname}-{int(time.time())}",
            }
        ],
    }


def post_alert(router: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(f"{router}/webhook/alertmanager", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


def fetch_audit(router: str, limit: int = 20) -> list[dict[str, Any]]:
    r = requests.get(f"{router}/api/maintenance/audit", params={"limit": limit}, timeout=5)
    r.raise_for_status()
    return r.json().get("rows", [])


def fetch_queue(router: str) -> list[dict[str, Any]]:
    r = requests.get(f"{router}/api/maintenance/queue", params={"status": "pending"}, timeout=5)
    r.raise_for_status()
    return r.json().get("items", [])


def healthz(router: str) -> bool:
    try:
        r = requests.get(f"{router}/healthz", timeout=3)
        return r.ok
    except Exception:
        return False


def expect(label: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    extra = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{extra}")
    return cond


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--router", default="http://192.168.2.103:9095")
    p.add_argument("--redis-host", default="192.168.2.103")
    p.add_argument("--redis-port", type=int, default=6379)
    p.add_argument(
        "--consume",
        action="store_true",
        help="Drain the Redis system_alert queue at the end so auto_repair_daemon doesn't act.",
    )
    args = p.parse_args()

    print(f"Router:       {args.router}")
    print(f"Redis:        {args.redis_host}:{args.redis_port}")
    print()

    if not healthz(args.router):
        print(f"FAIL: router /healthz unreachable at {args.router}")
        return 1
    print("Router /healthz OK")

    all_pass = True

    # Test 1 — agent_safe path
    print("\n[1] ServiceDown(job=postgres) — expect route=agent")
    resp = post_alert(args.router, make_payload("ServiceDown", job="postgres", instance="hopper:5432", severity="critical"))
    decisions = resp.get("decisions", [])
    all_pass &= expect("router accepted webhook", bool(decisions))
    if decisions:
        d = decisions[0]
        all_pass &= expect("route is agent", d.get("route") == "agent", f"got {d.get('route')}")
        all_pass &= expect("action is restart_container", d.get("action") == "restart_container")

    # Test 2 — human path
    print("\n[2] ContainerHighMemory — expect route=human + queue item")
    pre_queue = fetch_queue(args.router)
    resp = post_alert(args.router, make_payload("ContainerHighMemory", name="agent_runtime", severity="warning"))
    decisions = resp.get("decisions", [])
    if decisions:
        d = decisions[0]
        all_pass &= expect("route is human", d.get("route") == "human", f"got {d.get('route')}")
    post_queue = fetch_queue(args.router)
    all_pass &= expect(
        "queue grew by 1",
        len(post_queue) == len(pre_queue) + 1,
        f"{len(pre_queue)} -> {len(post_queue)}",
    )

    # Test 3 — cooldown suppression
    print("\n[3] Repeat ServiceDown(job=postgres) — expect route=suppressed_cooldown")
    resp = post_alert(args.router, make_payload("ServiceDown", job="postgres", instance="hopper:5432", severity="critical"))
    decisions = resp.get("decisions", [])
    if decisions:
        d = decisions[0]
        all_pass &= expect(
            "route is suppressed_cooldown",
            d.get("route") == "suppressed_cooldown",
            f"got {d.get('route')}",
        )

    # Test 4 — audit log shape
    print("\n[4] Audit log reflects the three dispatches")
    audit = fetch_audit(args.router, limit=10)
    routes = [r.get("route") for r in audit[:3]]
    all_pass &= expect(
        "3 most recent rows include agent + human + suppressed",
        set(routes) >= {"agent", "human", "suppressed_cooldown"},
        f"got {routes}",
    )

    # Test 5 — Redis received the agent dispatch
    print("\n[5] Redis system_alert queue received the agent dispatch")
    try:
        import redis  # type: ignore[import-not-found]
        r = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=True)
        depth = r.llen("maintenance:system_alert")
        all_pass &= expect("queue depth >= 1", depth >= 1, f"depth={depth}")
        if args.consume and depth > 0:
            drained = r.delete("maintenance:system_alert")
            print(f"  consumed (deleted {drained} key)")
        elif depth > 0:
            # Peek without removing so the daemon can still pick it up.
            peek = r.lrange("maintenance:system_alert", -1, -1)
            if peek:
                evt = json.loads(peek[0])
                all_pass &= expect(
                    "event has type=system_alert",
                    evt.get("type") == "system_alert",
                    f"got {evt.get('type')}",
                )
    except ImportError:
        print("  [SKIP] redis library not installed locally")
    except Exception as e:
        all_pass &= expect("redis reachable", False, str(e))

    print()
    if all_pass:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED — see above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
