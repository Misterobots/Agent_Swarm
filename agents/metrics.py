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

# ---------------------------------------------------------------------------
# Training Pipeline Metrics
# ---------------------------------------------------------------------------

TRAINING_RUNS_TOTAL = Counter(
    'training_runs_total',
    'Total training pipeline runs',
    ['run_type', 'status']  # run_type: export/synthetic/training/conversion
)

TRAINING_DATASET_SIZE = Gauge(
    'training_dataset_size',
    'Current training dataset size in trajectories',
    ['dataset_type']  # exported, synthetic
)

MODEL_VERSION_ACTIVE = Gauge(
    'model_version_active',
    'Currently active model version (1=active, 0=inactive)',
    ['template_id', 'model_name', 'version_tag']
)

AB_TEST_SCORE = Gauge(
    'ab_test_score',
    'Current average score in an active A/B test',
    ['test_id', 'arm']  # arm: candidate or base
)

MARS_LOOP_SCORE = Histogram(
    'mars_loop_final_score',
    'Distribution of MarsRL final quality scores',
    ['intent', 'template_id'],
    buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
)
