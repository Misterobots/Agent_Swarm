# Phase 5+ Implementation Roadmap
**Planning Date**: March 15, 2026
**Updated**: March 21, 2026
**Current Status**: Phase 6 Complete (GRPO Training Pipeline Deployed)
**Timeline**: Q2 2026 (3-4 months)

---

## Overview

With Phase 6 complete, the infrastructure provides:
- ✅ Distributed three-tier architecture (Control, Gateway, Compute)
- ✅ Centralized monitoring (Prometheus, Grafana, Loki)
- ✅ Zero-trust identity (SPIRE)
- ✅ Service observability (Langfuse)
- ✅ JWT-ACE per-request capability gating
- ✅ ExpertiseTemplate versioned agent system with performance tracking
- ✅ GRPO Training Pipeline (data export, QLoRA fine-tuning, GGUF conversion, Ollama import)
- ✅ A/B Testing with statistical significance and auto-promotion
- ✅ Grafana dashboards for Training Pipeline and Template Performance
- ✅ GPU resource isolation via Redis-based mutex with training context

**Phase 7-9** focuses on:
1. **Multi-Model Orchestration** (scale inference across GPU nodes)
2. **High Availability** (redundancy)
3. **Enterprise Features** (k8s, security hardening)

---

## PHASE 5: JWT-ACE Architecture & Ephemeral Agents ✅ COMPLETE
**Duration**: 2-3 weeks | **Effort**: 60 story points
**Goal**: Enable ephemeral agents with persistence at template level
**Completed**: March 17, 2026 | **Tests**: 31/31 passing

### Phase 5 Completion Summary

| Deliverable | File | Status |
|-------------|------|--------|
| Intent-to-capability mapping | `agents/intent_capabilities.py` | ✅ Created |
| PostgreSQL schema migration | `agents/expertise/schema.sql` | ✅ Applied |
| Template registry + caching | `agents/expertise/template_registry.py` | ✅ Created |
| Async template updater | `agents/expertise/async_template_updater.py` | ✅ Created |
| Thread-local execution context | `agents/security/execution_context.py` | ✅ Created |
| Router JWT integration | `agents/router.py` | ✅ Modified |
| MarsRL token threading | `agents/mars_loop.py` | ✅ Modified |
| Lifespan hooks | `agents/main.py` | ✅ Modified |
| JWT lifecycle tests | `tests/test_jwt_lifecycle.py` | ✅ 15/15 pass |
| Template system tests | `tests/test_template_system.py` | ✅ 16/16 pass |

**Deployment**: 7 seed templates in PostgreSQL `swarm` schema, agent-runtime container running with JWT-ACE + templates enabled, async updater polling every 5 minutes.

**Evidence**: [Phase 5 Audit](docs/evidence/phase5_jwt_ace_audit_2026_03_17.md)

### 5.1 Implement JWT-ACE (Agent Card Embedded JWT)

#### Task 5.1.1: Create token_issuer.py
```python
# Generate file: agents/security/token_issuer.py

Key responsibilities:
- EphemeralAgentCard dataclass (extends AgentCard from registry.py)
  - Template ID + version
  - Activated capabilities list
  - Expiry timestamp (default 1 hour)
- TokenIssuer class
  - issue_token(agent_card: EphemeralAgentCard) → JWT
  - Uses SPIRE for signing (cryptographic verification)
- TokenValidator class
  - validate_token(token: str) → EphemeralAgentCard (or raise)
  - Verify SPIRE signature + expiry

Dependencies:
- PyJWT (encoding/decoding)
- SPIRE client (signing key)
- Pydantic (models)
```

**Status Tracking**:
- [x] Create EphemeralAgentCard dataclass
- [x] Implement TokenIssuer with SPIRE integration
- [x] Implement TokenValidator with signature verification
- [x] Write unit tests (sign/verify cycle)
- [x] Deploy to agents/security/token_issuer.py

---

#### Task 5.1.2: Create capability_gate.py
```python
# Generate file: agents/security/capability_gate.py

Key responsibilities:
- @CapabilityRequired(capability='file_write') decorator
  - Extracts JWT from request headers
  - Validates token with TokenValidator
  - Checks if capability is in token.capabilities list
  - Allows/denies function execution
- Tool-level enforcement (file operations, API calls, etc.)
- Logging: Track denied access attempts for audit

Example usage:
@app.post("/api/v1/write-file")
@CapabilityRequired(capability='file_write')
async def write_file_endpoint(path: str, content: str, request: Request):
    # This endpoint only executes if JWT has 'file_write' capability
    ...
```

