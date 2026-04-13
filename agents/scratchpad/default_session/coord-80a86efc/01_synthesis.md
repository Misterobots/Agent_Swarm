# Synthesis

**Implementation Plan for Python Health Check Script**

---

### **1. Dependencies**
- **Library**: `ping3` (install via `pip install ping3`)
- **System Permissions**: Write access to `/var/log/health_check.log` (or adjust path as needed)

---

### **2. Script Structure**
**File Path**: `/opt/health_check/health_monitor.py`

```python
import ping3
from datetime import datetime

# Configuration
NODES = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
LOG_FILE = "/var/log/health_check.log"
PING_TIMEOUT = 1  # seconds

def ping_node(node):
    """Ping a node and return status."""
    response_time = ping3.ping(node, timeout=PING_TIMEOUT)
    return "UP" if response_time is not None else "DOWN"

def generate_report():
    """Check all nodes and log results."""
    results = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for node in NODES:
        status = ping_node(node)
        results.append(f"[{timestamp}] Node: {node} | Status: {status}")
        print(f"Node: {node} | Status: {status}")
    
    # Log to file
    with open(LOG_FILE, "a") as f:
        for line in results:
            f.write(line + "\n")
    
    # Summary
    up_count = sum(1 for res in results if "UP" in res)
    down_count = len(NODES) - up_count
    print(f"\nSummary: {up_count} UP, {down_count} DOWN")

if __name__ == "__main__":
    generate_report()
```

---

### **3. Key Implementation Details**
- **Ping Logic**: Uses `ping3` for cross-platform ICMP pinging.
- **Logging**: Appends timestamped results to `/var/log/health_check.log`.
- **Output**: Real-time console output + persistent log file.
- **Summary**: Counts and reports total UP/DOWN nodes.

---

### **4. Verification Steps**
1. **Install Dependency**:
   ```bash
   pip install ping3
   ```
2. **Run Script**:
   ```bash
   python /opt/health_check/health_monitor.py
   ```
3. **Check Output**:
   - Console: Immediate status of each node.
   - Log File: `/var/log/health_check.log` (verify entries match console output).
4. **Edge Case Testing**:
   - Simulate node downtime (e.g., disconnect network cable).
   - Ensure script handles permission errors writing to log file.

---

### **5. Constraints & Notes**
- **Permissions**: Ensure the script runs with write access to `/var/log`.
- **Firewall**: Ensure ICMP traffic is allowed on target nodes (may require `sudo` or firewall rules).
- **Alternative Ping Method**: If `ping3` is unavailable, replace with `subprocess` calls to system `ping` (less reliable across OSes).

---

### **6. Next Steps**
- Add email/SMS alerts for critical failures.
- Containerize with Docker for deployment consistency.
- Schedule via cron (e.g., `*/5 * * * * python /opt/health_check/health_monitor.py`).