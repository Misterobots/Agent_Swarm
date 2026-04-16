# Template-Level Expertise Evolution: Multi-Level RL Architecture

**Date**: March 14, 2026  
**Status**: Architecture Enhancement — Building on JWT-ACE  
**User Insight**: Expertise agents can be ephemeral while expertise itself evolves across instances

---

## Executive Summary

**The Problem with Instance-Level Only Learning**:
```
Ephemeral Agent #1 → MarsRL Loop → Reward: 0.82 → Discarded (learning lost)
Ephemeral Agent #2 → MarsRL Loop → Reward: 0.75 → Discarded (no transfer learning)
Ephemeral Agent #3 → MarsRL Loop → Reward: 0.80 → Discarded
```

**The Solution: Template-Level Expertise**:
```
ExpertiseTemplate("Code Developer") v1.0
    ↓ (Initialize)
Ephemeral Agent #1 → MarsRL Loop → Reward: 0.82
    ↓ (Update template)
ExpertiseTemplate("Code Developer") v1.1 (improved)
    ↓ (Initialize with v1.1 state)
Ephemeral Agent #2 → MarsRL Loop → Reward: 0.85 (benefits from learning!)
    ↓ (Update template)
ExpertiseTemplate("Code Developer") v1.2 (further improved)
    ↓
Ephemeral Agent #3 → MarsRL Loop → Reward: 0.88 (compounds learning)
```

**Key Insight**: The **expertise persists and evolves**; the **agents are disposable**.

---

## Part 1: What is Expertise?

Expertise is not monolithic. It's a collection of learnable components that improve with experience:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ExpertiseTemplate:
    """Learnable expertise that persists across ephemeral instances"""
    
    # === Identity ===
    id: str = "expertise-code-developer"
    name: str = "Code Developer"
    role: str = "Full Stack & System Engineer"
    version: int = 1
    created_date: datetime = field(default_factory=datetime.utcnow)
    
    # === Learnable Components (Updated via RL) ===
    
    # 1. System Prompt (narrative instructions, learned principles)
    system_prompt: str = """You are a Code Developer v1.0. Your role is to:
    - Write clean, modular Python code
    - Prefer composition over inheritance
    - Add comprehensive error handling
    - Write docstrings for all functions
    """
    
    # 2. Model Reference (base model or fine-tuned version)
    model_reference: str = "qwen3.5:9b"  # or "qwen3.5:9b-finetuned-v2" after fine-tuning
    
    # 3. Generation Parameters (learned via reward signal)
    generation_parameters: Dict[str, float] = field(default_factory=lambda: {
        "temperature": 0.7,      # Adjusted via RL
        "top_p": 0.9,            # Adjusted via RL
        "max_tokens": 4096,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0
    })
    
    # 4. Tool Selection Strategy (learned weights for which tools to prefer)
    tool_selection_strategy: Dict[str, float] = field(default_factory=lambda: {
        "file_ops.write": 0.95,   # High confidence in file writing
        "file_ops.read": 0.98,    # High confidence in file reading
        "terminal.exec": 0.75,    # Moderate confidence in terminal execution
        "git.ops": 0.50           # Low confidence in git operations
    })
    
    # 5. Failure Patterns to Avoid (learned from errors)
    antipatterns: List[str] = field(default_factory=list)
    
    # === Performance Tracking ===
    instance_count: int = 0              # How many ephemeral agents used this template
    cumulative_reward: float = 0.0       # Sum of all verifier scores
    average_performance: float = 0.0     # Mean verifier score
    min_performance: float = 1.0
    max_performance: float = 0.0
    learning_iterations: int = 0         # How many times updated
    
    # === Versioning ===
    previous_version_link: Optional[str] = None  # For rollback/traceability
    training_data_used: List[str] = field(default_factory=list)  # Trace IDs
    is_active: bool = True               # Multiple versions may exist, only one active
```

---

## Part 2: The Multi-Level Learning Flow

### Step 1: Initialize Ephemeral Agent with Template State

**Router Decision**:
```python
# User submits CODE task
intent = semantic_router.route(user_input)  # → "CODE"