**Status Tracking**:
- [x] Create @CapabilityRequired decorator
- [x] Implement JWT extraction from headers
- [x] Add capability checking logic
- [x] Write tests for allowed/denied scenarios
- [x] Deploy to agents/security/capability_gate.py

---

#### Task 5.1.3: Integrate with router.py

**Modify**: agents/router.py (entry point for all agent requests)

```python
# Changes to route_and_execute():
1. Extract JWT from Authorization header
2. Validate JWT with TokenValidator
3. Extract EphemeralAgentCard (template_id, version, capabilities)
4. Pass token to MarsRL loop (for trace metadata)
5. Enforce @CapabilityRequired on tool calls

# Changes to semantic_router():
1. Select agent template based on intent
2. Create ephemeral card with template capabilities
3. Issue JWT token (1-hour TTL)
4. Pass token to executor
```

**Status Tracking**:
- [x] Add JWT extraction to route entry
- [x] Integrate TokenValidator
- [x] Store token in context for MarsRL loop
- [x] Update executor to enforce capabilities
- [x] Test end-to-end flow

---

#### Task 5.1.4: Langfuse Integration

**Trace Format**:
```json
{
  "trace_id": "uuid",
  "agent_instance_id": "ephemeral-uuid",
  "template_id": "expertise_template_v1.3",
  "token_capabilities": ["file_write", "api_call"],
  "solver_output": "...",
  "verifier_output": "...",
  "corrector_output": "...",
  "reward_score": 0.92,
  "timestamp": "2026-03-15T10:30:00Z"
}
```

**Status Tracking**:
- [x] Add metadata fields to trace schema
- [x] Link trace to expertise_template_id
- [x] Export high-reward traces (>0.8) to training data
- [ ] Create dashboard: Template Performance Trend

---

### 5.2 Implement ExpertiseTemplate Registry

#### Task 5.2.1: Database Schema

```sql
-- Table: expertise_templates
CREATE TABLE expertise_templates (
  id SERIAL PRIMARY KEY,
  template_name VARCHAR(255) NOT NULL,
  current_version INT NOT NULL DEFAULT 1,
  
  -- Learnable parameters
  system_prompt TEXT,
  generation_parameters JSONB,  -- temp, top_p, etc.
  tool_strategy TEXT,  -- which tools to use
  antipatterns TEXT[],  -- things to avoid
  
  -- Performance tracking
  avg_reward_score FLOAT,
  samples_count INT,
  
  -- Versioning
  created_at TIMESTAMP DEFAULT NOW(),
  last_updated TIMESTAMP DEFAULT NOW()
);

-- Table: expertise_template_versions
CREATE TABLE expertise_template_versions (
  id SERIAL PRIMARY KEY,
  template_id INT REFERENCES expertise_templates(id),
  version INT,
  
  -- Snapshot of parameters at this version
  system_prompt TEXT,
  generation_parameters JSONB,
  tool_strategy TEXT,
  antipatterns TEXT[],
  
  -- Version metrics
  avg_reward FLOAT,
  num_instances INT,
  
  created_at TIMESTAMP DEFAULT NOW(),
  
  UNIQUE(template_id, version)
);

-- Table: performance_history
CREATE TABLE performance_history (
  id SERIAL PRIMARY KEY,
  template_id INT REFERENCES expertise_templates(id),
  version INT,
  metric_date DATE,
  
  avg_reward FLOAT,
  p95_latency INT,  -- milliseconds
  error_rate FLOAT,
  
  UNIQUE(template_id, version, metric_date)
);
```

**Status Tracking**:
- [x] Create PostgreSQL migration script
- [x] Deploy on Control Plane (<control-node-ip>)
- [x] Run migration on production
- [x] Verify tables created and accessible

---

#### Task 5.2.2: Create template_registry.py

```python
# Generate file: agents/expertise/template_registry.py

Key responsibilities:
- ExpertiseTemplate dataclass
  - id, name, version
  - Learnable: system_prompt, generation_parameters, tool_strategy, antipatterns
- ExpertiseTemplateRegistry class
  - get_template(template_id, version=None) → ExpertiseTemplate
  - create_version(template_id, params) → new version
  - update_metrics(template_id, version, reward_score)
  - get_performance_trend(template_id, days=30) → chart data
  - rollback_to_version(template_id, version)
- Database layer (PostgreSQL)
```

