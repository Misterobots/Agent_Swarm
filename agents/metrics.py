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

# ---------------------------------------------------------------------------
# Live Training Step Metrics (updated by PrometheusTrainingCallback)
# ---------------------------------------------------------------------------

TRAINING_IS_ACTIVE = Gauge(
    'training_is_active',
    'Whether training is currently running (1=yes, 0=no)',
)
TRAINING_STEP_CURRENT = Gauge(
    'training_step_current',
    'Current training step number',
)
TRAINING_EPOCH_CURRENT = Gauge(
    'training_epoch_current',
    'Current training epoch',
)
TRAINING_LOSS = Gauge(
    'training_loss',
    'Current training loss',
)
TRAINING_GRAD_NORM = Gauge(
    'training_grad_norm',
    'Current gradient norm',
)
TRAINING_LEARNING_RATE = Gauge(
    'training_learning_rate_current',
    'Current learning rate',
)
TRAINING_REWARD_MEAN = Gauge(
    'training_reward_mean',
    'Mean reward across GRPO group',
)
TRAINING_REWARD_STD = Gauge(
    'training_reward_std',
    'Reward standard deviation across GRPO group',
)
TRAINING_COMPLETION_LEN_MEAN = Gauge(
    'training_completion_length_mean',
    'Mean completion length in tokens',
)
TRAINING_COMPLETION_LEN_MIN = Gauge(
    'training_completion_length_min',
    'Min completion length in tokens',
)
TRAINING_COMPLETION_LEN_MAX = Gauge(
    'training_completion_length_max',
    'Max completion length in tokens',
)
TRAINING_ENTROPY = Gauge(
    'training_entropy',
    'Policy entropy',
)
TRAINING_STEP_TIME = Gauge(
    'training_step_time_seconds',
    'Time per training step in seconds',
)
TRAINING_TOTAL_STEPS = Gauge(
    'training_total_steps',
    'Total training steps expected (set once at train begin)',
)
TRAINING_PHASE = Gauge(
    'training_phase_ordinal',
    'Current pipeline phase as ordinal: 0=idle, 1=synthetic_generation, '
    '2=security_scan, 3=dataset_download, 4=model_loading, 5=training, '
    '6=saving_adapter, 7=completed, 8=failed',
)
TRAINING_TIME_BUDGET_SEC = Gauge(
    'training_time_budget_seconds',
    'Wall-clock training time budget in seconds (0 = unlimited)',
)
TRAINING_BUDGET_START = Gauge(
    'training_budget_start_epoch',
    'Unix epoch when the training time budget clock started',
)
TRAINING_RUN_ID = Gauge(
    'training_run_id',
    'Database ID of the currently active training run',
)

# Phase name <-> ordinal mapping (keep in sync with the gauge description)
PHASE_ORDINALS: dict[str, int] = {
    "idle": 0,
    "synthetic_generation": 1,
    "security_scan": 2,
    "dataset_download": 3,
    "model_loading": 4,
    "training": 5,
    "saving_adapter": 6,
    "completed": 7,
    "failed": 8,
}
PHASE_NAMES: dict[int, str] = {v: k for k, v in PHASE_ORDINALS.items()}

# ---------------------------------------------------------------------------
# Infrastructure Health Metrics
# ---------------------------------------------------------------------------

REDIS_CONNECTED = Gauge(
    'redis_connected',
    'Whether the dispatcher is connected to real Redis (1=connected, 0=in-memory fallback)'
)

# ---------------------------------------------------------------------------
# IoT Sensitive Action Metrics
# ---------------------------------------------------------------------------

IOT_SENSITIVE_ACTIONS_TOTAL = Counter(
    'iot_sensitive_actions_total',
    'Total sensitive IoT actions observed by service layer',
    ['domain', 'service', 'outcome']
)

IOT_SENSITIVE_ACTIONS_BLOCKED_TOTAL = Counter(
    'iot_sensitive_actions_blocked_total',
    'Total sensitive IoT actions blocked due to missing confirmation',
    ['domain', 'service']
)
