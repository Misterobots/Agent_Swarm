from phi.agent import Agent
from phi.model.ollama import Ollama
import os

from tools.file_ops import read_file, write_file, list_dir
from tools.terminal import run_command

from phi.knowledge.combined import CombinedKnowledgeBase
from phi.vectordb.pgvector import PgVector

from prompts.architect_prompts import ARCHITECT_INSTRUCTIONS

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = "qwen2.5-coder:14b"
DB_URL = os.getenv("AGNO_DB_URL")

def get_architect_agent():
    """
    Returns an instance of the Architect Agent.
    This agent is responsible for high-level planning and code generation.
    It now has ACCESS to the filesystem, sandbox terminal, and LONG-TERM MEMORY.
    """
    if not DB_URL or "dell_wyse_ip" in DB_URL:
        # print("!!! WARNING: AGNO_DB_URL is not set or contains placeholder. Memory disabled. !!!")
        knowledge_base = None
    else:
        knowledge_base = CombinedKnowledgeBase(
            sources=[], 
            vector_db=PgVector(
                table_name="architect_knowledge",
                db_url=DB_URL,
            ),
        )

    return Agent(
        name="Architect",
        model=Ollama(
            id=MODEL_NAME,
            host=OLLAMA_HOST,
            options={"temperature": 0.1}
        ),
        description="I am the Architect. I plan, write, and execute code using tools.",
        instructions=ARCHITECT_INSTRUCTIONS,
        tools=[read_file, write_file, list_dir, run_command],
        knowledge=knowledge_base,
        show_tool_calls=True,
        markdown=False, # Disable markdown to fix log capturing
        debug_mode=True # Enable full debug logs to see raw IO
    )

def assess_compatibility(req_type: str, details: str) -> str:
    """
    Assesses Technical Compatibility of a request.
    Checks for Hardware Constraints (GPU/RAM) and Environment Conflicts.
    """
    import subprocess
    
    # 1. Hardware Check (Mocked/Heuristic)
    # In a real scenario, we'd enable nvidia-smi parsing.
    # For now, we assume a standard consumer GPU (e.g. RTX 3060 12GB)
    SYSTEM_VRAM_GB = 12 
    
    if req_type == "MODEL":
        # Heuristic: FLUX and SD3 are heavy
        if "flux" in details.lower() or "sd3" in details.lower():
            if "quant" not in details.lower() and "schnell" not in details.lower():
                    return "WARNING: Model may exceed VRAM (Requires >16GB for full precision). Recommend Quantized version."
        if "70b" in details.lower():
            return "WARNING: 70B parameter models require >40GB VRAM. This is likely to OOM."
            
    if req_type == "PACKAGE":
        # Heuristic: Heavy Frameworks
        if "tensorflow" in details.lower():
            return "NOTE: TensorFlow can conflict with PyTorch. Ensure virtualenv is used."
        if "cu11" in details.lower():
            return "WARNING: Requested CUDA 11, but System is CUDA 12. Potential mismatch."

    return "COMPATIBLE"

from logger_setup import setup_logger
logger = setup_logger("Architect")

# Wrapper to log conversation
def run_architect(user_input: str):
    logger.info(f"--- [Architect] Thinking about: {user_input} ---")
    agent = get_architect_agent()
    response = agent.run(user_input)
    logger.info(f"--- [Architect] Response: {response.content[:200]}... ---") # Log snippet
    logger.debug(f"--- [Architect] Full Response: {response.content} ---")
    return response

if __name__ == "__main__":
    # Test the agent locally
    agent = get_architect_agent()
    agent.print_response("Hello, Architect. Ready to build?")