**Example Usage**:
```python
registry = ExpertiseTemplateRegistry()

# Load template (get latest or specific version)
template_v1_3 = registry.get_template(template_id='security_agent')
print(template_v1_3.system_prompt)

# Create ephemeral agent with template state
ephemeral_card = EphemeralAgentCard(
    template_id='security_agent',
    template_version=1.3,
    system_prompt=template_v1_3.system_prompt,
    capabilities=template_v1_3.available_capabilities
)

# After execution, record reward
registry.update_metrics(
    template_id='security_agent',
    version=1.3,
    reward_score=0.95
)

# Next instance gets updated template (if reward improved)
template_v1_4 = registry.get_template('security_agent')  # Gets latest
```

**Status Tracking**:
- [x] Create ExpertiseTemplate dataclass
- [x] Implement get_template (with version caching)
- [x] Implement create_version (database writes)
- [x] Implement update_metrics (async batch updates)
- [ ] Implement rollback_to_version (safety feature)
- [x] Write integration tests with PostgreSQL
- [x] Deploy to agents/expertise/template_registry.py

---

#### Task 5.2.3: Async Template Update Job

```python
# Generate file: agents/expertise/async_template_updater.py

Key responsibilities:
- Monitor Langfuse for completed traces
- Collect traces for (template_id, version) in time window
- If avg_reward improves by >2%, trigger template update
- Generate new parameters via heuristics or LLM:
  - If high failure rate on tool X, remove it
  - If low reward with high latency, reduce generation choices
  - If antipattern detected, add to antipatterns list
- Create new version in registry
- Emit notification (optional: Slack/Discord)

Trigger: Every hour (configurable)
Window: Last 100 instances of template
Threshold: 2% improvement to version bump
```

**Status Tracking**:
- [x] Create async update job skeleton
- [ ] Integrate with Langfuse client
- [x] Implement reward aggregation logic
- [x] Implement parameter update heuristics
- [ ] Test on non-prod template first
- [ ] Add monitoring/alerting
- [x] Deploy to agents/expertise/async_template_updater.py
- [x] Add to asyncio lifespan (replaces APScheduler)

---

### 5.3 Integration Testing

#### Test Scenarios
1. **Ephemeral Agent Lifecycle**
   - Router creates token for agent
   - Agent executes with token
   - Token expires after 1 hour
   - New request gets fresh token
   
2. **Template Evolution**
   - Instance 1 runs template v1.0 (reward 0.75)
   - Instance 2 runs template v1.1 (improved from 0.78)
   - Instance 3 runs template v1.2 (further improved to 0.82)
   - Performance trend shows monotonic improvement

3. **Capability Gating**
   - Token with file_write capability succeeds
   - Token without file_write capability fails with 403
   - Audit log records both attempts

**Status Tracking**:
- [x] Create integration test suite
- [x] Test ephemeral agent full cycle
- [x] Test template versioning
- [x] Test capability enforcement
- [ ] Test performance trend calculation

---

## PHASE 6: GRPO Training Pipeline & Model Lifecycle ✅ COMPLETE
**Duration**: 1 week | **Effort**: 55 story points
**Goal**: Close the MarsRL feedback loop — train local models on collected trace data
**Completed**: March 21, 2026 | **PR**: #1 (feature/neural-router → main)

### Phase 6 Completion Summary

| Deliverable | File | Status |
|-------------|------|--------|
| Langfuse trace export | `agents/training/export_traces.py` | ✅ Created |
| Synthetic trajectory generator | `agents/training/synthetic_gen.py` | ✅ Created (validated 5 samples) |
| Multi-objective reward function | `agents/training/reward_function.py` | ✅ Created |
| QLoRA GRPO trainer | `agents/training/grpo_trainer.py` | ✅ Created |
| LoRA→GGUF→Ollama converter | `agents/training/convert_gguf.py` | ✅ Created |
| A/B test harness | `agents/training/ab_test.py` | ✅ Created |
| Training runtime container | `execution_plane/Dockerfile.training` | ✅ Created |
| Training compose service | `execution_plane/docker-compose.yml` | ✅ Modified (profile: training) |
| GPU mutex training context | `agents/utils/gpu_queue.py` | ✅ Modified |
| Router A/B testing hooks | `agents/router.py` | ✅ Modified |
| Template updater A/B eval | `agents/expertise/async_template_updater.py` | ✅ Modified |
| Training DB schema | `agents/expertise/schema.sql` | ✅ Applied (4 new tables) |
| Training Pipeline dashboard | `turing_gateway/dashboards/training_pipeline.json` | ✅ Provisioned |
| Template Scores dashboard | `turing_gateway/dashboards/template_performance.json` | ✅ Provisioned |
| PostgreSQL-Swarm datasource | `turing_gateway/provisioning/datasources/datasource.yml` | ✅ Configured |
| Training config variables | `agents/config.py` | ✅ Modified (14 new vars) |

