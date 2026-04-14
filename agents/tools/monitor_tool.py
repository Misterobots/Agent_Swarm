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
CONTROL_NODE_IP = os.getenv("CONTROL_NODE_IP", "192.168.2.102")
JUSTIN_PC_IP = os.getenv("JUSTIN_PC_IP", "192.168.2.101")
R730_IP = os.getenv("R730_IP", "192.168.2.103")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", f"http://{CONTROL_NODE_IP}:3000")


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
        {"name": "PostgreSQL", "check": lambda: _tcp_check(CONTROL_NODE_IP, 5432)},
        {"name": "SPIRE Server", "check": lambda: _tcp_check(CONTROL_NODE_IP, 8081)},
        {"name": "MinIO API", "check": lambda: _http_check(f"http://{CONTROL_NODE_IP}:9190/minio/health/live")},
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
        {"name": "Justin-PC (Execution)", "ip": JUSTIN_PC_IP, "probe_port": 11434},
        {"name": "Control Node", "ip": CONTROL_NODE_IP, "probe_port": 5432},
        {"name": "R730 (Gateway)", "ip": R730_IP, "probe_port": 80},
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
        {"name": "PostgreSQL", "check": lambda: _tcp_check(CONTROL_NODE_IP, 5432)},
        {"name": "SPIRE Server", "check": lambda: _tcp_check(CONTROL_NODE_IP, 8081)},
        {"name": "MinIO API", "check": lambda: _http_check(f"http://{CONTROL_NODE_IP}:9190/minio/health/live")},
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
        {"name": "Justin-PC", "role": "execution", "ip": JUSTIN_PC_IP},
        {"name": "Control Node", "role": "control", "ip": CONTROL_NODE_IP},
        {"name": "R730", "role": "gateway", "ip": R730_IP},
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
