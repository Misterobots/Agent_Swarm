"""
mars_loop.py — MarsRL Inference-Time Loop

Implements the Solver → Verifier → Corrector pipeline inspired by:
  - MarsRL (Nov 2025): agent-specific reward signals for multi-agent systems
  - MiniMax Forge: process-level rewards, decoupled training/inference

The loop is model-agnostic. Pass any Solver, Verifier, and Corrector
that expose a .run(prompt) interface.
"""

import time
import logging
import threading
import queue
from dataclasses import dataclass, field
from typing import Optional, Callable

from logger_setup import setup_logger

logger = setup_logger("MarsLoop")

# --- Optional Langfuse integration ---
try:
    from langfuse import Langfuse, observe
    import os

    _langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-dev"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dev"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
    )
    USE_LANGFUSE = True
    logger.info("[MarsLoop] Langfuse tracing enabled")
except ImportError:
    USE_LANGFUSE = False
    observe = lambda *a, **kw: lambda f: f  # noqa: E731
    _langfuse = None
    logger.warning("[MarsLoop] Langfuse not available — process rewards disabled")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class VerifierResult:
    """Structured output from LogicVerifier."""
    passed: bool
    reason: str
    score: float  # 0.0–1.0


@dataclass
class MarsLoopResult:
    """Final result from one complete Mars loop execution."""
    response: str
    iterations: int                         # How many Solver/Corrector rounds
    solver_score: float                     # 1.0 if passed on first try
    corrector_invoked: bool
    final_score: float                      # Verifier's final score
    trace_id: Optional[str] = None          # Langfuse trace ID (if available)
    token: Optional[str] = None             # JWT-ACE token used during execution
    template_metadata: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Loop
# ---------------------------------------------------------------------------

