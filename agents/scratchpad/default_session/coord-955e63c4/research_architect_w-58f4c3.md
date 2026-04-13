# architect — Design the overall structure of the Python script, including functions for pinging nodes and reporting results.

```json
{
  "name": "write_file",
  "arguments": {
    "path": "/workspace/health_check.py",
    "content": "#!/usr/bin/env python3\n\nimport subprocess\nimport platform\nimport json\nimport os\n\n# Configuration loading\nCONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'nodes_config.json')\n\ndef load_nodes_config():\n    \"\"\"Load node IPs from JSON config file\"\"\"\n    with open(CONFIG_PATH, 'r') as f:\n        return json.load(f)['nodes']\n\ndef ping_node(ip):\n    \"\"\"Ping a single node with platform-specific parameters\"\"\"\n    param = '-n' if platform.system().lower() == 'windows' else '-c'\n    try:\n        output = subprocess.check_output(\n            ['ping', param, '1', ip],\n            stderr=subprocess.STDOUT,\n            universal_newlines=True,\n            timeout=2\n        )\n        return \"reachable\" if \"0% packet loss\" in output else \"unreachable\"\n    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):\n        return \"unreachable\"\n\ndef check_health_of_nodes(nodes):\n    \"\"\"Check health status of all nodes\"\"\"\n    return {node: ping_node(node) for node in nodes}\n\ndef generate_report(status_dict):\n    \"\"\"Generate human-readable report\"\"\"\n    report = []\n    for node, status in status_dict.items():\n        report.append(f'{node}: {status}')\n    return '\\n'.join(report)\n\ndef main():\n    \"\"\"Main execution flow\"\"\"\n    nodes = load_nodes_config()\n    status = check_health_of_nodes(nodes)\n    print(generate_report(status))\n    return status\n\nif __name__ == '__main__':\n    main()"
  }
}
```