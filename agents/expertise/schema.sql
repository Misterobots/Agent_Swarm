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
