from prometheus_client import Gauge, Counter, Histogram

# Central Registry for Swarm Metrics

# 1. Agent State (Gauge)
# Values: 0=Offline, 1=Idle, 2=Working, 3=Error
AGENT_STATE = Gauge(
    'agent_state', 
    'Current operational state of the agent', 
    ['agent_name']
)

# 2. Workflow Velocity (Counter)
# Tracks total steps completed, tagged by result status
WORKFLOW_STEPS = Counter(
    'workflow_steps_total', 
    'Total workflow steps executed', 
    ['status', 'agent_type']
)

# 3. Latency (Histogram)
# Measures how long operations take
AGENT_LATENCY = Histogram(
    'agent_operation_seconds', 
    'Time spent processing a request', 
    ['agent_name', 'operation_type']
)