class MarsRLLoop:
    """
    Inference-time MarsRL loop.

    Wraps a multi-agent Solver → Verifier → Corrector pipeline.
    Process rewards are injected into Langfuse at each step,
    building a training dataset for future fine-tuning.
    """

    def __init__(
        self,
        solver,
        verifier,
        corrector,
        max_iter: int = 2,
        intent: str = "CODE",
        session_id: Optional[str] = None,
        token: Optional[str] = None,
        template_metadata: Optional[dict] = None,
    ):
        self.solver = solver
        self.verifier = verifier
        self.corrector = corrector
        self.max_iter = max_iter
        self.intent = intent
        self.session_id = session_id
        self.token = token
        self.template_metadata = template_metadata or {}

    @observe(name="mars_loop")
    def run(self, task: str, event_callback: Optional[Callable[[dict], None]] = None, stream_timeout: float = 60.0) -> MarsLoopResult:
        """
        Executes the MarsRL loop: Solver → Verifier → Corrector.
        Uses event_callback to yield granular status/message/log events for UI.
        """
        logger.info(f"[MarsLoop] Starting loop for intent: {self.intent} | Session: {self.session_id}")
        logger.info(f"[MarsLoop] Task: {task[:100]}...")

        trace_id = None
        if USE_LANGFUSE and _langfuse:
            try:
                trace_metadata = {"intent": self.intent, "max_iter": self.max_iter}
                # Enrich with JWT-ACE template metadata
                if self.template_metadata:
                    trace_metadata.update({
                        "template_id": self.template_metadata.get("template_id"),
                        "template_version": self.template_metadata.get("template_version"),
                        "agent_instance_id": self.template_metadata.get("agent_instance_id"),
                        "token_capabilities": self.template_metadata.get("token_capabilities"),
                    })
                trace = _langfuse.trace(
                    name="mars_loop",
                    session_id=self.session_id,
                    metadata=trace_metadata,
                )
                trace_id = trace.id
            except Exception as e:
                logger.warning(f"[MarsLoop] Trace creation failed: {e}")

        current_response = ""
        iterations = 0
        corrector_invoked = False
        final_score = 0.0
        solver_score = 0.0

        # --- Step 1: Solver ---
        if event_callback:
            event_callback({"type": "status", "content": "🏗️ MarsRL: Solver is generating initial response..."})

        t0 = time.time()
        last_tok_time = time.time()
        try:
            if event_callback:
                current_response = ""
                solver_stream = self.solver.run(task, stream=True)
                for chunk in solver_stream:
                    # Update heartbeat for timeout detection
                    last_tok_time = time.time()
                    
                    if hasattr(chunk, "content") and chunk.content:
                        current_response += chunk.content
                        event_callback({"type": "message", "content": chunk.content})
                    
                    # Check for idle timeout during stream
                    if time.time() - last_tok_time > stream_timeout:
                        logger.warning(f"[MarsLoop] Solver stream idle for {stream_timeout}s. Current Response Len: {len(current_response)}")
                        event_callback({"type": "log", "content": f"⚠️ Solver stream idle for {stream_timeout}s. Checking for results..."})
                        # Don't necessarily break if we have some content; the loop might just be thinking
                        # But for safety, we break to avoid UI hang if TTFT is too long
                        break
            else:
                solver_resp = self.solver.run(task)
                current_response = solver_resp.content if hasattr(solver_resp, "content") else str(solver_resp)
                
            iterations += 1
            logger.info(f"[MarsLoop] Solver completed in {time.time() - t0:.2f}s")
        except Exception as e:
            logger.error(f"[MarsLoop] Solver failed: {e}")
            return MarsLoopResult(
                response=f"Solver failed: {e}",
                iterations=0,
                solver_score=0.0,
                corrector_invoked=False,
                final_score=0.0,
            )

        # --- Step 2: Verify → Correct loop ---
        for attempt in range(self.max_iter):
            if event_callback:
                event_callback({"type": "status", "content": f"🔍 MarsRL: Verifying attempt {attempt + 1}/{self.max_iter}..."})

            try:
                vr: VerifierResult = self.verifier.verify(task, current_response)
            except Exception as e:
                logger.error(f"[MarsLoop] Verifier error: {e}")
                vr = VerifierResult(passed=True, reason="Verifier unavailable", score=0.7)

            final_score = vr.score
            if event_callback:
                event_callback({"type": "log", "content": f"[Verifier] Score: {vr.score:.2f} | Reason: {vr.reason}"})

            self._inject_score(f"verifier_round_{attempt + 1}", vr.score, vr.reason, trace_id)

            if vr.passed:
                solver_score = 1.0 if attempt == 0 else max(0.0, 1.0 - attempt * 0.3)
                if event_callback:
                    event_callback({"type": "status", "content": "✅ MarsRL: Verification Passed!"})
                break

            # --- Step 3: Corrector ---
            if attempt < self.max_iter - 1:
                if event_callback:
                    event_callback({"type": "status", "content": f"🛠️ MarsRL: Correcting response..."})
                
                corrector_invoked = True
                try:
                    corrected = self.corrector.run(task, current_response, vr.reason)
                    current_response = corrected.content if hasattr(corrected, "content") else str(corrected)
                    iterations += 1
                    if event_callback:
                         event_callback({"type": "log", "content": "[Corrector] Revised response generated."})
                except Exception as e:
                    logger.error(f"[MarsLoop] Corrector failed: {e}")
                    break
            else:
                if event_callback:
                    event_callback({"type": "status", "content": "⚠️ MarsRL: Max iterations reached."})

        self._inject_score("solver_score", solver_score, f"Passed in {iterations} round(s)", trace_id)
        self._inject_score("final_quality", final_score, "Final verifier score", trace_id)

        # Tag high-reward traces as training candidates for future fine-tuning
        if final_score > 0.8:
            self._inject_score("training_candidate", 1.0, "High-reward trace for training export", trace_id)

        return MarsLoopResult(
            response=current_response,
            iterations=iterations,
            solver_score=solver_score,
            corrector_invoked=corrector_invoked,
            final_score=final_score,
            trace_id=trace_id,
            token=self.token,
            template_metadata=self.template_metadata,
        )

    def _inject_score(self, name: str, value: float, comment: str, trace_id: Optional[str]):
        if not USE_LANGFUSE or _langfuse is None:
            return
        try:
            _langfuse.score(name=name, value=value, comment=comment, trace_id=trace_id)
        except Exception as e:
            logger.warning(f"[MarsLoop] Failed to inject Langfuse score: {e}")


# ---------------------------------------------------------------------------
# Generator variant for UI streaming
# ---------------------------------------------------------------------------

def mars_loop_stream(task: str, loop: MarsRLLoop):
    """
    Generator wrapper for chat_swarm UI compatibility.
    """
    q = queue.Queue()

    def worker():
        try:
            def event_callback(update):
                q.put(update)
            result = loop.run(task, event_callback=event_callback)
            q.put({"type": "result", "content": result})
        except Exception as e:
            logger.error(f"[MarsLoop] Worker Thread Crash: {e}", exc_info=True)
            q.put({"type": "error", "content": str(e)})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    last_heartbeat = time.time()
    
    while True:
        try:
            msg = q.get(timeout=1.0)
            
            if msg["type"] == "result":
                result: MarsLoopResult = msg["content"]
                yield {
                    "type": "log",
                    "content": (f"[MarsRL] Iterations: {result.iterations} | Score: {result.final_score:.2f}")
                }
                yield {"type": "response", "content": result.response}
                break
            elif msg["type"] == "error":
                yield msg
                break
            else:
                yield msg
                
        except queue.Empty:
            if not t.is_alive() and q.empty():
                yield {"type": "log", "content": "[MarsRL] Loop terminated unexpectedly."}
                break
            
            if time.time() - last_heartbeat > 5.0:
                # Use 'log' type for heartbeats to keep stream active without UI artifacts
                yield {"type": "log", "content": "\u200B"}
                last_heartbeat = time.time()
