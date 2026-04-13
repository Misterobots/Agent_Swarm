# researcher — coordinate: Design and implement a Python health check script that pings all 3 nodes and reports status

To design and implement a Python health check script that pings three nodes and reports their status, we can use the `subprocess` module to execute system commands like `ping`. Below is a step-by-step guide along with a sample script.

### Step 1: Define Node Addresses
First, define the IP addresses or hostnames of the three nodes you want to ping. For this example, let's assume the nodes have the following addresses:
- Node 1: `192.168.1.1`
- Node 2: `192.168.1.2`
- Node 3: `192.168.1.3`

### Step 2: Create a Function to Ping Each Node
We'll create a function that pings each node and returns the status (reachable or unreachable).

```python
import subprocess

def ping_node(ip):
    try:
        # Use 'ping' command with '-c 1' for one packet
        output = subprocess.check_output(['ping', '-c', '1', ip], stderr=subprocess.STDOUT, universal_newlines=True)
        if "0% packet loss" in output:
            return f"{ip} is reachable."
        else:
            return f"{ip} is unreachable."
    except subprocess.CalledProcessError as e:
        return f"{ip} is unreachable. Error: {e.output}"

def check_health_of_nodes(nodes):
    statuses = []
    for node in nodes:
        status = ping_node(node)
        statuses.append(status)
    return statuses

# Define the list of nodes
nodes = ['192.168.1.1', '192.168.1.2', '192.168.1.3']

# Check the health of the nodes
health_statuses = check_health_of_nodes(nodes)

# Print the results
for status in health_statuses:
    print(status)
```

### Step 3: Explanation of the Script

1. **Import `subprocess`**: This module allows us to run system commands.
2. **Define `ping_node(ip)`**: This function takes an IP address, pings it using the `ping` command with one packet (`-c 1`), and checks the output for "0% packet loss" to determine reachability.
3. **Handle Exceptions**: If the ping fails (e.g., network issues or unreachable node), a `CalledProcessError` is raised, and we catch it to report that the node is unreachable.
4. **Define `check_health_of_nodes(nodes)`**: This function iterates over a list of nodes, calls `ping_node()` for each one, and collects the statuses in a list.
5. **Main Execution**:
   - Define the list of node IP addresses.
   - Call `check_health_of_nodes` to get the status of each node.
   - Print the results.

### Step 4: Running the Script

To run this script, save it to a file (e.g., `health_check.py`) and execute it using Python:

```bash
python health_check.py
```

This will output the reachability status of each node.

### Notes:
- This script uses the Unix/Linux `ping` command. If you're on Windows, you might need to adjust the ping command to use `-n 1` instead of `-c 1`.
- The script assumes that nodes are reachable within a reasonable time frame. You may want to add timeout functionality for very slow or unreachable nodes.
- This is a basic implementation and can be extended with more features such as logging, reporting, or integrating with monitoring systems.

### Conclusion
This Python script provides a simple way to check the reachability of multiple nodes by pinging them and reporting their status. Adjustments may be necessary based on your specific environment and requirements.