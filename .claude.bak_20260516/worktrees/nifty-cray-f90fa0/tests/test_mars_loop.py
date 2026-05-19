"""
tests/test_mars_loop.py

Integration tests for the MarsRL Solver → Verifier → Corrector loop.

Run with:
    pytest tests/test_mars_loop.py -v

Uses mock agents to isolate the loop logic from live Ollama calls.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Helpers: Mock Agents
# ---------------------------------------------------------------------------

@dataclass
class MockRunResponse:
    content: str


def make_solver(response_text: str):
    """Returns a mock solver that always returns response_text."""
    solver = MagicMock()
    solver.run.return_value = MockRunResponse(content=response_text)
    return solver


def make_corrector(corrected_text: str):
    """Returns a mock corrector that always returns corrected_text."""
    corrector = MagicMock()
    corrector.run.return_value = MockRunResponse(content=corrected_text)
    return corrector


# ---------------------------------------------------------------------------
# Import targets (patch Langfuse before importing)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_langfuse(monkeypatch):
    """Disable Langfuse in all tests."""
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3001")

    # Patch langfuse module to prevent real network calls
    import sys
    langfuse_mock = MagicMock()
    langfuse_mock.Langfuse.return_value = MagicMock()
    sys.modules["langfuse"] = langfuse_mock
    
    class DummyDecorators:
        @staticmethod
        def observe(*args, **kwargs):
            return lambda f: f
        langfuse_context = MagicMock()
    sys.modules["langfuse.decorators"] = DummyDecorators


# ---------------------------------------------------------------------------
# Tests: MarsRLLoop
# ---------------------------------------------------------------------------

class TestMarsRLLoop:
    """Unit tests for the MarsRLLoop class."""

    def _make_passing_verifier(self, score: float = 0.95):
        """Verifier that always passes."""
        from verifier_agent import LogicVerifier
        from mars_loop import VerifierResult
        v = MagicMock(spec=LogicVerifier)
        v.verify.return_value = VerifierResult(passed=True, reason="All checks passed.", score=score)
        return v

    def _make_failing_verifier(self, reason: str = "SyntaxError: invalid syntax"):
        """Verifier that always fails."""
        from verifier_agent import LogicVerifier
        from mars_loop import VerifierResult
        v = MagicMock(spec=LogicVerifier)
        v.verify.return_value = VerifierResult(passed=False, reason=reason, score=0.3)
        return v

    def _make_first_fail_then_pass_verifier(self):
        """Verifier that fails on first call, passes on second."""
        from verifier_agent import LogicVerifier
        from mars_loop import VerifierResult
        v = MagicMock(spec=LogicVerifier)
        v.verify.side_effect = [
            VerifierResult(passed=False, reason="Truncated code block", score=0.3),
            VerifierResult(passed=True, reason="All checks passed.", score=0.95),
        ]
        return v

    def test_solver_passes_first_try(self):
        """Verifier passes immediately — Corrector should NOT be called."""
        from mars_loop import MarsRLLoop

        solver = make_solver("def hello(): return 'hello'")
        verifier = self._make_passing_verifier()
        corrector = make_corrector("should not be called")

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        result = loop.run("Write a hello function")

        assert result.iterations == 1
        assert result.corrector_invoked is False
        assert result.solver_score == 1.0  # First try pass
        assert result.final_score >= 0.9
        corrector.run.assert_not_called()

    def test_solver_fails_corrector_invoked(self):
        """Verifier fails first, Corrector is invoked, then verifier passes."""
        from mars_loop import MarsRLLoop

        solver = make_solver("def hello(  # broken")
        verifier = self._make_first_fail_then_pass_verifier()
        corrector = make_corrector("def hello(): return 'hello'")

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        result = loop.run("Write a hello function")

        assert result.corrector_invoked is True
        assert result.iterations == 2  # Solver + Corrector
        assert result.solver_score < 1.0  # Didn't pass on first try
        assert result.final_score >= 0.9
        corrector.run.assert_called_once()

        # Verify corrector received the right args
        call_args = corrector.run.call_args
        assert "Write a hello function" in call_args[0][0]  # original task
        assert "# broken" in call_args[0][1]  # failed response

    def test_max_iterations_respected(self):
        """Verifier always fails — loop should exit at max_iter without hanging."""
        from mars_loop import MarsRLLoop

        solver = make_solver("bad code")
        verifier = self._make_failing_verifier()
        corrector = make_corrector("still bad code")

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        result = loop.run("Write something")

        # Should not raise; should exit gracefully
        assert result.iterations >= 1
        assert result.solver_score == 0.0  # Never passed
        # Corrector called max_iter - 1 times
        assert corrector.run.call_count <= 1  # 2 verify rounds, 1 corrector call

    def test_solver_crash_returns_error_result(self):
        """If Solver crashes, loop returns a graceful error result."""
        from mars_loop import MarsRLLoop

        solver = MagicMock()
        solver.run.side_effect = RuntimeError("Ollama connection refused")
        verifier = self._make_passing_verifier()
        corrector = make_corrector("won't be called")

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        result = loop.run("Write something")

        assert "Solver failed" in result.response
        assert result.solver_score == 0.0
        assert result.iterations == 0


# ---------------------------------------------------------------------------
# Tests: LogicVerifier
# ---------------------------------------------------------------------------

class TestLogicVerifier:
    """Unit tests for the LogicVerifier layers."""

    def _make_verifier(self, use_guard: bool = False):
        from verifier_agent import LogicVerifier
        return LogicVerifier(use_llama_guard=use_guard)

    def test_valid_python_passes(self):
        v = self._make_verifier()
        result = v.verify(
            "Write a fibonacci function",
            "```python\ndef fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n```"
        )
        assert result.passed is True
        assert result.score >= 0.6

    def test_syntax_error_fails(self):
        v = self._make_verifier()
        result = v.verify(
            "Write a function",
            "```python\ndef foo(\n    # missing closing\n```"
        )
        assert result.passed is False
        assert "Syntax" in result.reason or "SyntaxError" in result.reason
        assert result.score < 0.6

    def test_empty_response_fails(self):
        v = self._make_verifier()
        result = v.verify("Write something", "")
        assert result.passed is False
        assert result.score < 0.6

    def test_repetitive_response_fails(self):
        v = self._make_verifier()
        repeated = "\n".join(["Hello there!"] * 20)  # same line 20 times
        result = v.verify("Say hello once", repeated)
        assert result.passed is False

    def test_unclosed_codeblock_fails(self):
        v = self._make_verifier()
        result = v.verify(
            "Write code",
            "Here is your code that is sufficiently long to pass length checks:\n```python\ndef foo():\n    pass\n"  # No closing ```
        )
        assert result.passed is False
        assert "truncated" in result.reason.lower()

    def test_plain_text_research_passes(self):
        """Non-code responses should pass coherence without AST check."""
        v = self._make_verifier()
        result = v.verify(
            "What is machine learning?",
            "Machine learning is a subset of artificial intelligence that enables computers to learn from data."
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# Tests: mars_loop_stream
# ---------------------------------------------------------------------------

class TestMarsLoopStream:
    """Test that the streaming generator yields expected message types."""

    def test_stream_yields_response_on_success(self):
        from mars_loop import MarsRLLoop, mars_loop_stream, VerifierResult

        solver = make_solver("def ok(): pass")
        verifier = MagicMock()
        verifier.verify.return_value = VerifierResult(passed=True, reason="OK", score=1.0)
        corrector = make_corrector("unused")

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        updates = list(mars_loop_stream("Write a function", loop))

        types = [u["type"] for u in updates]
        assert "response" in types
        assert "error" not in types

    def test_stream_yields_error_on_loop_crash(self):
        from mars_loop import MarsRLLoop, mars_loop_stream

        solver = MagicMock()
        solver.run.side_effect = RuntimeError("GPU OOM")
        verifier = MagicMock()
        corrector = MagicMock()

        loop = MarsRLLoop(solver, verifier, corrector, max_iter=2)
        updates = list(mars_loop_stream("Write something", loop))

        types = [u["type"] for u in updates]
        # Should yield a response (graceful error) or a log, not blow up
        assert "error" in types or "response" in types