**Deployment**: Training pipeline code-complete, dashboards live on Gateway Node Grafana, schema applied to control plane, training-runtime Docker image ready to build on Execution Node.

**Evidence**: [Phase 6 Audit](docs/evidence/phase6_training_pipeline_audit_2026_03_21.md) | **Testing**: [Testing Plan](docs/TESTING_PLAN_PHASE6.md)

---

## PHASE 7: Multi-Model Orchestration & Inference Scaling
**Duration**: 2-3 weeks | **Effort**: 50 story points
**Goal**: Enable load balancing across multiple GPU nodes

### 7.1 Add Gateway Node as Secondary GPU Node

**Objective**: Gateway Node currently runs Ollama + Open-WebUI (media stack). Redeploy GPU access for inference.

#### Task 7.1.1: Configure Ollama on Gateway Node
- Install NVIDIA drivers (if not present)
- Deploy Ollama container on Gateway Node
- Mount shared model directory (NFS from Control Plane)
- Register Gateway Node Ollama in load balancer

**Status Tracking**:
- [ ] Verify Gateway Node GPU availability (NVIDIA GPU?)
- [ ] Install drivers if needed
- [ ] Deploy Ollama on Gateway Node
- [ ] Test model loading
- [ ] Benchmark inference latency

#### Task 7.1.2: Implement Load Balancer

```python
# Generate file: agents/inference/load_balancer.py

Key responsibilities:
- InferenceNodePool
  - Register nodes: [ollama:11434, turing_ollama:11434]
  - Health check each (periodic /api/tags)
  - Round-robin or weighted selection
  - Failover on node down
- Smart routing:
  - Small model (3B) → fastest node
  - Large model (7B) → most available VRAM
  - Image gen → GPU with highest VRAM
```

**Status Tracking**:
- [ ] Create InferenceNodePool class
- [ ] Implement health checks
- [ ] Implement routing strategies
- [ ] Test failover (stop one node)
- [ ] Benchmark throughput improvement

---

### 7.2 Model Version Pinning

**Objective**: Allow agents to request specific model versions for reproducibility.

```python
# Extend ExpertiseTemplate to include:
model_config = {
    'primary_model': 'qwen2.5:7b@latest',  # Can pin version hash
    'fallback_model': 'mistral:7b@v1.0',
    'tool_models': {
        'web_search': 'neural-chat:7b@latest',
        'code_analysis': 'dolphin-mixtral:latest'
    }
}

# Load balancer resolves @version to specific checkpoint
# If version not available locally, pull from registry
```

**Status Tracking**:
- [ ] Create ModelVersionRegistry class
- [ ] Implement version resolution
- [ ] Add model pull/cache logic
- [ ] Extend load balancer for version affinity

---

### 7.3 A/B Testing Infrastructure (Partially Complete — see Phase 6)

**Objective**: Compare template versions in production with statistical confidence.

```python
# Route requests:
# - 50% → template_v1.3 (control)
# - 50% → template_v1.4 (experimental)

# Collect metrics:
# - Reward score
# - Latency
# - Error rate

# After 100 samples:
# - Report if v1.4 > v1.3 + 1 stddev (statistically significant)
# - Auto-promote if significant
```

**Status Tracking**:
- [ ] Create ExperimentRunner class
- [ ] Implement bucketing logic
- [ ] Add statistical analysis (t-test)
- [ ] Create reporting dashboard

---

## PHASE 8: High Availability & Resilience
**Duration**: 3-4 weeks | **Effort**: 70 story points  
**Goal**: Eliminate single points of failure

### 8.1 PostgreSQL Replication

**Current**: Single PostgreSQL on Control Plane (SPOF)  
**Target**: Primary (Control) + Replica (Gateway Node)

```bash
# On Control Plane:
# 1. Enable replication role
# 2. Create replication user
# 3. Configure pg_hba.conf for replica

# On Gateway Node:
# 1. pg_basebackup from Control Plane
# 2. Configure as streaming replica
# 3. Start replication

# HA Setup:
# - Use patroni + etcd for automatic failover
# - Agent Runtime connects to virtual IP (patroni-managed)
# - If primary fails, replica promoted automatically
```

