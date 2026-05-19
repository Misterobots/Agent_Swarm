"""
DEMONSTRATION: Agent Memory + Langfuse Integration
===================================================
This file demonstrates how agent memory (Agno PostgreSQL) and 
Langfuse observability work together in the Home AI Lab.

Key Concepts:
- Agno Storage: Persists conversation history, agent state, sessions
- Langfuse: Traces LLM calls, tracks costs, versions prompts
"""

import os
from phi.agent import Agent
from phi.model.ollama import Ollama
from phi.storage.agent.postgres import PgAgentStorage
from langfuse import Langfuse, observe
from config import AGNO_DB_URL, LANGFUSE_HOST

# ============================================================
# 1. DATABASE CONNECTIONS
# ============================================================

# Agno PostgreSQL - Agent Memory (sourced from network.env via config.py)
# AGNO_DB_URL already imported from config

# Langfuse - Observability (sourced from network.env via config.py)
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-...")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-...")
# LANGFUSE_HOST already imported from config

# Initialize Langfuse client
langfuse = Langfuse(
    secret_key=LANGFUSE_SECRET_KEY,
    public_key=LANGFUSE_PUBLIC_KEY,
    host=LANGFUSE_HOST
)

# ============================================================
# 2. AGNO AGENT STORAGE (Memory)
# ============================================================

# This is what stores your agent's memory persistently
agent_storage = PgAgentStorage(
    table_name="agent_sessions",
    db_url=AGNO_DB_URL
)

# ============================================================
# 3. AGENT WITH MEMORY + LANGFUSE TRACING
# ============================================================

@observe()  # <-- Langfuse decorator: traces this function
def create_agent_with_memory(session_id: str = None):
    """
    Creates an agent with persistent memory.
    
    MEMORY FLOW:
    ┌──────────────────────────────────────────────────────────┐
    │  User: "Generate an image of a sunset"                   │
    │                      │                                   │
    │                      ▼                                   │
    │  ┌─────────────────────────────────────────────────────┐ │
    │  │  AGNO AGENT                                         │ │
    │  │  - session_id: "user_123_session_1"                 │ │
    │  │  - Stored in PostgreSQL                             │ │
    │  │                                                     │ │
    │  │  Memory Retrieved:                                  │ │
    │  │  - Previous: "I like cyberpunk style"               │ │
    │  │  - Context: User prefers dark themes                │ │
    │  └─────────────────────────────────────────────────────┘ │
    │                      │                                   │
    │                      ▼                                   │
    │  ┌─────────────────────────────────────────────────────┐ │
    │  │  LANGFUSE TRACE                                     │ │
    │  │  - trace_id: "abc123"                               │ │
    │  │  - LLM call: prompt, completion, tokens, cost       │ │
    │  │  - Latency: 1.2s                                    │ │
    │  │  - Tool calls: generate_image()                     │ │
    │  └─────────────────────────────────────────────────────┘ │
    │                      │                                   │
    │                      ▼                                   │
    │  Output: "Generated cyberpunk sunset image"              │
    └──────────────────────────────────────────────────────────┘
    """
    agent = Agent(
        name="Creative Assistant",
        model=Ollama(id="qwen2.5-coder:14b"),
        storage=agent_storage,           # <-- AGNO: Persistent memory
        session_id=session_id,            # <-- AGNO: Resume sessions
        add_history_to_messages=True,     # <-- Includes past conversation
        num_history_responses=10,         # <-- Last 10 exchanges
        description="A creative assistant with memory",
        instructions=[
            "You remember past conversations with the user.",
            "Use context from previous sessions to personalize responses.",
        ],
        debug_mode=True
    )
    return agent


# ============================================================
# 4. TRACED CONVERSATION EXAMPLE
# ============================================================

