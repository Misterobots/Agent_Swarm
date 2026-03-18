"""
corrector_agent.py — MarsRL Corrector Agent

The Corrector receives the original task, the Solver's failed response,
and the Verifier's failure reason, then generates a corrected output.

Model: qwen3.5:9b (same as Solver but with different system prompt)
This follows MarsRL's agent-specific optimization — same model, different role.
"""

from typing import Optional
from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
from phi.storage.agent.postgres import PgAgentStorage
from config import AGNO_DB_URL
from utils.gpu_queue import get_ollama_host
from logger_setup import setup_logger

logger = setup_logger("Corrector")

# Config
from utils.gpu_queue import get_ollama_host
CORRECTOR_MODEL = os.getenv("CORRECTOR_MODEL", "qwen3.5:9b")
OLLAMA_HOST = get_ollama_host(CORRECTOR_MODEL)

CORRECTOR_SYSTEM_PROMPT = """You are the Corrector Agent in a multi-agent software engineering system.

Your job is to receive a FAILED response from the Solver Agent and fix it.

You will be given:
1. ORIGINAL TASK: The user's original request
2. FAILED RESPONSE: The Solver's output that failed verification
3. FAILURE REASON: The specific error or problem detected

YOUR RULES:
- Address the failure reason directly and precisely
- Preserve any correct parts of the failed response
- For SyntaxError: fix ONLY the broken code, keep everything else
- For truncation: complete the response where it was cut off
- For repetition: shrink and de-duplicate the repeated section
- For coherence issues: rewrite the problematic section cleanly
- Do NOT introduce new functionality beyond what was asked
- Do NOT change working code to a different approach unless the original approach is fundamentally broken
- Output the COMPLETE corrected response, not just the diff

Your output is the final corrected response delivered to the user.
"""


# Shared Storage for persistent sessions
agent_storage = PgAgentStorage(
    table_name="corrector_sessions",
    db_url=AGNO_DB_URL
)

class CorrectorAgent:
    """
    Wraps qwen3.5:9b as the Corrector in the MarsRL loop.
    """

    def __init__(self, session_id: Optional[str] = None):
        self._agent = None
        self.session_id = session_id

    def _get_agent(self) -> Agent:
        if self._agent is None:
            logger.info(f"[Corrector] Initializing with model: {CORRECTOR_MODEL} | Session: {self.session_id}")
            self._agent = Agent(
                name="Corrector",
                model=Ollama(
                    id=CORRECTOR_MODEL,
                    host=OLLAMA_HOST,
                    options={"temperature": 0.05},  # Low temp — precise corrections
                    client_kwargs={"timeout": 300.0}
                ),
                storage=agent_storage,
                session_id=self.session_id,
                add_history_to_messages=True,
                num_history_responses=5,
                description="I am the Corrector. I fix failed Solver responses.",
                instructions=CORRECTOR_SYSTEM_PROMPT,
                show_tool_calls=False,
                markdown=True,
            )
        return self._agent

    def run(self, original_task: str, failed_response: str, failure_reason: str) -> RunResponse:
        """
        Generate a corrected response.

        Args:
            original_task:   The user's original request
            failed_response: The Solver's output that failed verification
            failure_reason:  The Verifier's failure explanation

        Returns:
            RunResponse with .content containing the corrected text
        """
        agent = self._get_agent()

        # Truncate failed_response to avoid context overflow
        max_failed_len = 3000
        truncated = failed_response[:max_failed_len]
        if len(failed_response) > max_failed_len:
            truncated += "\n... [truncated for context]"

        correction_prompt = f"""ORIGINAL TASK:
{original_task}

FAILED RESPONSE:
{truncated}

FAILURE REASON:
{failure_reason}

Please provide the corrected, complete response:"""

        logger.info(f"[Corrector] Sending correction prompt (reason: {failure_reason})")
        try:
            response: RunResponse = agent.run(correction_prompt)
            logger.info(f"[Corrector] Correction complete ({len(response.content)} chars)")
            return response
        except Exception as e:
            logger.error(f"[Corrector] Failed to correct: {e}")
            raise


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_corrector = None

def get_corrector() -> CorrectorAgent:
    """Returns a shared CorrectorAgent instance (lazy init)."""
    global _corrector
    if _corrector is None:
        _corrector = CorrectorAgent()
    return _corrector
