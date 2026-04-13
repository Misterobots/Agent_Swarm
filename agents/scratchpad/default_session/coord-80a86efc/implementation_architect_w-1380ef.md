# architect — coordinate: Design and implement a Python health check script that pings all 3 nodes and reports status

```json
{
  "name": "write_file",
  "arguments": {
    "path": "/workspace/health_monitor.py",
    "content": "#!/usr/bin/env python3\n\nimport ping3\nfrom datetime import datetime\n\n# Configuration\nNODES = ['192.168.1.1', '192.168.1.2', '192.168.1.3']\nLOG_FILE = '/var/log/health_check.log'\nPING_TIMEOUT = 1  # seconds\n\ndef ping_node(node):\n    \"\"\"Ping a node and return status.\"\"\"\n    response_time = ping3.ping(node, timeout=PING_TIMEOUT)\n    return 'UP' if response_time is not None else 'DOWN'\n\ndef generate_report():\n    \"\"\"Check all nodes and log results.\"\"\"\n    results = []\n    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')\n    \n    for node in NODES:\n        status = ping_node(node)\n        results.append(f'[{timestamp}] Node: {node} | Status: {status}')\n        print(f'Node: {node} | Status: {status}')\n    \n    # Log to file\n    with open(LOG_FILE, 'a') as f:\n        for line in results:\n            f.write(line + '\\n')\n    \n    # Summary\n    up_count = sum(1 for res in results if 'UP' in res)\n    down_count = len(NODES) - up_count\n    print(f'\\nSummary: {up_count} UP, {down_count} DOWN')\n\nif __name__ == '__main__':\n    generate_report()"
  }
}
```