"""
mars_loop.py — MarsRL Inference-Time Loop

Implements the Solver → Verifier → Corrector pipeline inspired by:
  - MarsRL (Nov 2025): agent-specific reward signals for multi-agent systems
  - MiniMax Forge: process-level rewards, decoupled training/inference

The loop is model-agnostic. Pass any Solver, Verifier, and Corrector
that expose a .run(prompt) interface.
"""

import time
import re
import logging
import threading
import queue
import concurrent.futures
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

from config import SOLVING_MAX_TIME

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
        max_time: Optional[int] = None,  # seconds — overall wall-clock budget
        # Per-agent granular controls (developer mode). 0 / None = no per-call cap.
        solver_n_drafts: int = 1,
        solver_max_time: Optional[int] = None,
        verifier_max_time: Optional[int] = None,
        corrector_max_time: Optional[int] = None,
    ):
        self.solver = solver
        self.verifier = verifier
        self.corrector = corrector
        self.max_iter = max_iter
        self.intent = intent
        self.session_id = session_id
        self.token = token
        self.template_metadata = template_metadata or {}
        # Use config default if not provided
        self.max_time = max_time if max_time is not None else SOLVING_MAX_TIME
        # Per-agent budgets. Clamp drafts to [1, 10] for safety.
        self.solver_n_drafts = max(1, min(int(solver_n_drafts or 1), 10))
        self.solver_max_time = solver_max_time if solver_max_time else None
        self.verifier_max_time = verifier_max_time if verifier_max_time else None
        self.corrector_max_time = corrector_max_time if corrector_max_time else None

    @staticmethod
    def _call_with_timeout(fn, timeout_s: Optional[int], *args, **kwargs):
        """Run a blocking fn with optional wall-clock cap. Raises concurrent.futures.TimeoutError on overrun.
        Note: the worker thread keeps running on timeout (Python can't kill it remotely) — the LLM
        call continues server-side until it finishes naturally. This just stops US from waiting."""
        if not timeout_s or timeout_s <= 0:
            return fn(*args, **kwargs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(fn, *args, **kwargs)
            return future.result(timeout=timeout_s)

    @observe(name="mars_loop")
    def run(self, task: str, event_callback: Optional[Callable[[dict], None]] = None, stream_timeout: float = 60.0) -> MarsLoopResult:
        """
        Executes the MarsRL loop: Solver → Verifier → Corrector.
        Uses event_callback to yield granular status/message/log events for UI.
        """
        logger.info(f"[MarsLoop] Starting loop for intent: {self.intent} | Session: {self.session_id}")
        logger.info(f"[MarsLoop] Task: {task[:100]}...")

        trace_id = None
        _lf_ctx = None
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
                _lf_ctx = _langfuse.start_as_current_observation(
                    name="mars_loop",
                    as_type="agent",
                    input={"input": task[:4000]},
                    metadata=trace_metadata,
                )
                _lf_ctx.__enter__()
                trace_id = _langfuse.get_current_trace_id()
            except Exception as e:
                _lf_ctx = None
                logger.warning(f"[MarsLoop] Trace creation failed: {e}")

        current_response = ""
        iterations = 0
        corrector_invoked = False
        final_score = 0.0
        solver_score = 0.0
        start_time = time.time()
        pre_winner_vr: Optional[VerifierResult] = None  # Pre-verified Best-of-N winner, if any

        # --- Step 1: Solver (single pass OR Best-of-N drafts) ---
        n_drafts = self.solver_n_drafts
        # When N > 1, streaming is disabled across all drafts to avoid the UI
        # seeing one draft's text replaced by a different winner.
        allow_streaming = (n_drafts == 1)

        if event_callback:
            if n_drafts > 1:
                event_callback({"type": "status", "content": f"🏗️ MarsRL: Generating {n_drafts} solver drafts (best-of-N)..."})
                event_callback({"type": "thought", "content": f"→ MarsRL: Best-of-{n_drafts} drafts, then up to {self.max_iter} verify/correct rounds"})
            else:
                event_callback({"type": "status", "content": "🏗️ MarsRL: Solver is generating initial response..."})
                event_callback({"type": "thought", "content": f"→ MarsRL: Solver generating (max {self.max_iter} iterations)"})

        drafts: list[tuple[str, Optional[VerifierResult], float]] = []  # (response, verifier_result, elapsed_s)

        try:
            for draft_idx in range(n_drafts):
                if n_drafts > 1 and event_callback:
                    event_callback({"type": "status", "content": f"🏗️ MarsRL: Solver draft {draft_idx + 1}/{n_drafts}..."})

                draft_resp, draft_elapsed = self._execute_solver_pass(
                    task=task,
                    event_callback=event_callback if allow_streaming else None,
                    stream_timeout=stream_timeout,
                    trace_id=trace_id,
                    draft_idx=draft_idx,
                    n_drafts=n_drafts,
                )

                # When N > 1, score each draft now so we can pick a winner
                if n_drafts > 1:
                    try:
                        draft_vr = self._call_with_timeout(
                            self.verifier.verify,
                            self.verifier_max_time,
                            task, draft_resp, intent=self.intent,
                        )
                    except concurrent.futures.TimeoutError:
                        logger.warning(f"[MarsLoop] Draft {draft_idx + 1} verifier timeout after {self.verifier_max_time}s")
                        draft_vr = VerifierResult(passed=False, reason=f"verifier timeout ({self.verifier_max_time}s)", score=0.0)
                    except Exception as e:
                        logger.warning(f"[MarsLoop] Draft {draft_idx + 1} verifier error: {e}")
                        draft_vr = VerifierResult(passed=False, reason=f"verifier error: {e}", score=0.0)
                    drafts.append((draft_resp, draft_vr, draft_elapsed))
                    if event_callback:
                        event_callback({"type": "log", "content": f"[Draft {draft_idx + 1}/{n_drafts}] Score: {draft_vr.score:.2f} | {'PASS' if draft_vr.passed else 'FAIL'} | {draft_elapsed:.1f}s"})
                else:
                    drafts.append((draft_resp, None, draft_elapsed))

                # Respect overall budget across drafts
                if self.max_time and (time.time() - start_time) > self.max_time:
                    if event_callback:
                        event_callback({"type": "log", "content": f"[MarsRL] Overall time limit reached during drafts — using best so far"})
                    break

            # Pick the winner
            if n_drafts > 1 and any(vr is not None for _, vr, _ in drafts):
                # Rank by (passed desc, score desc)
                scored = [(r, vr, e) for r, vr, e in drafts if vr is not None]
                scored.sort(key=lambda x: (1 if x[1].passed else 0, x[1].score), reverse=True)
                current_response, pre_winner_vr, _ = scored[0]
                if event_callback:
                    event_callback({"type": "status", "content": f"✨ MarsRL: Best-of-{n_drafts} winner selected (score: {pre_winner_vr.score:.2f})"})
                    event_callback({"type": "message", "content": current_response})
            else:
                current_response = drafts[0][0]

            iterations += 1
            solver_elapsed = time.time() - start_time
            logger.info(f"[MarsLoop] Solver phase completed in {solver_elapsed:.2f}s ({n_drafts} draft(s))")

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
            # Check time limit before each iteration
            if self.max_time and (time.time() - start_time) > self.max_time:
                logger.info(f"[MarsLoop] Time limit reached: {self.max_time}s. Stopping iterations.")
                if event_callback:
                    event_callback({"type": "status", "content": f"⏰ MarsRL: Time limit reached ({self.max_time}s). Stopping."})
                break
            if event_callback:
                event_callback({"type": "status", "content": f"🔍 MarsRL: Verifying attempt {attempt + 1}/{self.max_iter}..."})

            # Reuse the Best-of-N pre-verification for the first iteration (avoids a duplicate verifier call).
            if attempt == 0 and pre_winner_vr is not None:
                vr = pre_winner_vr
            else:
                try:
                    vr = self._call_with_timeout(
                        self.verifier.verify,
                        self.verifier_max_time,
                        task, current_response, intent=self.intent,
                    )
                except concurrent.futures.TimeoutError:
                    logger.warning(f"[MarsLoop] Verifier timeout after {self.verifier_max_time}s — treating as pass")
                    vr = VerifierResult(passed=True, reason=f"Verifier timeout ({self.verifier_max_time}s)", score=0.7)
                except Exception as e:
                    logger.error(f"[MarsLoop] Verifier error: {e}")
                    vr = VerifierResult(passed=True, reason="Verifier unavailable", score=0.7)

            final_score = vr.score
            if event_callback:
                event_callback({"type": "log", "content": f"[Verifier] Score: {vr.score:.2f} | Reason: {vr.reason}"})

            self._inject_score(f"verifier_round_{attempt + 1}", vr.score, vr.reason, trace_id)

            # Langfuse span for verifier
            if USE_LANGFUSE and _langfuse and trace_id:
                try:
                    with _langfuse.start_as_current_observation(
                        name=f"verifier_round_{attempt + 1}",
                        as_type="span",
                        input=current_response[:1000],
                        output={"passed": vr.passed, "score": vr.score, "reason": vr.reason},
                        metadata={"attempt": attempt + 1},
                    ):
                        pass
                except Exception as e_span:
                    logger.debug(f"[MarsLoop] Verifier span failed: {e_span}")

            if vr.passed:
                solver_score = 1.0 if attempt == 0 else max(0.0, 1.0 - attempt * 0.3)
                if event_callback:
                    event_callback({"type": "status", "content": "✅ MarsRL: Verification Passed!"})
                    event_callback({"type": "thought", "content": f"→ Verifier: PASS (score: {vr.score:.2f})"})
                break

            # --- Step 3: Corrector ---
            if attempt < self.max_iter - 1:
                if event_callback:
                    event_callback({"type": "status", "content": f"🛠️ MarsRL: Correcting response..."})
                    event_callback({"type": "thought", "content": f"→ Verifier: FAIL (score: {vr.score:.2f}) — Corrector engaged"})

                corrector_invoked = True
                t_corr = time.time()
                try:
                    corrected = self._call_with_timeout(
                        self.corrector.run,
                        self.corrector_max_time,
                        task, current_response, vr.reason,
                    )
                    current_response = corrected.content if hasattr(corrected, "content") else str(corrected)
                    iterations += 1
                    corr_elapsed = time.time() - t_corr

                    # Langfuse span for corrector
                    if USE_LANGFUSE and _langfuse and trace_id:
                        try:
                            with _langfuse.start_as_current_observation(
                                name="corrector_generation",
                                as_type="span",
                                input={"task": task[:1000], "failure_reason": vr.reason},
                                output=current_response[:2000],
                                metadata={
                                    "elapsed_s": round(corr_elapsed, 2),
                                    "response_len": len(current_response),
                                },
                            ):
                                pass
                        except Exception as e_span:
                            logger.debug(f"[MarsLoop] Corrector span failed: {e_span}")

                    if event_callback:
                         event_callback({"type": "log", "content": "[Corrector] Revised response generated."})
                except concurrent.futures.TimeoutError:
                    logger.warning(f"[MarsLoop] Corrector timeout after {self.corrector_max_time}s — stopping loop")
                    if event_callback:
                        event_callback({"type": "log", "content": f"⏰ Corrector timeout ({self.corrector_max_time}s) — returning best so far"})
                    break
                except Exception as e:
                    logger.error(f"[MarsLoop] Corrector failed: {e}")
                    break
            else:
                if event_callback:
                    event_callback({"type": "status", "content": "⚠️ MarsRL: Max iterations reached."})

        self._inject_score("solver_score", solver_score, f"Passed in {iterations} round(s)", trace_id)
        self._inject_score("final_quality", final_score, "Final verifier score", trace_id)

        # Update trace with final output and close context
        if USE_LANGFUSE and _langfuse and trace_id:
            try:
                _langfuse.set_current_trace_io(output={"response": current_response[:4000]})
            except Exception:
                pass
            try:
                if _lf_ctx is not None:
                    _lf_ctx.__exit__(None, None, None)
                    _lf_ctx = None
            except Exception:
                pass

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

    def _execute_solver_pass(
        self,
        task: str,
        event_callback: Optional[Callable[[dict], None]],
        stream_timeout: float,
        trace_id: Optional[str],
        draft_idx: int,
        n_drafts: int,
    ) -> tuple[str, float]:
        """One solver invocation. Returns (response_text, elapsed_seconds).

        When event_callback is provided and the solver has no tools, streams chunks
        via the callback. Otherwise uses non-streaming mode. The wall-clock cap
        from self.solver_max_time is enforced in streaming mode by breaking the
        chunk loop, and in non-streaming mode via _call_with_timeout."""
        t0 = time.time()
        last_tok_time = time.time()
        _solver_has_tools = bool(getattr(self.solver, "tools", None))
        _in_think = False
        current_response = ""

        if event_callback and not _solver_has_tools:
            # --- Streaming mode (no tools, N == 1) ---
            solver_deadline = t0 + self.solver_max_time if self.solver_max_time else None
            solver_stream = self.solver.run(task, stream=True)
            for chunk in solver_stream:
                last_tok_time = time.time()

                if hasattr(chunk, "content") and chunk.content:
                    raw = chunk.content
                    parts = re.split(r'(<think>|</think>)', raw)
                    for part in parts:
                        if part == '<think>':
                            _in_think = True
                            continue
                        elif part == '</think>':
                            _in_think = False
                            continue
                        if not part:
                            continue
                        if _in_think:
                            event_callback({"type": "thought", "content": part})
                        else:
                            current_response += part
                            event_callback({"type": "message", "content": part})

                # Idle timeout
                if time.time() - last_tok_time > stream_timeout:
                    logger.warning(f"[MarsLoop] Solver stream idle for {stream_timeout}s. Len: {len(current_response)}")
                    event_callback({"type": "log", "content": f"⚠️ Solver stream idle for {stream_timeout}s. Checking for results..."})
                    break

                # Wall-clock cap
                if solver_deadline and time.time() > solver_deadline:
                    logger.warning(f"[MarsLoop] Solver wall-clock {self.solver_max_time}s reached")
                    event_callback({"type": "log", "content": f"⏰ Solver wall-clock cap ({self.solver_max_time}s) reached"})
                    break
        else:
            # --- Non-streaming mode (tools present, Best-of-N, or no UI callback) ---
            if _solver_has_tools and event_callback and n_drafts == 1:
                event_callback({"type": "log", "content": "[MarsRL] Solver has tools — using non-streaming mode for tool execution"})
            try:
                solver_resp = self._call_with_timeout(self.solver.run, self.solver_max_time, task)
            except concurrent.futures.TimeoutError:
                logger.warning(f"[MarsLoop] Solver (draft {draft_idx + 1}) timeout after {self.solver_max_time}s")
                if event_callback:
                    event_callback({"type": "log", "content": f"⏰ Solver draft {draft_idx + 1} timeout ({self.solver_max_time}s)"})
                return ("", time.time() - t0)
            current_response = solver_resp.content if hasattr(solver_resp, "content") else str(solver_resp)
            current_response = re.sub(r'<think>.*?</think>', '', current_response, flags=re.DOTALL).strip()
            # Only forward to UI when streaming-equivalent (N == 1). N > 1 drafts are
            # collected silently — the winner is emitted after selection.
            if event_callback and n_drafts == 1:
                raw_resp = solver_resp.content if hasattr(solver_resp, "content") else str(solver_resp)
                event_callback({"type": "message", "content": raw_resp})

        solver_elapsed = time.time() - t0

        # Langfuse span per draft
        if USE_LANGFUSE and _langfuse and trace_id:
            try:
                with _langfuse.start_as_current_observation(
                    name=f"solver_draft_{draft_idx + 1}" if n_drafts > 1 else "solver_generation",
                    as_type="span",
                    input=task[:2000],
                    output=current_response[:2000],
                    metadata={
                        "model": getattr(self.solver, "model", {}).get("id", "unknown") if hasattr(self.solver, "model") and isinstance(getattr(self.solver, "model", None), dict) else str(getattr(self.solver, "model", "unknown")),
                        "elapsed_s": round(solver_elapsed, 2),
                        "response_len": len(current_response),
                        "draft_idx": draft_idx,
                        "n_drafts": n_drafts,
                    },
                ):
                    pass
            except Exception as e_span:
                logger.debug(f"[MarsLoop] Solver span failed: {e_span}")

        return current_response, solver_elapsed

    def _inject_score(self, name: str, value: float, comment: str, trace_id: Optional[str]):
        if not USE_LANGFUSE or _langfuse is None:
            return
        try:
            _langfuse.create_score(name=name, value=value, comment=comment, trace_id=trace_id)
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