# Load the LATEST version of Code Developer template
template = expertise_registry.get_template(
    expertise_id="expertise-code-developer",
    version="latest"
)
# Returns: ExpertiseTemplate(..., version=1.3, average_performance=0.84)

# Create ephemeral card with template state
ephemeral_card = EphemeralAgentCard(
    instance_id=f"code-dev-{uuid.uuid4().hex[:8]}",
    name="Code Developer",
    expertise_template_id=template.id,
    expertise_template_version=template.version,
    
    # Bootstrap: inherit optimized state from template
    system_prompt=template.system_prompt,           # "You are Code Developer v1.3..."
    generation_parameters=template.generation_parameters,  # {"temperature": 0.68, ...}
    tool_selection_strategy=template.tool_selection_strategy,  # Learned weights
    
    session_id=session_id,
    created_by="spiffe://home-ai-lab/agent/router"
)

# Issue JWT with template snapshot
token = issuer.issue_token(
    ephemeral_card=ephemeral_card,
    template_version=template.version
)

# Spawn agent with optimized state
agent = ArchitectAgent(token=token)
```

### Step 2: Instance Learns via MarsRL Loop

```python
# Ephemeral agent runs with template-optimized parameters
mars_loop = MarsRLLoop(
    solver=agent,
    verifier=get_verifier(),
    corrector=get_corrector(),
    agent_token=token,
    expertise_template_id=template.id
)

result = mars_loop.run(
    task=user_input,
    stream_callback=lambda e: print(f"[{ephemeral_card.instance_id}] {e}")
)
```

**Langfuse Trace Includes**:
```json
{
  "trace_id": "langfuse-abc123",
  "name": "mars_loop",
  "input": "Write a function to parse JSON",
  "metadata": {
    "agent_id": "code-dev-xyz789",
    "expertise_template_id": "expertise-code-developer",
    "expertise_version": 1.3,  // Track which template version was used
    "session_id": "user-session-456"
  },
  "steps": [
    {
      "name": "solver",
      "output": "def parse_json(s: str):\n    return json.loads(s)",
      "metadata": {"iteration": 1}
    },
    {
      "name": "verifier",
      "output": "PASS",
      "metadata": {
        "ast_valid": true,
        "coherent": true,
        "safe": true,
        "score": 0.88  // ← This is the reward signal
      }
    }
  ],
  "output": "def parse_json(s: str):\n    return json.loads(s)",
  "final_reward": 0.88  // ← Aggregate score
}
```

### Step 3: Async Job Updates Template with Learning

**Background Task**:
```python
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@background_task
async def update_expertise_template_from_trace(trace_id: str):
    """
    Called after each MarsRL loop completes.
    Updates the ExpertiseTemplate with learnings from this instance.
    """
    
    # 1. Fetch the trace
    trace = langfuse.fetch_trace(trace_id)
    
    if not trace.metadata.get("expertise_template_id"):
        return  # Not an expertise trace
    
    # 2. Extract learning signals
    expertise_id = trace.metadata["expertise_template_id"]
    template_version = trace.metadata["expertise_version"]
    final_reward = trace.metadata.get("final_reward", 0.0)
    agent_id = trace.metadata["agent_id"]
    
    logger.info(
        f"Updating template {expertise_id} based on agent {agent_id} (reward: {final_reward:.3f})"
    )
    
    # 3. Load current template
    registry = ExpertiseTemplateRegistry(db)
    current_template = registry.get_template(expertise_id, version="latest")
    
    # 4. Compute new metrics
    new_instance_count = current_template.instance_count + 1
    new_cumulative_reward = current_template.cumulative_reward + final_reward
    new_average_performance = new_cumulative_reward / new_instance_count
    
    # 5. Adaptive Parameter Updates (RL policy)
    
    # If this instance performed well, reinforce its behavior
    if final_reward > 0.85:
        # High reward → reduce randomness (lower temperature)
        current_template.generation_parameters["temperature"] *= 0.98
        current_template.generation_parameters["top_p"] = min(
            current_template.generation_parameters["top_p"],
            0.92
        )
        logger.info(f"  → Reducing exploration (reward > 0.85)")
    
    # If this instance performed poorly, increase exploration
    elif final_reward < 0.65:
        # Low reward → increase randomness (higher temperature)
        current_template.generation_parameters["temperature"] *= 1.02
        logger.info(f"  → Increasing exploration (reward < 0.65)")
    
    # 6. Tool Strategy Refinement
    # Analyze trace to see which tools were used and how much they helped
    
    for step in trace.steps:
        if step.name == "solver":
            # Analyze which tools were called
            tool_calls = parse_tool_calls_from_step(step)
            
            for tool_called in tool_calls:
                # If this tool was used and the output was high-reward, reinforce it
                if final_reward > current_template.average_performance:
                    current_template.tool_selection_strategy[tool_called] *= 1.01
                # If this tool was used and the output was low-reward, deprioritize it
                elif final_reward < current_template.average_performance - 0.1:
                    current_template.tool_selection_strategy[tool_called] *= 0.99
    
    # 7. Capture Antipatterns (what NOT to do)
    if final_reward < 0.6 and trace.steps[-1].name == "verifier":
        verifier_feedback = trace.steps[-1].metadata.get("reason", "Unknown failure")
        if verifier_feedback not in current_template.antipatterns:
            current_template.antipatterns.append(verifier_feedback)
            logger.info(f"  → Added antipattern: {verifier_feedback}")
    
    # 8. Create new template version
    new_template = registry.create_version(
        previous=current_template,
        updates={
            "instance_count": new_instance_count,
            "cumulative_reward": new_cumulative_reward,
            "average_performance": new_average_performance,
            "generation_parameters": current_template.generation_parameters,
            "tool_selection_strategy": current_template.tool_selection_strategy,
            "antipatterns": current_template.antipatterns,
            "learning_iterations": current_template.learning_iterations + 1
        },
        training_trace_ids=[trace_id]
    )
    
    # 9. Log the update
    logger.info(
        f"Created {expertise_id} v{new_template.version} "
        f"(avg_performance: {new_template.average_performance:.3f}, "
        f"instances: {new_template.instance_count})"
    )
    
    # 10. Optional: Trigger rollback if performance degraded
    if new_average_performance < current_template.average_performance * 0.95:
        logger.warning(
            f"{expertise_id} v{new_template.version} shows degradation. "
            f"Reverting to previous version."
        )
        registry.rollback_to_version(expertise_id, current_template.version)
