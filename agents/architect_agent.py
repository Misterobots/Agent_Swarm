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
