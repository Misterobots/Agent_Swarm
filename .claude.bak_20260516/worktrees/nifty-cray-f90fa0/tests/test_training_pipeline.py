"""
Training Pipeline Unit Tests
================================

Tests for the GRPO training pipeline: reward function, A/B testing logic,
trace export, synthetic generation, GRPO trainer config, and GGUF conversion.

Uses mocked external services (PostgreSQL, Ollama, Langfuse) to test logic
in isolation.
"""

import pytest
import json
import math
import random
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


# ──────────────────────────────────────────────────────────────
# Reward Function Tests (U9-U12)
# ──────────────────────────────────────────────────────────────
class TestRewardFunction:
    """Test multi-objective GRPO reward computation."""

    def test_perfect_score(self):
        """U9: All components perfect → composite = 1.0"""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        signal = rf.compute_reward(final_score=1.0, iterations=1, safety_passed=True)
        assert signal.composite == pytest.approx(1.0)
        assert signal.correctness == 1.0
        assert signal.efficiency == 1.0
        assert signal.safety == 1.0

    def test_weighted_composite(self):
        """U10: Verify weighted sum: 0.8×0.5 + 0.6×0.3 + 1.0×0.2 = 0.78"""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        # iterations=1 gives efficiency=1.0, but we want 0.6
        # efficiency = 1/iterations, so for 0.5 we need iterations=2
        # Let's compute: correctness=0.8, iterations=2 → efficiency=0.5, safety=1.0
        signal = rf.compute_reward(final_score=0.8, iterations=2, safety_passed=True)
        expected = 0.8 * 0.5 + 0.5 * 0.3 + 1.0 * 0.2
        assert signal.composite == pytest.approx(expected)
        assert signal.correctness == 0.8
        assert signal.efficiency == 0.5

    def test_safety_failure_penalty(self):
        """U11: Safety failure (guard blocked) penalizes composite."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        safe = rf.compute_reward(final_score=0.9, iterations=1, safety_passed=True)
        unsafe = rf.compute_reward(final_score=0.9, iterations=1, safety_passed=False)
        assert unsafe.composite < safe.composite
        assert unsafe.safety == 0.0
        assert safe.safety == 1.0
        # The penalty is exactly 0.2 (safety weight)
        assert safe.composite - unsafe.composite == pytest.approx(0.2)

    def test_all_zeros(self):
        """U12: Edge case — all zeros, no crash."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        signal = rf.compute_reward(final_score=0.0, iterations=1, safety_passed=False)
        assert signal.composite == pytest.approx(0.0 * 0.5 + 1.0 * 0.3 + 0.0 * 0.2)
        # efficiency is 1/1 = 1.0 even with "zero" score

    def test_correctness_clamped(self):
        """Correctness should be clamped to [0, 1]."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        over = rf.compute_reward(final_score=1.5, iterations=1, safety_passed=True)
        under = rf.compute_reward(final_score=-0.5, iterations=1, safety_passed=True)
        assert over.correctness == 1.0
        assert under.correctness == 0.0

    def test_group_advantages_sum_to_zero(self):
        """GRPO advantages should sum to approximately zero."""
        from training.reward_function import MarsRewardFunction, RewardSignal
        rf = MarsRewardFunction()
        rewards = [
            rf.compute_reward(final_score=0.9, iterations=1, safety_passed=True),
            rf.compute_reward(final_score=0.7, iterations=2, safety_passed=True),
            rf.compute_reward(final_score=0.5, iterations=3, safety_passed=False),
            rf.compute_reward(final_score=0.8, iterations=1, safety_passed=True),
        ]
        advantages = rf.compute_group_advantages(rewards)
        assert len(advantages) == 4
        assert sum(advantages) == pytest.approx(0.0, abs=1e-10)

    def test_group_advantages_empty(self):
        """Empty reward list → empty advantages."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        assert rf.compute_group_advantages([]) == []

    def test_reward_from_trajectory(self):
        """Reward extracted from trajectory dict matches expectations."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction()
        trajectory = {
            "id": "test",
            "conversations": [],
            "reward": {"correctness": 0.9, "efficiency": 0.5, "safety": 1.0},
        }
        signal = rf.reward_from_trajectory(trajectory)
        assert signal.correctness == 0.9
        assert signal.efficiency == 0.5
        assert signal.safety == 1.0
        expected_composite = 0.9 * 0.5 + 0.5 * 0.3 + 1.0 * 0.2
        assert signal.composite == pytest.approx(expected_composite)

    def test_custom_weights(self):
        """Custom weights are applied correctly."""
        from training.reward_function import MarsRewardFunction
        rf = MarsRewardFunction(
            correctness_weight=1.0,
            efficiency_weight=0.0,
            safety_weight=0.0,
        )
        signal = rf.compute_reward(final_score=0.7, iterations=1, safety_passed=True)
        assert signal.composite == pytest.approx(0.7)


# ──────────────────────────────────────────────────────────────
# A/B Testing Logic Tests (U21-U27)
# ──────────────────────────────────────────────────────────────
class TestABTestStatistics:
    """Test A/B test statistical logic (no DB required)."""

    def test_welch_t_test_identical(self):
        """Identical distributions → p ≈ 1.0"""
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        p = mgr._welch_t_test([0.8, 0.8, 0.8, 0.8], [0.8, 0.8, 0.8, 0.8])
        assert p > 0.9  # Not significant

    def test_welch_t_test_very_different(self):
        """Very different distributions → p ≈ 0.0"""
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        a = [0.95, 0.93, 0.97, 0.94, 0.96, 0.92, 0.95, 0.93, 0.96, 0.94]
        b = [0.50, 0.52, 0.48, 0.51, 0.49, 0.53, 0.50, 0.52, 0.48, 0.51]
        p = mgr._welch_t_test(a, b)
        assert p < 0.001  # Highly significant

    def test_welch_t_test_insufficient_data(self):
        """Less than 2 samples → p = 1.0"""
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        assert mgr._welch_t_test([0.8], [0.7, 0.8]) == 1.0
        assert mgr._welch_t_test([0.8, 0.9], [0.7]) == 1.0
        assert mgr._welch_t_test([], []) == 1.0

    def test_welch_t_test_zero_variance(self):
        """Zero variance (all same values) → p = 1.0 (se = 0)."""
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        p = mgr._welch_t_test([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        assert p == 1.0

    def test_normal_cdf_known_values(self):
        """Normal CDF at known points."""
        from training.ab_test import ABTestManager
        assert ABTestManager._normal_cdf(0.0) == pytest.approx(0.5, abs=0.001)
        assert ABTestManager._normal_cdf(1.96) == pytest.approx(0.975, abs=0.005)
        assert ABTestManager._normal_cdf(-1.96) == pytest.approx(0.025, abs=0.005)

    def test_traffic_split_distribution(self):
        """U22: 80/20 split distributes correctly over 1000 calls."""
        from training.ab_test import ABTestManager

        split = 0.2
        random.seed(42)
        candidate_count = sum(1 for _ in range(1000) if random.random() < split)
        # Should be ~200 ± 50
        assert 150 < candidate_count < 250

    def test_welch_t_test_borderline(self):
        """Borderline significance — small effect, moderate samples."""
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        # Small difference, moderate variance
        a = [0.82, 0.84, 0.81, 0.83, 0.85, 0.80, 0.84, 0.82, 0.83, 0.81]
        b = [0.78, 0.80, 0.77, 0.79, 0.81, 0.76, 0.80, 0.78, 0.79, 0.77]
        p = mgr._welch_t_test(a, b)
        # Should be significant with this clear separation
        assert p < 0.05


# ──────────────────────────────────────────────────────────────
# A/B Testing with Mocked DB (U21, U23-U27)
# ──────────────────────────────────────────────────────────────
class TestABTestManagerDB:
    """Test ABTestManager methods with mocked PostgreSQL."""

    def _make_manager(self):
        from training.ab_test import ABTestManager
        mgr = ABTestManager.__new__(ABTestManager)
        mgr.db_url = "postgresql://fake:fake@localhost/fake"
        return mgr

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_start_test_creates_row(self, mock_conn):
        """U21: start_test inserts a row and returns test_id."""
        mgr = self._make_manager()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [None, (42,)]  # No existing test, then return id
        mock_conn.return_value.cursor.return_value = mock_cur

        test_id = mgr.start_test("code_developer", "candidate:v1", "base:v1", 0.2, 100)
        assert test_id == 42
        # Verify INSERT was called
        assert mock_cur.execute.call_count == 2  # SELECT + INSERT

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_start_test_rejects_duplicate(self, mock_conn):
        """Starting a test when one is already active raises ValueError."""
        mgr = self._make_manager()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1,)  # Existing active test
        mock_conn.return_value.cursor.return_value = mock_cur

        with pytest.raises(ValueError, match="Active A/B test already exists"):
            mgr.start_test("code_developer", "candidate:v1", "base:v1")

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_route_model_no_test(self, mock_conn):
        """route_model returns default when no active test."""
        mgr = self._make_manager()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur

        result = mgr.route_model("code_developer", "qwen2.5-coder:14b")
        assert result == "qwen2.5-coder:14b"

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_route_model_with_test(self, mock_conn):
        """route_model routes to candidate or base based on random."""
        mgr = self._make_manager()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1, "candidate:v1", "base:v1", 0.5)
        mock_conn.return_value.cursor.return_value = mock_cur

        random.seed(42)
        results = [mgr.route_model("code_dev", "default") for _ in range(100)]
        candidate_count = results.count("candidate:v1")
        base_count = results.count("base:v1")
        # With 50/50 split, should be roughly even
        assert 30 < candidate_count < 70
        assert candidate_count + base_count == 100

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_route_model_db_failure_returns_default(self, mock_conn):
        """route_model gracefully returns default on DB error."""
        mgr = self._make_manager()
        mock_conn.side_effect = Exception("Connection refused")

        result = mgr.route_model("code_developer", "fallback_model")
        assert result == "fallback_model"

    @patch("training.ab_test.ABTestManager._get_conn")
    def test_record_result(self, mock_conn):
        """U23: record_result inserts into ab_test_results."""
        mgr = self._make_manager()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1,)  # Active test id
        mock_conn.return_value.cursor.return_value = mock_cur

        mgr.record_result("code_dev", "candidate:v1", 0.85, latency_ms=150)
        # Should have done SELECT + INSERT
        assert mock_cur.execute.call_count == 2


# ──────────────────────────────────────────────────────────────
# Trace Export Tests (U1-U4)
# ──────────────────────────────────────────────────────────────
class TestTraceExport:
    """Test Langfuse trace export logic."""

    def test_trace_to_trajectory_valid(self):
        """U1: Valid trace produces valid GRPO trajectory."""
        from training.export_traces import TraceExporter

        with patch.object(TraceExporter, "__init__", lambda self, **kw: None):
            exporter = TraceExporter()
            from training.reward_function import MarsRewardFunction
            exporter.reward_fn = MarsRewardFunction()

            trace = {
                "id": "trace-123",
                "input": "Write a function to sort a list",
                "metadata": {"template_id": "code_developer", "intent": "CODE"},
            }
            observations = [
                {
                    "type": "GENERATION",
                    "name": "solver",
                    "startTime": "2026-03-21T10:00:00Z",
                    "output": "def sort_list(lst): return sorted(lst)",
                },
            ]

            result = exporter.trace_to_grpo_trajectory(trace, observations)
            assert result is not None
            assert result["id"] == "trace-123"
            assert len(result["conversations"]) == 2  # user + assistant
            assert result["conversations"][0]["role"] == "user"
            assert result["conversations"][1]["role"] == "assistant"
            assert "correctness" in result["reward"]
            assert "efficiency" in result["reward"]
            assert "safety" in result["reward"]
            assert result["metadata"]["template_id"] == "code_developer"

    def test_trace_to_trajectory_no_input(self):
        """U4: Trace with no input is skipped."""
        from training.export_traces import TraceExporter

        with patch.object(TraceExporter, "__init__", lambda self, **kw: None):
            exporter = TraceExporter()
            from training.reward_function import MarsRewardFunction
            exporter.reward_fn = MarsRewardFunction()

            trace = {"id": "trace-empty", "input": None, "metadata": {}}
            result = exporter.trace_to_grpo_trajectory(trace, [])
            assert result is None

    def test_trace_to_trajectory_no_generations(self):
        """Trace with no generation observations is skipped."""
        from training.export_traces import TraceExporter

        with patch.object(TraceExporter, "__init__", lambda self, **kw: None):
            exporter = TraceExporter()
            from training.reward_function import MarsRewardFunction
            exporter.reward_fn = MarsRewardFunction()

            trace = {
                "id": "trace-no-gen",
                "input": "Do something",
                "metadata": {},
            }
            result = exporter.trace_to_grpo_trajectory(trace, [])
            assert result is None

    def test_extract_tool_calls(self):
        """Tool call extraction from assistant text."""
        from training.export_traces import TraceExporter

        with patch.object(TraceExporter, "__init__", lambda self, **kw: None):
            exporter = TraceExporter()

            text = 'I will read the file: {"name": "read_file", "arguments": {"path": "/etc/config"}}'
            calls = exporter._extract_tool_calls(text)
            assert len(calls) == 1
            assert calls[0]["name"] == "read_file"

    def test_extract_tool_calls_no_match(self):
        """No tool calls in plain text."""
        from training.export_traces import TraceExporter

        with patch.object(TraceExporter, "__init__", lambda self, **kw: None):
            exporter = TraceExporter()

            calls = exporter._extract_tool_calls("Just a plain response")
            assert calls == []


# ──────────────────────────────────────────────────────────────
# GRPO Trainer Config Tests (U13-U16)
# ──────────────────────────────────────────────────────────────
class TestGRPOTrainerConfig:
    """Test training config defaults and validation."""

    def test_default_config(self):
        """U13: Default config has correct values from config.py."""
        from training.grpo_trainer import GRPOTrainingConfig
        cfg = GRPOTrainingConfig()
        assert cfg.lora_rank == 16
        assert cfg.lora_alpha == 32
        assert cfg.batch_size == 1
        assert cfg.gradient_accumulation == 8
        assert cfg.learning_rate == pytest.approx(5e-6)
        assert cfg.num_epochs == 3
        assert cfg.max_seq_len == 4096
        assert cfg.warmup_ratio == 0.1
        assert cfg.group_size == 4
        assert cfg.kl_coeff == 0.05

    def test_custom_config(self):
        """Custom config overrides defaults."""
        from training.grpo_trainer import GRPOTrainingConfig
        cfg = GRPOTrainingConfig(
            base_model="test-model",
            lora_rank=32,
            batch_size=2,
            learning_rate=1e-5,
        )
        assert cfg.base_model == "test-model"
        assert cfg.lora_rank == 32
        assert cfg.batch_size == 2
        assert cfg.learning_rate == pytest.approx(1e-5)


# ──────────────────────────────────────────────────────────────
# Synthetic Generation Tests (U5-U8)
# ──────────────────────────────────────────────────────────────
class TestSyntheticGeneration:
    """Test synthetic trajectory generation structure."""

    def test_tool_definitions_present(self):
        """U7: All tool families present in TOOL_DEFINITIONS."""
        from training.synthetic_gen import TOOL_DEFINITIONS
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "read_file" in names
        assert "write_file" in names
        assert "run_command" in names
        assert "list_dir" in names

    def test_task_templates_exist(self):
        """Task templates for all domains exist."""
        from training.synthetic_gen import CODE_TASKS, FILE_TASKS, IOT_TASKS, RESEARCH_TASKS
        assert len(CODE_TASKS) > 0
        assert len(FILE_TASKS) > 0
        assert len(IOT_TASKS) > 0
        assert len(RESEARCH_TASKS) > 0


# ──────────────────────────────────────────────────────────────
# GPU Queue Training Tests (U28-U31)
# ──────────────────────────────────────────────────────────────
class TestGPUQueueTraining:
    """Test GPU queue training-related utilities."""

    @patch("utils.gpu_queue.datetime")
    def test_is_training_window_in_window(self, mock_dt):
        """U28: Hour 3 is inside 2-6 window."""
        from utils.gpu_queue import is_training_window
        mock_dt.now.return_value = datetime(2026, 3, 21, 3, 0, 0)
        assert is_training_window() is True

    @patch("utils.gpu_queue.datetime")
    def test_is_training_window_out_of_window(self, mock_dt):
        """U29: Hour 14 is outside 2-6 window."""
        from utils.gpu_queue import is_training_window
        mock_dt.now.return_value = datetime(2026, 3, 21, 14, 0, 0)
        assert is_training_window() is False

    @patch("utils.gpu_queue.datetime")
    def test_is_training_window_boundary_start(self, mock_dt):
        """Window boundary — start hour is inclusive."""
        from utils.gpu_queue import is_training_window
        mock_dt.now.return_value = datetime(2026, 3, 21, 2, 0, 0)
        assert is_training_window() is True

    @patch("utils.gpu_queue.datetime")
    def test_is_training_window_boundary_end(self, mock_dt):
        """Window boundary — end hour is exclusive."""
        from utils.gpu_queue import is_training_window
        mock_dt.now.return_value = datetime(2026, 3, 21, 6, 0, 0)
        # Default window is 2-6, hour 6 should be outside
        assert is_training_window() is False


# ──────────────────────────────────────────────────────────────
# RewardSignal dataclass
# ──────────────────────────────────────────────────────────────
class TestRewardSignal:
    """Test RewardSignal dataclass."""

    def test_reward_signal_creation(self):
        from training.reward_function import RewardSignal
        rs = RewardSignal(correctness=0.9, efficiency=0.5, safety=1.0, composite=0.78)
        assert rs.correctness == 0.9
        assert rs.efficiency == 0.5
        assert rs.safety == 1.0
        assert rs.composite == 0.78