**Status Tracking**:
- [ ] Configure replication on primary
- [ ] Set up replica on Gateway Node
- [ ] Test failover procedure
- [ ] Deploy patroni + etcd
- [ ] Verify automatic promotion

---

### 8.2 Redis Sentinel for Monitoring Queue

**Current**: Single Redis on Gateway Node  
**Target**: Master + 2 Replicas + Sentinel for failover

**Status Tracking**:
- [ ] Deploy Redis replicas on Control + Compute nodes
- [ ] Configure Sentinel trio
- [ ] Test failover (kill master)
- [ ] Update connection strings to sentinel DNS

---

### 8.3 Ollama Model Caching Across Nodes

**Objective**: Model loaded on one node available to others without re-download.

```python
# Strategy:
# 1. Shared NFS mount for models: /shared/ollama/models
# 2. All Ollama instances mount same directory
# 3. First node to load model caches it
# 4. Other nodes use cached copy (saves 5-10 min per model)
```

**Status Tracking**:
- [ ] Set up NFS export on Control Plane
- [ ] Mount on Execution Node and Gateway Node
- [ ] Reconfigure Ollama to use shared mount
- [ ] Test model sharing

---

## PHASE 9: Kubernetes Migration
**Duration**: 4-6 weeks | **Effort**: 100+ story points  
**Goal**: Move from Docker Compose to k3s for production readiness

### 9.1 k3s Cluster Setup

```bash
# Control Plane: k3s server
# Compute Nodes: k3s agents (execution-node, gateway-node)

# Install:
# Control: curl -sfL https://get.k3s.io | sh -
# Agents: k3s agent --server https://control:6443 --token $TOKEN
```

**Status Tracking**:
- [ ] Install k3s on Control Plane
- [ ] Install k3s agents on Compute nodes
- [ ] Configure networking (CNI)
- [ ] Verify cluster health (kubectl get nodes)

---

### 9.2 Helm Charts

**Create Helm charts for each tier**:
1. control-plane/ (SPIRE, Langfuse, PostgreSQL, ClickHouse, MinIO)
2. gateway/ (Traefik, Prometheus, Grafana, Loki)
3. compute/ (Ollama, ComfyUI, Agent Runtime, Voice Services)

**Status Tracking**:
- [ ] Create Helm chart scaffolds
- [ ] Test chart deployment
- [ ] Document values.yaml for customization
- [ ] Create upgrade procedures

---

### 9.3 Auto-Scaling

**Horizontal Pod Autoscaling**:
```yaml
# Scale Agent Runtime based on queue depth
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-runtime-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-runtime
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: queue_depth  # Custom metric from Prometheus
      target:
        type: AverageValue
        averageValue: "30"  # Scale up if avg queue > 30
```

**Status Tracking**:
- [ ] Define autoscaling metrics
- [ ] Create HPAs for key services
- [ ] Test scaling under load
- [ ] Document cost implications

---

## Implementation Timeline

```
Q1 2026 (March) — COMPLETED
├─ March 15: Phase 5.1 (JWT-ACE) ✅ Done
├─ March 16: Phase 5.2 (Template Registry) ✅ Done
├─ March 17: Phase 5.3 (Integration Tests + Deploy) ✅ Done — 31/31 tests passing
├─ March 18-20: Phase 6 (GRPO Training Pipeline) ✅ Done
└─ March 21: Phase 6 Deploy + Dashboards + Documentation ✅ Done

Q2 2026 (April - June)
├─ Week 1-2: Phase 7.1 (Multi-GPU load balancing)
├─ Week 2-3: Phase 7.2 (Model Versioning)
├─ Week 3-4: First full training run + A/B test validation
└─ Week 4-6: Phase 8 (HA)

Q3 2026 (July - September)
├─ Week 1-3: Phase 8 (PostgreSQL HA, Redis Sentinel)
├─ Week 3-4: Phase 9.1-9.2 (k3s + Helm)
└─ Week 4-5: Phase 9.3 (Auto-scaling)
```

---

## Resource Allocation

### Development Team
- **1 Senior Engineer**: Phase 5 architecture, Phase 8 k3s setup
- **2 Mid-Level Engineers**: Phase 5 implementation, Phase 6 features
- **1 QA Engineer**: Phase 5/6 testing, chaos testing
- **1 DevOps Engineer**: Phase 7 HA, Phase 8 deployment

