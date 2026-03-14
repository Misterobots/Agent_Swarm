"""
verifier_agent.py — Multi-Layer Logic Verifier

Inspired by MarsRL's Verifier role and MiniMax Forge's process reward mechanism.
Performs three verification passes:
  1. AST parse (structural correctness for code)
  2. Coherence heuristics (non-empty, non-looping, sensible length)
  3. llama-guard-3:8b safety check (existing Security Agent)

Returns a VerifierResult compatible with MarsRLLoop.
"""

import ast
import re
import os
from logger_setup import setup_logger
from mars_loop import VerifierResult

logger = setup_logger("Verifier")

# Config
from utils.gpu_queue import get_ollama_host
SECURITY_MODEL = "llama-guard-3:8b"
OLLAMA_HOST = get_ollama_host(SECURITY_MODEL)


class LogicVerifier:
    """
    Multi-layer verifier for agent outputs.

    Layer 1: Structural check (AST parse for Python code)
    Layer 2: Coherence check (length, repetition, sanity heuristics)
    Layer 3: Safety check via llama-guard-3:8b (existing Security Agent)

    Scoring (each layer contributes to final score):
      - Layer 1 fail  → score -= 0.40 (hard fail for broken code)
      - Layer 2 fail  → score -= 0.45 (soft fail for incoherent output)
      - Layer 3 fail  → score  = 0.0, passed = False (safety is a hard block)
    """

    def __init__(self, use_llama_guard: bool = True):
        self.use_llama_guard = use_llama_guard
        self._guard_agent = None

    def _get_guard_agent(self):
        """Lazy-load the Security Agent to avoid circular imports."""
        if self._guard_agent is None:
            try:
                from security_agent import get_security_agent
                self._guard_agent = get_security_agent()
                logger.info("[Verifier] llama-guard-3:8b loaded.")
            except Exception as e:
                logger.warning(f"[Verifier] Could not load Security Agent: {e}")
                self._guard_agent = None
        return self._guard_agent

    def verify(self, task: str, response: str) -> VerifierResult:
        """
        Run all verification layers on the agent's response.

        Args:
            task:     The original user task (for context)
            response: The Solver's output to verify

        Returns:
            VerifierResult with passed, reason, and score
        """
        logger.info(f"[Verifier] Verifying response ({len(response)} chars)...")

        score = 1.0
        failures = []

        # --- Layer 2: Coherence (run first, cheapest) ---
        coherence_ok, coherence_reason = self._check_coherence(response)
        if not coherence_ok:
            score -= 0.45
            failures.append(f"Coherence: {coherence_reason}")
            logger.warning(f"[Verifier] Coherence fail: {coherence_reason}")

        # --- Layer 1: AST Parse (only if response contains Python code) ---
        if self._response_contains_code(response):
            ast_ok, ast_reason = self._check_ast(response)
            if not ast_ok:
                score -= 0.40
                failures.append(f"Syntax: {ast_reason}")
                logger.warning(f"[Verifier] AST fail: {ast_reason}")

        # Clamp score
        score = max(0.0, score)

        # --- Layer 3: Safety (hard block — always run if available) ---
        if self.use_llama_guard:
            safety_ok, safety_reason = self._check_safety(task, response)
            if not safety_ok:
                logger.warning(f"[Verifier] Safety BLOCK: {safety_reason}")
                return VerifierResult(
                    passed=False,
                    reason=f"SAFETY BLOCK: {safety_reason}",
                    score=0.0,
                )

        # Final determination
        threshold = 0.60  # Must score >= 60% to pass
        passed = score >= threshold

        reason = "All checks passed." if not failures else " | ".join(failures)
        logger.info(f"[Verifier] Score: {score:.2f} | Passed: {passed} | Reason: {reason}")

        return VerifierResult(passed=passed, reason=reason, score=score)

    # ------------------------------------------------------------------
    # Layer 1: AST Parse
    # ------------------------------------------------------------------

    def _response_contains_code(self, response: str) -> bool:
        """Detect if the response contains Python code blocks."""
        return "```python" in response or "def " in response or "import " in response

    def _check_ast(self, response: str) -> tuple[bool, str]:
        """
        Extract Python code from markdown blocks and attempt AST parse.
        Returns (ok, reason).
        """
        # Extract ```python ... ``` blocks
        code_blocks = re.findall(r"```python\s*(.*?)\s*```", response, re.DOTALL)

        if not code_blocks:
            # Try to parse the whole response if it looks like raw code
            code_blocks = [response] if "def " in response else []

        if not code_blocks:
            return True, "No parseable code blocks found"

        for i, block in enumerate(code_blocks):
            try:
                ast.parse(block)
            except SyntaxError as e:
                return False, f"SyntaxError in block {i + 1}: {e.msg} (line {e.lineno})"
            except Exception as e:
                return False, f"Parse error in block {i + 1}: {e}"

        return True, f"All {len(code_blocks)} code block(s) parsed successfully"

    # ------------------------------------------------------------------
    # Layer 2: Coherence Heuristics
    # ------------------------------------------------------------------

    def _check_coherence(self, response: str) -> tuple[bool, str]:
        """
        Basic coherence checks. Returns (ok, reason).
        """
        # 1. Non-empty
        if not response or len(response.strip()) < 10:
            return False, "Response is empty or too short"

        # 2. Not excessively short for a coding task
        if len(response.strip()) < 50:
            return False, f"Response suspiciously short ({len(response.strip())} chars)"

        # 3. Repetition detection — flag if the same sentence repeats 5+ times
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        if lines:
            from collections import Counter
            most_common_count = Counter(lines).most_common(1)[0][1]
            if most_common_count >= 5 and len(lines) > 5:
                return False, f"Repetition detected (line repeated {most_common_count}x)"

        # 4. Truncation detection — response ends mid-sentence or mid-code-block
        stripped = response.strip()
        open_blocks = stripped.count("```") % 2
        if open_blocks != 0:
            return False, "Response appears truncated (unclosed code block)"

        return True, "Coherence OK"

    # ------------------------------------------------------------------
    # Layer 3: Safety via llama-guard
    # ------------------------------------------------------------------

    def _check_safety(self, task: str, response: str) -> tuple[bool, str]:
        """
        Run llama-guard-3:8b safety check on the response.
        Returns (safe, reason).
        """
        guard = self._get_guard_agent()
        if guard is None:
            logger.warning("[Verifier] Safety check skipped — guard unavailable.")
            return True, "Guard unavailable"

        try:
            check = guard.run(
                f"Validate this AI-generated response for safety:\n\nTask: {task}\n\nResponse: {response[:1000]}"
            )
            content = check.content.upper() if hasattr(check, "content") else ""
            if "UNSAFE" in content:
                return False, check.content
            return True, "Safety OK"
        except Exception as e:
            logger.warning(f"[Verifier] Safety check error: {e}")
            return True, f"Safety check error (fail-open): {e}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_verifier = None

def get_verifier() -> LogicVerifier:
    """Returns a shared LogicVerifier instance (lazy init)."""
    global _verifier
    if _verifier is None:
        _verifier = LogicVerifier()
    return _verifier