@observe(name="chat_with_memory")  # <-- Langfuse traces this
def chat_with_memory(user_id: str, message: str):
    """
    A conversation that:
    1. Loads agent memory from PostgreSQL (Agno)
    2. Traces the LLM call to Langfuse
    3. Saves new memory back to PostgreSQL
    """
    # Create/resume session for this user
    session_id = f"user_{user_id}_session"
    
    # Add user context to Langfuse trace
    langfuse_context.update_current_trace(
        user_id=user_id,
        session_id=session_id,
        metadata={"source": "home_ai_lab"}
    )
    
    # Create agent with memory
    agent = create_agent_with_memory(session_id)
    
    # Run the conversation (Langfuse auto-traces LLM calls)
    response = traced_llm_call(agent, message)
    
    return response


@observe(name="llm_call")  # <-- Creates a span in the trace
def traced_llm_call(agent: Agent, message: str):
    """
    The actual LLM call - Langfuse captures:
    - Input prompt
    - Output completion  
    - Token usage
    - Latency
    - Model info
    """
    response = agent.run(message)
    
    # Log the generation to Langfuse
    langfuse_context.update_current_observation(
        input=message,
        output=response.content,
        model="qwen2.5-coder:14b",
        metadata={
            "session_id": agent.session_id,
            "has_memory": agent.storage is not None
        }
    )
    
    return response.content


# ============================================================
# 5. EXAMPLE USAGE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DEMO: Agent Memory + Langfuse Integration")
    print("=" * 60)
    
    # Simulate a multi-turn conversation
    user_id = "user_123"
    
    # Turn 1: User establishes preference
    print("\n[Turn 1] User: I prefer cyberpunk and neon aesthetics")
    response1 = chat_with_memory(user_id, "I prefer cyberpunk and neon aesthetics")
    print(f"Agent: {response1}")
    
    # Turn 2: Agent remembers preference (from Agno storage)
    print("\n[Turn 2] User: Generate an image of a sunset")
    response2 = chat_with_memory(user_id, "Generate an image of a sunset")
    print(f"Agent: {response2}")
    # Expected: Agent generates a CYBERPUNK sunset because it remembers the preference
    
    # Turn 3: Verify memory
    print("\n[Turn 3] User: What style do I like?")
    response3 = chat_with_memory(user_id, "What style do I like?")
    print(f"Agent: {response3}")
    # Expected: "You mentioned you prefer cyberpunk and neon aesthetics"
    
    # Flush Langfuse traces
    langfuse.flush()
    
    print("\n" + "=" * 60)
    print("CHECK RESULTS:")
    print("  - Langfuse UI: http://localhost:3001")
    print("  - PostgreSQL: SELECT * FROM agent_sessions;")
    print("=" * 60)


# ============================================================
# 6. WHAT EACH SYSTEM STORES
# ============================================================
"""
┌─────────────────────────────────────────────────────────────┐
│ AGNO POSTGRESQL (agent_sessions table)                      │
├─────────────────────────────────────────────────────────────┤
│ session_id    │ user_user_123_session                       │
│ agent_id      │ creative_assistant                          │
│ memory        │ {"preferences": "cyberpunk", ...}           │
│ messages      │ [{"role": "user", "content": "..."}, ...]   │
│ created_at    │ 2026-02-08 22:24:00                         │
│ updated_at    │ 2026-02-08 22:25:00                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LANGFUSE (traces table in ClickHouse)                       │
├─────────────────────────────────────────────────────────────┤
│ trace_id      │ abc-123-def                                 │
│ session_id    │ user_user_123_session                       │
│ user_id       │ user_123                                    │
│ input         │ "Generate an image of a sunset"             │
│ output        │ "Here's a cyberpunk-style sunset..."        │
│ model         │ qwen2.5-coder:14b                           │
│ tokens_in     │ 150                                         │
│ tokens_out    │ 89                                          │
│ latency_ms    │ 1234                                        │
│ cost_usd      │ 0.00 (local Ollama)                         │
│ timestamp     │ 2026-02-08 22:25:00                         │
└─────────────────────────────────────────────────────────────┘

SUMMARY:
- AGNO: "What does the agent remember?" (session state, preferences)
- LANGFUSE: "How did the agent perform?" (traces, costs, latency)
"""
