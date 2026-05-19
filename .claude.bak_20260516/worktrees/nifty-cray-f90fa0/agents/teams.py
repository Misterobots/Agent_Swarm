import os
from phi.agent import Agent
from phi.model.ollama import Ollama
from config import get_ollama_options

# Import Specialized Agents
from leibniz_agent import get_architect_agent
from specialized.iot_agent import get_iot_agent
from specialized.bmo_agent import get_bmo_agent

# Import MarsRL agents
from verifier_agent import get_verifier
from dijkstra_agent import get_corrector

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")          # Lovelace (Solver/Corrector)
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", OLLAMA_HOST)  # Dell Turing (Router/Orchestrator)
ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "nemotron-orchestrator:8b")

# --- 1. CODING TEAM ---
def get_coding_team():
    """
    Returns the Coding Team:
    - Architect (Lead): Plans & Writes Code.
    - Security (Guardian): Checks patterns (Mock/Llama-Guard).
    """
    architect = get_architect_agent()
    
    team = Agent(
        name="Coding Team",
        model=Ollama(id="qwen2.5-coder:14b", host=OLLAMA_HOST, options=get_ollama_options("qwen2.5-coder:14b")),
        team=[architect],
        description="A team of autonomous coding agents led by the Architect.",
        instructions=["Your goal is to write, debug, and execute code.", "Always delegate to the Architect for implementation."],
        show_tool_calls=True,
        markdown=True
    )
    return team

# --- 2. CREATIVE TEAM ---
def get_creative_team(session_id: str = None):
    """
    Returns the Creative Team with:
    - Persistent memory (Agno PostgreSQL)
    - Langfuse tracing
    - Preference confirmation (HITL)
    """
    from specialized.image_gen import generate_image
    from preferences import get_confirmation_instructions
    
    try:
        from langfuse import observe
        USE_LANGFUSE = True
    except ImportError:
        USE_LANGFUSE = False
        observe = lambda *args, **kwargs: lambda f: f  # No-op decorator
    
    storage = None
    try:
        from phi.storage.agent.postgres import PgAgentStorage
        AGNO_DB_URL = os.getenv("AGNO_DB_URL")
        if AGNO_DB_URL:
            storage = PgAgentStorage(
                table_name="creative_team_sessions",
                db_url=AGNO_DB_URL
            )
    except Exception as e:
        print(f"[Creative Team] Storage not available: {e}")
    
    confirmation_protocol = get_confirmation_instructions()
    
    art_director = Agent(
        name="Art Director",
        model=Ollama(id="qwen2.5-coder:14b", host=OLLAMA_HOST, options=get_ollama_options("qwen2.5-coder:14b")),
        storage=storage,
        session_id=session_id,
        add_history_to_messages=True,  # Include conversation history
        num_history_responses=10,       # Last 10 exchanges
        description="Creative Lead for visual assets with memory.",
        instructions=[
            "You are the Art Director with memory of user preferences.",
            "Refine user prompts to be vivid and detailed.",
            "Use 'generate_image' to create visual assets.",
            "",
            confirmation_protocol,
        ],
        tools=[generate_image], 
        show_tool_calls=True
    )
    
    # BMO Voice Agent
    bmo_agent = get_bmo_agent()
    
    team = Agent(
        name="Creative Team",
        team=[art_director, bmo_agent],
        storage=storage,
        session_id=session_id,
        description="A studio team for generating Images and 3D Models.",
        instructions=["Delegate visual tasks to the Art Director."],
        markdown=True
    )
    return team

# --- 3. IoT TEAM ---
def get_iot_team():
    """
    Returns the Home Automation Team.
    """
    iot_controller = get_iot_agent()
    
    team = Agent(
        name="IoT Team",
        team=[iot_controller],
        description="A team for controlling Home Assistant devices.",
        instructions=["Delegate Home Assistant tasks to the IoT Controller."],
        markdown=True
    )
    return team

# --- 4. THE ORCHESTRATOR ---
def get_orchestrator():
    """
    The Master Agent that routes tasks to specific Teams.
    Uses Nemotron-Orchestrator-8B: purpose-built for multi-agent coordination.
    Runs on Dell Turing (RTX 3070 Ti 8GB) via SECONDARY_OLLAMA_HOST.
    """
    coding_team = get_coding_team()
    creative_team = get_creative_team()
    iot_team = get_iot_team()
    
    orchestrator = Agent(
        name="Orchestrator",
        model=Ollama(id=ORCHESTRATOR_MODEL, host=SECONDARY_OLLAMA_HOST, options=get_ollama_options(ORCHESTRATOR_MODEL)),
        team=[coding_team, creative_team, iot_team],
        description="The Head of the Swarm. You route requests to the specialized teams.",
        instructions=[
            "You are the Orchestrator.",
            "Analyze the user's request and delegate it to the appropriate Team.",
            "- Code/Scripts -> Coding Team",
            "- Images/Art/Voice -> Creative Team",
            "- Lights/Home Assistant -> IoT Team",
            "If the request is general chat, answer it yourself."
        ],
        show_tool_calls=True,
        markdown=True,
        debug_mode=True
    )
    return orchestrator


# --- 5. MARSRL AGENT ACCESSORS ---

def get_verifier_agent():
    """
    Returns the LogicVerifier for the MarsRL loop.
    3-layer verification: AST parse + coherence + llama-guard safety.
    """
    return get_verifier()


def get_corrector_agent():
    """
    Returns the CorrectorAgent for the MarsRL loop.
    Wraps the corrector model with a targeted correction system prompt.
    """
    return get_corrector()

if __name__ == "__main__":
    from phi.agent import Agent
    print("--- Testing Agno Orchestrator ---")
    
    try:
        orchestrator = get_orchestrator()
        
        # Test 1: Coding Task
        print("\n[Test 1] Routing Coding Task...")
        orchestrator.print_response("Write a python script to calculate pi.", stream=False)
        
    except Exception as e:
        print(f"Test Failed: {e}")


