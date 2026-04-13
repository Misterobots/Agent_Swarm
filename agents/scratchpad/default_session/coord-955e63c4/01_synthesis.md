# Synthesis

# Implementation Plan: Python Health Check Script for 3-Node System

## 📁 File Structure
```
/health_check
├── health_check.py
├── config/
│   └── nodes_config.json
└── logs/
    └── health_check_{timestamp}.log
```

## 🧠 Key Implementation Details

### 1. **Node Configuration**
- **File Path**: `config/nodes_config.json`
- **Format**:
```json
{
  "nodes": ["192.168.1.10", "192.168.1.11", "192.168.1.12"]
}
```

### 2. **Core Script Functionality**
- **File Path**: `health_check.py`
- **Key Functions**:
```python
import json
import os
import platform
import subprocess
import datetime
import logging

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'nodes_config.json')
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Logging Setup
logging.basicConfig(
    filename=os.path.join(LOG_DIR, f'health_check_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_nodes_config():
    """Load node IPs from JSON config file"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)['nodes']
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Config error: {str(e)}")
        return []

def ping_node(ip):
    """Ping a single node with platform-specific parameters"""
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    try:
        output = subprocess.check_output(
            ['ping', param, '1', ip],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=2
        )
        # Extract response time (simplified parsing)
        response_time = None
        for line in output.splitlines():
            if 'time=' in line:
                response_time = float(line.split('time=')[1].split(' ')[0])
                break
        return {
            "status": "reachable",
            "response_time": response_time,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return {
            "status": "unreachable",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

def check_health_of_nodes(nodes):
    """Check health status of all nodes"""
    results = {}
    for node in nodes:
        results[node] = ping_node(node)
    return results

def generate_report(status_dict):
    """Generate human-readable report with timestamps"""
    report = []
    for node, status in status_dict.items():
        if status["status"] == "reachable":
            report.append(f"{node} ✅ Reachable | {status['response_time']:.2f}ms | {status['timestamp']}")
        else:
            report.append(f"{node} ❌ Unreachable | Error: {status['error']} | {status['timestamp']}")
    return "\n".join(report)

def main():
    """Main execution flow"""
    nodes = load_nodes_config()
    if not nodes:
        logging.error("No valid nodes in configuration")
        return
    
    status = check_health_of_nodes(nodes)
    print(generate_report(status))
    logging.info(generate_report(status))
    return status

if __name__ == '__main__':
    main()
```

## 🛠️ Implementation Steps

### 1. **Configuration Setup**
- Create `config/nodes_config.json` with your 3 node IPs
- Ensure the script has execute permissions: `chmod +x health_check.py`

### 2. **Testing & Validation**
- **Test Case 1**: All nodes reachable
  - Expected: Green status with response times
- **Test Case 2**: One node unreachable
  - Expected: Red status with error message
- **Test Case 3**: Config file missing
  - Expected: Error logged and empty report
- **Test Case 4**: Network timeout
  - Expected: Unreachable status with timeout error

### 3. **Enhancements (Optional)**
- Add alerting via email/SMS using `smtplib` or `twilio`
- Implement parallel pinging using `concurrent.futures`
- Add historical data storage with `sqlite3` or `pandas`

## 📌 Verification Criteria

| Criteria | Verification Method |
|--------|---------------------|
| Accurate ping detection | Test with known good/bad IPs |
| Graceful failure handling | Simulate network outages |
| Timestamp inclusion | Check log file timestamps |
| Config validation | Test with invalid JSON/config file |

## ⚠️ Known Limitations
- Platform-specific ping parsing (Windows vs Linux)
- Limited to 1 ping per node (configurable)
- No GUI/visualization (can be added with `matplotlib`)

## 🧪 Example Output
```
192.168.1.10 ✅ Reachable | 12.34ms | 2023-09-20T14:30:00
192.168.1.11 ❌ Unreachable | Error: Timeout expired | 2023-09-20T14:30:01
192.168.1.12 ✅ Reachable | 15.67ms | 2023-09-20T14:30:00
```

This implementation balances simplicity with robustness, using standard libraries for cross-platform compatibility while providing detailed logging and reporting.