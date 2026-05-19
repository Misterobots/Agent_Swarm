from typing import Optional, List
from phi.agent import Agent
from phi.model.ollama import Ollama
import os

from tools.file_ops import read_file, write_file, list_dir
from tools.terminal import run_command
from tools.web_builder import build_web_app, get_project_template, list_project_templates

from phi.knowledge.combined import CombinedKnowledgeBase
from phi.vectordb.pgvector import PgVector

from prompts.architect_prompts import ARCHITECT_INSTRUCTIONS

# Configuration
from phi.storage.agent.postgres import PgAgentStorage
from config import AGNO_DB_URL
from utils.gpu_queue import get_best_host_for_model

DEFAULT_MODEL = os.getenv("SOLVER_MODEL", "qwen2.5-coder:14b-instruct-q4_k_m")

# Shared Storage for persistent sessions
agent_storage = PgAgentStorage(
    table_name="architect_sessions",
    db_url=AGNO_DB_URL
)

def get_architect_agent(session_id: Optional[str] = None, model_name: Optional[str] = None):
    """
    Returns an instance of the Architect Agent (MarsRL Solver role).
    Host is resolved lazily at call time via health-aware routing.
    """
    resolved_model = model_name or DEFAULT_MODEL
    resolved_host = get_best_host_for_model(resolved_model)

    if not AGNO_DB_URL or "dell_wyse_ip" in AGNO_DB_URL:
        knowledge_base = None
    else:
        knowledge_base = CombinedKnowledgeBase(
            sources=[],
            vector_db=PgVector(
                table_name="architect_knowledge",
                db_url=AGNO_DB_URL,
            ),
        )

    return Agent(
        name="Architect",
        model=Ollama(
            id=resolved_model,
            host=resolved_host,
            options={"temperature": 0.1},
            client_kwargs={"timeout": 300.0}
        ),
        storage=agent_storage,
        session_id=session_id,
        add_history_to_messages=True,
        num_history_responses=5,
        description="I am the Architect. I plan, write, and execute code using tools.",
        instructions=ARCHITECT_INSTRUCTIONS,
        tools=[read_file, write_file, list_dir, run_command,
               build_web_app, get_project_template, list_project_templates],
        knowledge=knowledge_base,
        show_tool_calls=False,
        run_tool_calls=True, # Enable NATIVE execution
        markdown=True,
        debug_mode=True
    )

def assess_compatibility(req_type: str, details: str) -> str:
    """
    Assesses Technical Compatibility of a request.
    Checks for Hardware Constraints (GPU/RAM) and Environment Conflicts.
    """
    import subprocess
    
    # Hardware Check (Mocked/Heuristic)
    SYSTEM_VRAM_GB = 12 
    
    if req_type == "MODEL":
        if "flux" in details.lower() or "sd3" in details.lower():
            if "quant" not in details.lower() and "schnell" not in details.lower():
                    return "WARNING: Model may exceed VRAM (Requires >16GB for full precision). Recommend Quantized version."
        if "70b" in details.lower():
            return "WARNING: 70B parameter models require >40GB VRAM. This is likely to OOM."
            
    if req_type == "PACKAGE":
        if "tensorflow" in details.lower():
            return "NOTE: TensorFlow can conflict with PyTorch. Ensure virtualenv is used."
        if "cu11" in details.lower():
            return "WARNING: Requested CUDA 11, but System is CUDA 12. Potential mismatch."

    return "COMPATIBLE"

from logger_setup import setup_logger
logger = setup_logger("Architect")

def run_architect(user_input: str):
    logger.info(f"--- [Architect] Thinking about: {user_input} ---")
    agent = get_architect_agent()
    response = agent.run(user_input)
    logger.info(f"--- [Architect] Response: {response.content[:200]}... ---") # Log snippet
    logger.debug(f"--- [Architect] Full Response: {response.content} ---")
    return response

if __name__ == "__main__":
    agent = get_architect_agent()
    agent.print_response("Hello, Architect. Ready to build?")