```

### Step 4: Next Instance Inherits Improved Template

```
Moment 1:
  ExpertiseTemplate("Code Developer") v1.3
  ├─ average_performance: 0.831
  ├─ instance_count: 87
  ├─ temperature: 0.668
  └─ tool_selection_strategy: {file_ops.write: 0.96, ...}

Ephem Instance #88 created with v1.3
    ↓ MarsRL → reward: 0.87
    ↓ async update job runs

Moment 2 (10 seconds later):
  ExpertiseTemplate("Code Developer") v1.4 (NEW)
  ├─ average_performance: 0.833 (improved!)
  ├─ instance_count: 88
  ├─ temperature: 0.648 (learned to reduce randomness)
  └─ tool_selection_strategy: {file_ops.write: 0.965, ...} (refined)

Ephem Instance #89 created with v1.4 (benefits immediately)
    ↓ MarsRL → reward: 0.89 (higher score due to template improvement!)
```

---

## Part 3: Storage & Registry

**File: `agents/expertise/template_registry.py`** (NEW)

```python
from typing import Dict, List, Optional
from datetime import datetime
import logging
from dataclasses import asdict

logger = logging.getLogger(__name__)

class ExpertiseTemplateRegistry:
    """
    Persistent registry of evolving expertise templates.
    
    Stores in PostgreSQL with full version history and lineage tracking.
    """
    
    def __init__(self, db_engine):
        """
        Initialize registry with database connection.
        
        Args:
            db_engine: SQLAlchemy engine or connection pool
        """
        self.db = db_engine
        self._init_schema()
    
    def _init_schema(self):
        """Create tables if they don't exist"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS expertise_templates (
                id VARCHAR(255),
                name VARCHAR(255),
                role VARCHAR(255),
                version INT,
                created_date TIMESTAMP,
                
                system_prompt TEXT,
                model_reference VARCHAR(255),
                generation_parameters JSONB,
                tool_selection_strategy JSONB,
                antipatterns TEXT[],
                
                instance_count INT DEFAULT 0,
                cumulative_reward FLOAT DEFAULT 0.0,
                average_performance FLOAT DEFAULT 0.0,
                min_performance FLOAT DEFAULT 1.0,
                max_performance FLOAT DEFAULT 0.0,
                learning_iterations INT DEFAULT 0,
                
                previous_version_link VARCHAR(255),
                training_data_used TEXT[],
                is_active BOOLEAN DEFAULT FALSE,
                
                PRIMARY KEY (id, version)
            );
            
            CREATE INDEX IF NOT EXISTS idx_expertise_active 
            ON expertise_templates(id, is_active);
        """)
    
    def get_template(self, expertise_id: str, version: str = "latest") -> Optional[ExpertiseTemplate]:
        """
        Fetch expertise template by ID and version.
        
        Args:
            expertise_id: Template identifier (e.g., "expertise-code-developer")
            version: "latest" | "active" | specific version number (int)
        
        Returns:
            ExpertiseTemplate object or None if not found
        """
        if version == "latest":
            result = self.db.execute("""
                SELECT * FROM expertise_templates 
                WHERE id = %s 
                ORDER BY version DESC LIMIT 1
            """, (expertise_id,)).fetchone()
        
        elif version == "active":
            result = self.db.execute("""
                SELECT * FROM expertise_templates 
                WHERE id = %s AND is_active = TRUE
            """, (expertise_id,)).fetchone()
        
        else:
            result = self.db.execute("""
                SELECT * FROM expertise_templates 
                WHERE id = %s AND version = %s
            """, (expertise_id, int(version))).fetchone()
        
        if not result:
            return None
        
        return ExpertiseTemplate(**dict(result))
    
    def create_version(self,
                      expertise_id: str,
                      previous: ExpertiseTemplate,
                      updates: Dict) -> ExpertiseTemplate:
        """
        Create new template version with updates.
        
        Args:
            expertise_id: Template identifier
            previous: Previous ExpertiseTemplate version
            updates: Dict of fields to update
        
        Returns:
            New ExpertiseTemplate with incremented version
        """
        new_version_num = previous.version + 1
        
        new_template = ExpertiseTemplate(
            id=expertise_id,
            name=previous.name,
            role=previous.role,
            version=new_version_num,
            created_date=datetime.utcnow(),
            
            system_prompt=updates.get("system_prompt", previous.system_prompt),
            model_reference=updates.get("model_reference", previous.model_reference),
            generation_parameters=updates.get("generation_parameters", previous.generation_parameters),
            tool_selection_strategy=updates.get("tool_selection_strategy", previous.tool_selection_strategy),
            antipatterns=updates.get("antipatterns", previous.antipatterns),
            
            instance_count=updates.get("instance_count", previous.instance_count),
            cumulative_reward=updates.get("cumulative_reward", previous.cumulative_reward),
            average_performance=updates.get("average_performance", previous.average_performance),
            learning_iterations=updates.get("learning_iterations", previous.learning_iterations),
            
            previous_version_link=f"{expertise_id}:v{previous.version}",
            training_data_used=updates.get("training_data_used", []),
            is_active=True
        )
        
        # Persist
        self.db.execute("""
            INSERT INTO expertise_templates 
            (id, name, role, version, created_date, system_prompt, model_reference, 
             generation_parameters, tool_selection_strategy, antipatterns,
             instance_count, cumulative_reward, average_performance, learning_iterations,
             previous_version_link, training_data_used, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            new_template.id, new_template.name, new_template.role, new_template.version,
            new_template.created_date, new_template.system_prompt, new_template.model_reference,
            new_template.generation_parameters, new_template.tool_selection_strategy,
            new_template.antipatterns, new_template.instance_count,
            new_template.cumulative_reward, new_template.average_performance,
            new_template.learning_iterations, new_template.previous_version_link,
            new_template.training_data_used, new_template.is_active
        ))
        
        # Deactivate previous version
        self.db.execute("""
            UPDATE expertise_templates SET is_active = FALSE
            WHERE id = %s AND version = %s
        """, (expertise_id, previous.version))
        
        logger.info(f"Created {expertise_id} v{new_version_num}")
        return new_template
    
    def rollback_to_version(self, expertise_id: str, target_version: int):
        """
        Rollback to previous template version.
        
        Useful if new version shows performance degradation.
        
        Args:
            expertise_id: Template identifier
            target_version: Version number to rollback to
        """
        # Deactivate all
        self.db.execute("""
            UPDATE expertise_templates SET is_active = FALSE
            WHERE id = %s
        """, (expertise_id,))
        
        # Activate target version
        self.db.execute("""
            UPDATE expertise_templates SET is_active = TRUE
            WHERE id = %s AND version = %s
        """, (expertise_id, target_version))
        
        logger.warning(f"Rolled back {expertise_id} to v{target_version}")
    
    def get_performance_trend(self, expertise_id: str, limit: int = 10) -> List[Dict]:
        """
        Get performance across template versions (for dashboards).
        
        Returns:
            List of {version, average_performance, instance_count, learning_iterations}
        """
        results = self.db.execute("""
            SELECT version, average_performance, instance_count, learning_iterations
            FROM expertise_templates 
            WHERE id = %s 
            ORDER BY version DESC 
            LIMIT %s
        """, (expertise_id, limit)).fetchall()
        
        return [dict(r) for r in results]
```

---

## Part 4: Integration with JWT-ACE

The JWT token now embeds the expertise template snapshot:

```python
# In agents/security/token_issuer.py

class TokenIssuer:
    def issue_token(self,
                   ephemeral_card: EphemeralAgentCard,
                   expertise_template: ExpertiseTemplate = None,
                   parent_trace_id: str = None,
                   ttl_seconds: int = 600) -> str:
        """
        Issue JWT for ephemeral agent with expertise template state.
        """
        
        now = datetime.utcnow()
        claims = {
            # Standard SPIFFE claims
            "iss": "spiffe://home-ai-lab",
            "sub": f"spiffe://home-ai-lab/agent/ephemeral/{ephemeral_card.instance_id}",
            "aud": ["spiffe://home-ai-lab/api/dispatch"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
            
            # Agent Card claims
            "agent_id": ephemeral_card.instance_id,
            "agent_name": ephemeral_card.name,
            "capabilities": ephemeral_card.activated_capabilities,
            
            # NEW: Expertise Template snapshot
            "expertise_template_id": expertise_template.id,
            "expertise_version": expertise_template.version,
            
            # Learnable state (what the agent should optimize toward)
            "system_prompt": expertise_template.system_prompt,
            "generation_parameters": expertise_template.generation_parameters,
            "tool_selection_strategy": expertise_template.tool_selection_strategy,
            "antipatterns": expertise_template.antipatterns,
            
            # Context
            "parent_trace_id": parent_trace_id,
            "session_id": ephemeral_card.session_id,
            "created_by": ephemeral_card.created_by
        }
        
        token = jwt.encode(
            claims,
            self.spiffe_auth.get_private_key(),
            algorithm="RS256"
        )
        
        return token
```

---

## Part 5: The Self-Improving Loop

**Monthly Batch Fine-Tuning Pipeline**:

```python
# in agents/expertise/training_pipeline.py (NEW)

async def monthly_finetune_expertise(expertise_id: str):
    """
    Monthly background job to fine-tune models based on high-reward traces.
    """
    
    # 1. Collect high-reward traces from last month
    traces = langfuse.fetch_traces(
        metadata_match={"expertise_template_id": expertise_id},
        time_window=("2026-02-14", "2026-03-14")
    )
    
    high_quality = [t for t in traces if t.metadata.final_reward > 0.85]
    if len(high_quality) < 10:
        logger.info(f"Not enough high-quality traces for {expertise_id}, skipping fine-tune")
        return
    
    # 2. Build training dataset
    dataset = []
    for trace in high_quality:
        solver_step = trace.steps[0]
        verifier_step = trace.steps[1]
        
        dataset.append({
            "input": trace.input,
            "output": solver_step.output,
            "reward": verifier_step.metadata.score,
            "iterations_needed": len(trace.steps) - 2  # How many corrections?
        })
    
    # 3. Submit fine-tuning job
    template = expertise_registry.get_template(expertise_id, version="latest")
    
    finetune_job = submit_vllm_finetune_job(
        model=template.model_reference,  # "qwen3.5:9b"
        dataset=dataset,
        config={
            "learning_rate": 1e-4,
            "num_epochs": 3
        }
    )
    
    logger.info(f"Submitted fine-tune job for {expertise_id}: {finetune_job.id}")
    
    # 4. Wait for completion and update template
    while True:
        status = finetune_job.get_status()
        if status == "COMPLETED":
            break
        await asyncio.sleep(300)  # Check every 5 min
    
    # 5. Create new template version with fine-tuned model
    new_template = expertise_registry.create_version(
        expertise_id=expertise_id,
        previous=template,
        updates={
            "model_reference": finetune_job.model_output_path,  # "qwen3.5:9b-finetuned-v2"
            "training_data_used": [t.id for t in high_quality],
        }
    )
    
    logger.info(f"Fine-tuning complete. {expertise_id} now uses {new_template.model_reference}")
```

---

## Part 6: Dashboards & Observability

**Metrics to Track** (in Grafana):

```
For each ExpertiseTemplate:
  1. Performance Trend:
     - Graph: average_performance over time (template versions)
     - Alert: if new version drops > 5% below previous
  
  2. Learning Progress:
     - Stacked area: instance_count per template version
     - Shows adoption rate of new versions
  
  3. Parameter Evolution:
     - Heatmap: generation_parameters[temperature] across versions
     - Shows how temperature was adjusted via RL
  
  4. Tool Usage:
     - Bar chart: tool_selection_strategy values
     - Which tools are being preferred/deprioritized?
```

---

## Summary: Multi-Level RL Architecture

| Level | What Learns | Mechanism | Outcome |
|-------|------------|-----------|---------|
| **Instance** | Solves specific task | MarsRL Loop (Solver→Verifier→Corrector) | One-off solution |
| **Expertise Template** | General capability | Aggregate rewards across instances | Improved prompts, parameters, strategies |
| **Model (Optional)** | Underlying patterns | Monthly fine-tuning on high-reward traces | Better base model for future instances |

**Benefits**:
- ✅ Continuous learning without retraining
- ✅ Each new ephemeral agent inherits optimized state
- ✅ Full audit trail of what training each version
- ✅ Safe rollback if performance degrades
- ✅ Compounding improvements (v1.0 → v1.1 → v1.2 → ...)

**Implementation Roadmap**:
1. **Phase 0**: Create ExpertiseTemplate model + ExpertiseTemplateRegistry
2. **Phase 1**: Integrate template initialization with JWT-ACE tokens
3. **Phase 2**: Async job to update templates after MarsRL completion
4. **Phase 3**: Monthly fine-tuning pipeline
5. **Phase 4**: Grafana dashboards for template evolution

---

**Next Step**: Implement Phase 0–2 now, then quarterly fine-tuning in Phase 3.

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `agents/expertise/template_registry.py` | Implementation | ExpertiseTemplateRegistry, DB operations |
| `agents/security/token_issuer.py` | Implementation | JWT-ACE token with expertise embedding |
| `agents/mars_loop.py` | Implementation | MarsRL scoring for template evolution |
| `config/grafana/dashboards/` | Infrastructure | Expertise evolution dashboards |

</details>

<details>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-15 | AI-Copilot | Multi-level RL architecture for expertise template evolution |

</details>

---

## Maintenance & Update Guide

- Update when new expertise domains are added to the template registry.
- Update when the RL reward structure changes.
- Update architectural diagrams when new template versioning strategies are introduced.

---

## Functionality Testing

| Claim | How to Verify |
|-------|---------------|
| Templates seeded | Query PostgreSQL → `SELECT count(*) FROM expertise_templates` → 7+ |
| Template versioning | Create template v1, evolve it → verify v2 created with lineage |