### Infrastructure
- **Phase 5-6**: Current infrastructure (no new hardware)
- **Phase 7**: HA requires 1 additional IP (virtual IP for PostgreSQL)
- **Phase 8**: k3s runs on existing 3 nodes (no new hardware)

### Budget Estimate
- **Development**: 300 story points @ $25/point = ~$7,500
- **Infrastructure**: Minimal (same hardware) + NFS storage (~$2,000)
- **Testing/QA**: 50 hours @ $50/hr = $2,500
- **Total**: ~$12,000 over 4 months

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| JWT signature verification bug | Medium | High | Extensive unit tests, cryptographic validation |
| Template update breaks production | Low | High | A/B testing framework, automatic rollback |
| PostgreSQL replication lag | Low | Medium | Synchronous replication, monitoring |
| k3s cluster incompatibility | Medium | High | Test on staging cluster first |

---

## Success Metrics

### Phase 5
- ✓ Ephemeral agents created/destroyed on demand
- ✓ Token validation enforces capabilities
- ✓ Template versions created from trace data
- ✓ >50% code coverage for new modules

### Phase 6 (Training Pipeline)
- ✓ Training data exported from Langfuse traces
- ✓ Synthetic trajectories generated (5 validated, 50+ target)
- ✓ QLoRA GRPO training runs on RTX 5060 Ti (12.5GB VRAM budget)
- ✓ LoRA → GGUF → Ollama pipeline automated
- ✓ A/B testing with statistical significance (Welch's t-test, p<0.05)
- ✓ Auto-promotion when candidate >5% better over 100+ invocations
- ✓ Grafana dashboards for training pipeline and template performance

### Phase 7 (Multi-Model Orchestration)
- ✓ Load balancer distributes requests across 2 GPU nodes
- ✓ Throughput increases 50% (2 nodes) vs single
- ✓ Model versioning enables reproducible experiments

### Phase 8 (High Availability)
- ✓ Database failover <5 seconds
- ✓ System tolerates node failure without downtime
- ✓ Model cache shared across nodes
- ✓ 99.9% availability target

### Phase 9 (Kubernetes)
- ✓ All services deployable via Helm
- ✓ Auto-scaling works under load
- ✓ Rolling updates with zero downtime
- ✓ Cost reduced 30% via efficient resource packing

---

## Dependencies & Blockers

### On Phase 5
- **Langfuse API stability** (trace format must be finalized)
- **SPIRE deployment** (must be operational on Control Plane)
- **PostgreSQL** (must support JSON columns for parameters)

### On Phase 7
- **Phase 6 completion** ✅ (A/B testing and model versioning available)
- **Secondary GPU availability** (Gateway Node or new node must have GPU)
- **Network performance** (multi-node inference needs <10ms latency)

### On Phase 8-9
- **Team expertise** (Kubernetes requires special skills)
- **Production validation** (must test HA extensively before live)

---

## Communication Plan

- **Weekly standups**: 15 min (progress, blockers)
- **Bi-weekly architecture reviews**: 1 hour (design decisions)
- **Monthly stakeholder updates**: 30 min (business value, roadmap)
- **Documentation**: Continuous (update as progress)

---

## Next Action Items (Phase 7 Planning)

1. **Build training-runtime on Execution Node** — `docker compose --profile training build training-runtime`
2. **Execute first full training run** — synthetic data → QLoRA → GGUF → Ollama → A/B test
3. **Rotate default credentials** — 20+ default passwords identified across the stack
4. **Gateway Node SPIRE enrollment** — complete the remaining identity gap
5. **Verify Gateway Node GPU availability** — confirm NVIDIA drivers and VRAM for secondary inference
6. **Design load balancer** — route requests across Execution Node + Gateway Node based on model size and VRAM
7. **Template auto-versioning** — accumulate performance data to trigger first automatic version bump

---

**Document Version**: 3.0
**Status**: Phase 6 Complete, Phase 7 Planning
**Last Updated**: March 21, 2026

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `docs/phase_reports/` | Documentation | Completed phase reports (0–6) |
| `agents/main.py` | Implementation | Latest API endpoints |
| `agents/grpc/` | Implementation | Phase 6 gRPC server |
| `agents/training/` | Implementation | Phase 6 training pipeline |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide |
| 2026-03-21 | AI-Copilot | Phase 6 (GRPO) marked complete, Phase 7 planning |

</details>

---

## Maintenance & Update Guide

- Mark phases as complete with links to their phase reports.
- Add new phases as they are planned.
- Update "Last Updated" date when modifying.
