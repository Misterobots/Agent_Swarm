"""
MONITOR_TOOL — Agent-callable system monitoring tool.

Wraps the cluster health infrastructure so any agent can check system
status during task execution (e.g., DevOps agent verifying a deployment).
"""

import json
import os
import socket
import logging

logger = logging.getLogger("MonitorTool")

# Node IPs from config
HOPPER_IP = os.getenv("HOPPER_IP", os.getenv("HOPPER_IP", "192.168.2.102"))
LOVELACE_IP    = os.getenv("LOVELACE_IP",   os.getenv("LOVELACE_IP",    "192.168.2.101"))
TURING_IP   = os.getenv("TURING_IP",  os.getenv("TURING_IP",         "192.168.2.103"))
# backward-compat
HOPPER_IP = HOPPER_IP
LOVELACE_IP    = LOVELACE_IP
TURING_IP         = TURING_IP
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", f"http://{HOPPER_IP}:3000")


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    """Quick TCP port check."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        code = s.connect_ex((host, port))
        s.close()
        return code == 0
    except Exception:
        return False


def _http_check(url: str, timeout: float = 3.0) -> bool:
    """Quick HTTP health check (< 500 is healthy)."""
    import requests
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def check_control_plane() -> str:
    """
    Check control-plane service health (Langfuse, PostgreSQL, SPIRE, MinIO).

    Returns:
        JSON string with service health status.
    """
    services = [
        {"name": "Langfuse", "check": lambda: _http_check(f"{LANGFUSE_HOST}/api/public/health")},
        {"name": "PostgreSQL", "check": lambda: _tcp_check(HOPPER_IP, 5432)},
        {"name": "SPIRE Server", "check": lambda: _tcp_check(HOPPER_IP, 8081)},
        {"name": "MinIO API", "check": lambda: _http_check(f"http://{HOPPER_IP}:9190/minio/health/live")},
    ]
    results = []
    for svc in services:
        try:
            healthy = svc["check"]()
        except Exception:
            healthy = False
        results.append({"name": svc["name"], "healthy": healthy})

    all_healthy = all(s["healthy"] for s in results)
    down = [s["name"] for s in results if not s["healthy"]]
    summary = "All control-plane services healthy" if all_healthy else f"Down: {', '.join(down)}"
    return json.dumps({"status": "ONLINE" if all_healthy else "DEGRADED", "summary": summary, "services": results})


def check_node_connectivity() -> str:
    """
    Check network reachability of all three cluster nodes.

    Returns:
        JSON string with node connectivity status.
    """
    nodes = [
        {"name": "Lovelace (Execution)", "ip": LOVELACE_IP, "probe_port": 11434},
        {"name": "Hopper (Control)", "ip": HOPPER_IP, "probe_port": 5432},
        {"name": "Turing (Gateway)", "ip": TURING_IP, "probe_port": 80},
    ]
    results = []
    for node in nodes:
        reachable = _tcp_check(node["ip"], node["probe_port"])
        results.append({"name": node["name"], "ip": node["ip"], "reachable": reachable})

    all_ok = all(n["reachable"] for n in results)
    unreachable = [n["name"] for n in results if not n["reachable"]]
    summary = "All nodes reachable" if all_ok else f"Unreachable: {', '.join(unreachable)}"
    return json.dumps({"status": "ONLINE" if all_ok else "DEGRADED", "summary": summary, "nodes": results})


def get_system_health_report() -> str:
    """
    Comprehensive system health report combining control-plane and node status.
    Call this tool to check overall infrastructure health.

    Returns:
        JSON string with full cluster health status.
    """
    import requests

    # Control-plane services
    cp_services = [
        {"name": "Langfuse", "check": lambda: _http_check(f"{LANGFUSE_HOST}/api/public/health")},
        {"name": "PostgreSQL", "check": lambda: _tcp_check(HOPPER_IP, 5432)},
        {"name": "SPIRE Server", "check": lambda: _tcp_check(HOPPER_IP, 8081)},
        {"name": "MinIO API", "check": lambda: _http_check(f"http://{HOPPER_IP}:9190/minio/health/live")},
    ]
    cp_results = []
    for svc in cp_services:
        try:
            healthy = svc["check"]()
        except Exception:
            healthy = False
        cp_results.append({"name": svc["name"], "healthy": healthy})

    # Node connectivity + container counts via Docker API
    node_defs = [
        {"name": "Lovelace", "role": "execution", "ip": LOVELACE_IP},
        {"name": "Hopper", "role": "control", "ip": HOPPER_IP},
        {"name": "Turing", "role": "gateway", "ip": TURING_IP},
    ]
    node_results = []
    total_containers = 0
    for node in node_defs:
        container_count = 0
        healthy = False
        try:
            r = requests.get(f"http://{node['ip']}:2375/containers/json", timeout=3)
            if r.status_code == 200:
                container_count = len(r.json())
                healthy = True
        except Exception:
            # TCP fallback — just check if the node is reachable at all
            healthy = _tcp_check(node["ip"], 22, timeout=2)

        total_containers += container_count
        node_results.append({
            "name": node["name"],
            "role": node["role"],
            "ip": node["ip"],
            "healthy": healthy,
            "containers": container_count,
        })

    # Build summary
    down_cp = [s["name"] for s in cp_results if not s["healthy"]]
    down_nodes = [n["name"] for n in node_results if not n["healthy"]]
    issues = []
    if down_cp:
        issues.append(f"Control plane: {', '.join(down_cp)}")
    if down_nodes:
        issues.append(f"Nodes: {', '.join(down_nodes)}")

    status = "ONLINE" if not issues else "DEGRADED"
    summary = "All systems operational" if not issues else "; ".join(issues)

    return json.dumps({
        "status": status,
        "summary": summary,
        "total_containers": total_containers,
        "control_plane": cp_results,
        "nodes": node_results,
    })


# Agent tool functions list — register these with phi Agent tools parameter
MONITOR_TOOLS = [
    check_control_plane,
    check_node_connectivity,
    get_system_health_report,
]


