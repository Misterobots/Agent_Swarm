-- =============================================================================
-- Swarm ExpertiseTemplate Schema
-- Applied to control plane PostgreSQL (langfuse DB, swarm schema)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS swarm;

-- -----------------------------------------------------------------------------
-- expertise_templates: master record for each agent template
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.expertise_templates (
    id VARCHAR(128) PRIMARY KEY,             -- e.g., "code_developer"
    name VARCHAR(255) NOT NULL,              -- Human-readable name
    description TEXT,
    intent VARCHAR(64) NOT NULL,             -- SemanticRouter intent key
    current_version VARCHAR(32) NOT NULL DEFAULT '1.0',

    -- Learnable parameters
    system_prompt TEXT,                      -- Agent system instructions
    capabilities TEXT[] NOT NULL,            -- PostgreSQL array of capability strings
    security_level VARCHAR(32) DEFAULT 'L2_USER',
    default_model VARCHAR(128),              -- e.g., "qwen2.5-coder:14b"
    config JSONB DEFAULT '{}',               -- temperature, max_tokens, etc.

    -- Metadata
    source VARCHAR(32) DEFAULT 'manual',     -- 'seed', 'manual', 'auto_evolved'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- expertise_template_versions: snapshot of parameters at each version
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.expertise_template_versions (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(128) NOT NULL REFERENCES swarm.expertise_templates(id),
    version VARCHAR(32) NOT NULL,            -- "1.0", "1.1", "2.0"

    -- Snapshot of parameters
    system_prompt TEXT,
    capabilities TEXT[],
    config JSONB DEFAULT '{}',

    -- Performance metrics for this version
    avg_score FLOAT DEFAULT 0.0,
    total_invocations INTEGER DEFAULT 0,
    successful_invocations INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP,                   -- When this version became "latest"

    UNIQUE(template_id, version)
);

-- -----------------------------------------------------------------------------
-- performance_history: per-invocation performance records
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.performance_history (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(128) NOT NULL REFERENCES swarm.expertise_templates(id),
    template_version VARCHAR(32),
    trace_id VARCHAR(255),                   -- Langfuse trace ID
    session_id VARCHAR(255),
    intent VARCHAR(64),

    -- Scores from MarsRL loop
    solver_score FLOAT,
    verifier_score FLOAT,
    final_score FLOAT,
    corrector_invoked BOOLEAN DEFAULT FALSE,
    iterations INTEGER DEFAULT 1,
    latency_ms INTEGER,

    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_perf_template
    ON swarm.performance_history(template_id, template_version);

CREATE INDEX IF NOT EXISTS idx_perf_score
    ON swarm.performance_history(final_score);

CREATE INDEX IF NOT EXISTS idx_perf_recorded
    ON swarm.performance_history(recorded_at);

CREATE INDEX IF NOT EXISTS idx_versions_template
    ON swarm.expertise_template_versions(template_id, version);

-- -----------------------------------------------------------------------------
-- training_runs: tracks each training pipeline execution
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.training_runs (
    id SERIAL PRIMARY KEY,
    run_type VARCHAR(32) NOT NULL,        -- export, synthetic, training, conversion
    target_model VARCHAR(128),
    dataset_path TEXT,
    dataset_size INTEGER,
    status VARCHAR(32) DEFAULT 'pending',  -- pending, running, completed, failed
    config JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',            -- loss, reward, etc.
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- -----------------------------------------------------------------------------
-- model_versions: fine-tuned model registry
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.model_versions (
    id SERIAL PRIMARY KEY,
    base_model VARCHAR(128) NOT NULL,
    version_tag VARCHAR(64) NOT NULL,
    adapter_path TEXT,
    gguf_path TEXT,
    ollama_model_name VARCHAR(128),
    training_run_id INTEGER REFERENCES swarm.training_runs(id),
    status VARCHAR(32) DEFAULT 'candidate', -- candidate, ab_testing, promoted, retired
    avg_score FLOAT DEFAULT 0.0,
    total_invocations INTEGER DEFAULT 0,
    promoted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_versions_status
    ON swarm.model_versions(status);

CREATE INDEX IF NOT EXISTS idx_training_runs_status
    ON swarm.training_runs(status, run_type);

-- -----------------------------------------------------------------------------
-- ab_tests: A/B test configurations for model comparison
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.ab_tests (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(128) REFERENCES swarm.expertise_templates(id),
    candidate_model VARCHAR(128) NOT NULL,
    base_model VARCHAR(128) NOT NULL,
    traffic_split FLOAT DEFAULT 0.2,
    min_invocations INTEGER DEFAULT 100,
    status VARCHAR(32) DEFAULT 'active',   -- active, concluded, cancelled
    winner VARCHAR(32),                     -- candidate, base, or NULL
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    concluded_at TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- ab_test_results: per-invocation scores during A/B tests
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS swarm.ab_test_results (
    id SERIAL PRIMARY KEY,
    test_id INTEGER REFERENCES swarm.ab_tests(id),
    model_used VARCHAR(128),
    score FLOAT,
    latency_ms INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ab_tests_active
    ON swarm.ab_tests(template_id, status);

CREATE INDEX IF NOT EXISTS idx_ab_results_test
    ON swarm.ab_test_results(test_id, model_used);
