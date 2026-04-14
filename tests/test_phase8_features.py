"""
Phase 8: Tests for MONITOR_TOOL, CONTEXT_COLLAPSE helpers, and VERIFICATION_AGENT UI parsing.

All tests run offline — network calls, Docker, and LLM are mocked.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)

# Pre-mock heavy deps
_MOCK_MODULES = [
    "pynvml", "redis",
    "phi", "phi.agent", "phi.model", "phi.model.ollama",
    "phi.knowledge", "phi.knowledge.combined",
    "phi.vectordb", "phi.vectordb.pgvector",
    "phi.storage", "phi.storage.agent", "phi.storage.agent.postgres",
    "langfuse", "langfuse.decorators",
    "httpx", "pydantic", "requests", "prometheus_client",
    "streamlit",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

_phi_agent_mod = sys.modules["phi.agent"]
_phi_agent_mod.Agent = MagicMock
_phi_agent_mod.RunResponse = type("RunResponse", (), {"content": ""})
sys.modules["phi.model.ollama"].Ollama = MagicMock


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  1. MONITOR_TOOL                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestMonitorTool:
    """Tests for agents/tools/monitor_tool.py."""

    def test_check_control_plane_all_healthy(self):
        with patch("tools.monitor_tool._http_check", return_value=True), \
             patch("tools.monitor_tool._tcp_check", return_value=True):
            from tools.monitor_tool import check_control_plane
            result = json.loads(check_control_plane())
            assert result["status"] == "ONLINE"
            assert all(s["healthy"] for s in result["services"])

    def test_check_control_plane_langfuse_down(self):
        def mock_http(url, timeout=3.0):
            return "health" not in url  # Langfuse health check fails
        with patch("tools.monitor_tool._http_check", side_effect=mock_http), \
             patch("tools.monitor_tool._tcp_check", return_value=True):
            from tools.monitor_tool import check_control_plane
            result = json.loads(check_control_plane())
            assert result["status"] == "DEGRADED"
            assert "Langfuse" in result["summary"]

    def test_check_node_connectivity_all_reachable(self):
        with patch("tools.monitor_tool._tcp_check", return_value=True):
            from tools.monitor_tool import check_node_connectivity
            result = json.loads(check_node_connectivity())
            assert result["status"] == "ONLINE"
            assert len(result["nodes"]) == 3

    def test_check_node_connectivity_r730_down(self):
        def mock_tcp(host, port, timeout=2.0):
            return host != "192.168.2.103"
        with patch("tools.monitor_tool._tcp_check", side_effect=mock_tcp):
            from tools.monitor_tool import check_node_connectivity
            result = json.loads(check_node_connectivity())
            assert result["status"] == "DEGRADED"
            assert "R730" in result["summary"]

    def test_system_health_report_structure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"name": "test-container"}]

        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        with patch("tools.monitor_tool._http_check", return_value=True), \
             patch("tools.monitor_tool._tcp_check", return_value=True), \
             patch.dict("sys.modules", {"requests": mock_requests}):
            from tools.monitor_tool import get_system_health_report
            result = json.loads(get_system_health_report())
            assert "status" in result
            assert "summary" in result
            assert "total_containers" in result
            assert "control_plane" in result
            assert "nodes" in result

    def test_system_health_report_degraded(self):
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("Connection refused")
        with patch("tools.monitor_tool._http_check", return_value=False), \
             patch("tools.monitor_tool._tcp_check", return_value=False), \
             patch.dict("sys.modules", {"requests": mock_requests}):
            from tools.monitor_tool import get_system_health_report
            result = json.loads(get_system_health_report())
            assert result["status"] == "DEGRADED"

    def test_tcp_check_with_mock_socket(self):
        with patch("tools.monitor_tool.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.socket.return_value = mock_sock
            from tools.monitor_tool import _tcp_check
            assert _tcp_check("127.0.0.1", 8080) is True

    def test_tcp_check_refused(self):
        with patch("tools.monitor_tool.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 111  # Connection refused
            mock_socket.socket.return_value = mock_sock
            from tools.monitor_tool import _tcp_check
            assert _tcp_check("127.0.0.1", 8080) is False

    def test_tcp_check_exception(self):
        with patch("tools.monitor_tool.socket") as mock_socket:
            mock_socket.socket.side_effect = Exception("Network error")
            from tools.monitor_tool import _tcp_check
            assert _tcp_check("127.0.0.1", 8080) is False

    def test_monitor_tools_list(self):
        from tools.monitor_tool import MONITOR_TOOLS
        assert len(MONITOR_TOOLS) == 3
        assert all(callable(t) for t in MONITOR_TOOLS)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  2. CONTEXT_COLLAPSE (token estimation)                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestTokenEstimation:
    """Tests for the token counter utility (agents/utils/token_counter.py)."""

    def test_count_tokens_basic(self):
        from utils.token_counter import count_tokens
        # chars/4 heuristic, min 1
        result = count_tokens("Hello world")  # 11 chars → 2
        assert isinstance(result, int)
        assert result > 0

    def test_count_tokens_empty(self):
        from utils.token_counter import count_tokens
        result = count_tokens("")
        assert result == 1  # max(1, 0//4) == 1

    def test_count_messages_tokens(self):
        from utils.token_counter import count_messages_tokens
        messages = [
            {"role": "user", "content": "Hello world"},  # 11//4=2 + 4 = 6
            {"role": "assistant", "content": "Hi"},       # 2//4=1(min) + 4 = 5
        ]
        result = count_messages_tokens(messages)
        assert result > 0
        assert isinstance(result, int)

    def test_context_usage(self):
        from utils.token_counter import context_usage
        messages = [{"role": "user", "content": "x" * 400}]  # 100 tokens + 4 overhead
        usage = context_usage(messages, "default")
        assert usage["total"] == 8192
        assert 0 < usage["pct"] < 1.0
        assert usage["used"] > 0


class TestContextCompactLogic:
    """Tests for the context compaction threshold logic."""

    def test_compact_short_conversation_below_threshold(self):
        """Short conversations should stay well below 95% threshold."""
        from utils.token_counter import context_usage
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        usage = context_usage(messages, "default")
        assert usage["pct"] < 0.95  # Way under threshold

    def test_compact_threshold_config_value(self):
        from config import COMPACT_AUTO_THRESHOLD
        assert COMPACT_AUTO_THRESHOLD == 0.95

    def test_token_model_windows(self):
        """Verify model window sizes are reasonable."""
        from config import CONTEXT_WINDOWS
        for model, window in CONTEXT_WINDOWS.items():
            assert window >= 4096, f"Model {model} window too small: {window}"
            assert window <= 131072, f"Model {model} window suspiciously large: {window}"
        assert "default" in CONTEXT_WINDOWS


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  3. VERIFICATION BADGE PARSING                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestVerificationBadgeParsing:
    """
    Tests verifying that the thought trace patterns from MarsRL
    can be correctly parsed to extract verification badges.
    This mirrors the useMemo logic in message-bubble.tsx.
    """

    @staticmethod
    def _parse_verification(thoughts: list[dict]) -> dict | None:
        """Python mirror of the TS useMemo logic in message-bubble.tsx."""
        import re
        if not thoughts:
            return None

        passed = False
        score = 0.0
        iterations = 0
        corrector_used = False
        has_verifier = False

        for t in thoughts:
            c = t.get("content", "")
            match = re.search(r"Verifier:\s*(PASS|FAIL)\s*\(score:\s*([\d.]+)\)", c, re.IGNORECASE)
            if match:
                has_verifier = True
                iterations += 1
                passed = match.group(1).upper() == "PASS"
                score = float(match.group(2))
            if re.search(r"Corrector engaged|Correcting response", c, re.IGNORECASE):
                corrector_used = True

        if not has_verifier:
            return None
        return {"passed": passed, "score": score, "iterations": iterations, "corrector_used": corrector_used}

    def test_pass_first_attempt(self):
        thoughts = [
            {"content": "→ Verifier: PASS (score: 0.92)", "timestamp": 1},
        ]
        result = self._parse_verification(thoughts)
        assert result is not None
        assert result["passed"] is True
        assert result["score"] == 0.92
        assert result["iterations"] == 1
        assert result["corrector_used"] is False

    def test_fail_then_pass_with_corrector(self):
        thoughts = [
            {"content": "→ Verifier: FAIL (score: 0.40) — Corrector engaged", "timestamp": 1},
            {"content": "[Corrector] Revised response generated.", "timestamp": 2},
            {"content": "→ Verifier: PASS (score: 0.85)", "timestamp": 3},
        ]
        result = self._parse_verification(thoughts)
        assert result is not None
        assert result["passed"] is True
        assert result["score"] == 0.85  # Final score
        assert result["iterations"] == 2
        assert result["corrector_used"] is True

    def test_fail_all_rounds(self):
        thoughts = [
            {"content": "→ Verifier: FAIL (score: 0.30) — Corrector engaged", "timestamp": 1},
            {"content": "→ Verifier: FAIL (score: 0.45)", "timestamp": 2},
        ]
        result = self._parse_verification(thoughts)
        assert result is not None
        assert result["passed"] is False
        assert result["score"] == 0.45

    def test_no_verifier_in_trace(self):
        thoughts = [
            {"content": "→ Routing to Architect (qwen2.5-coder:14b)", "timestamp": 1},
            {"content": "DevOps plan generated.", "timestamp": 2},
        ]
        result = self._parse_verification(thoughts)
        assert result is None

    def test_empty_trace(self):
        assert self._parse_verification([]) is None
        assert self._parse_verification(None) is None

    def test_score_boundary_0_60(self):
        """Score exactly at 0.60 threshold."""
        thoughts = [{"content": "→ Verifier: PASS (score: 0.60)", "timestamp": 1}]
        result = self._parse_verification(thoughts)
        assert result["passed"] is True
        assert result["score"] == 0.60

    def test_correcting_response_status(self):
        """The status message 'Correcting response' should mark corrector as used."""
        thoughts = [
            {"content": "🛠️ MarsRL: Correcting response...", "timestamp": 1},
            {"content": "→ Verifier: PASS (score: 0.78)", "timestamp": 2},
        ]
        result = self._parse_verification(thoughts)
        assert result["corrector_used"] is True

    def test_verification_score_parsing_formats(self):
        """Various formatting of the score decimal."""
        for score_str, expected in [("0.95", 0.95), ("1.0", 1.0), ("0.5", 0.5)]:
            thoughts = [{"content": f"→ Verifier: PASS (score: {score_str})", "timestamp": 1}]
            result = self._parse_verification(thoughts)
            assert result["score"] == expected


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  4. MarsRL LOOP STREAM EVENTS                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestMarsLoopStreamEvents:
    """Tests for mars_loop_stream event format consistency."""

    def test_marsloop_result_has_required_fields(self):
        from mars_loop import MarsLoopResult
        result = MarsLoopResult(
            response="Test response",
            iterations=1,
            solver_score=0.9,
            corrector_invoked=False,
            final_score=0.85,
        )
        assert result.response == "Test response"
        assert result.iterations == 1
        assert result.solver_score == 0.9
        assert result.corrector_invoked is False
        assert result.final_score == 0.85

    def test_marsloop_result_optional_fields(self):
        from mars_loop import MarsLoopResult
        result = MarsLoopResult(
            response="Test",
            iterations=2,
            solver_score=0.8,
            corrector_invoked=True,
            final_score=0.75,
            trace_id="abc-123",
            token="jwt-token",
            template_metadata={"template_id": "code_developer"},
        )
        assert result.trace_id == "abc-123"
        assert result.token == "jwt-token"
        assert result.template_metadata["template_id"] == "code_developer"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  5. VERIFIER AGENT UNIT TESTS                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestVerifierAgent:
    """Tests for agents/verifier_agent.py LogicVerifier."""

    def test_verifier_ast_check_valid_python(self):
        from verifier_agent import LogicVerifier
        v = LogicVerifier(use_llama_guard=False)
        ok, reason = v._check_ast("```python\ndef hello():\n    return 'world'\n```")
        assert ok is True

    def test_verifier_ast_check_invalid_python(self):
        from verifier_agent import LogicVerifier
        v = LogicVerifier(use_llama_guard=False)
        ok, reason = v._check_ast("```python\ndef hello(\n```")
        assert ok is False

    def test_verifier_result_structure(self):
        from verifier_agent import VerifierResult
        vr = VerifierResult(passed=True, reason="All checks passed", score=0.95)
        assert vr.passed is True
        assert vr.reason == "All checks passed"
        assert vr.score == 0.95

    def test_verifier_result_failed(self):
        from verifier_agent import VerifierResult
        vr = VerifierResult(passed=False, reason="Truncated response detected", score=0.35)
        assert vr.passed is False
        assert vr.score < 0.6
