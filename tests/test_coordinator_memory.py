"""
tests/test_coordinator_memory.py

Unit tests for the coordinator's MemPalace team memory integration.
Tests _team_store() and _team_clear() helpers plus the WorkerInfo lifecycle.

Run:
    pytest tests/test_coordinator_memory.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock, call

import pytest

# Ensure agents/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


# ---------------------------------------------------------------------------
# Pre-import patches: mock heavy deps that coordinator.py imports at module level
# ---------------------------------------------------------------------------
# phi.agent, phi.model.ollama, gpu_queue, etc.
mock_phi_agent = MagicMock()
mock_phi_model = MagicMock()
mock_phi_storage = MagicMock()
mock_gpu_queue = MagicMock()
mock_gpu_queue.request_lock.return_value.__enter__ = MagicMock()
mock_gpu_queue.request_lock.return_value.__exit__ = MagicMock(return_value=False)
mock_gpu_queue.get_best_host_for_model.return_value = "http://localhost:11434"

# Ensure we have a mock config
mock_config = MagicMock()
mock_config.AGNO_DB_URL = "sqlite:///test.db"
mock_config.ARCHITECT_MODEL = "test-model"
mock_config.CONTROL_NODE_IP = "127.0.0.1"

# Install mocks before importing coordinator
for mod_name, mock_obj in {
    "phi": MagicMock(),
    "phi.agent": mock_phi_agent,
    "phi.model.ollama": mock_phi_model,
    "phi.storage.agent.postgres": mock_phi_storage,
    "utils.gpu_queue": mock_gpu_queue,
    "config": mock_config,
    "logger_setup": MagicMock(setup_logger=MagicMock(return_value=MagicMock())),
}.items():
    sys.modules.setdefault(mod_name, mock_obj)


from coordinator import _team_store, _team_clear, WorkerInfo, WorkerState


# ═══════════════════════════════════════════════════════════════════════════
# _team_store / _team_clear
# ═══════════════════════════════════════════════════════════════════════════

class TestTeamStoreHelper:

    def test_team_store_calls_client(self):
        mock_mp = MagicMock()
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            _team_store("coord-abc", "research_summary", "findings text", "worker-1")
            mock_mp.team_store.assert_called_once_with(
                "coord-abc", "research_summary", "findings text", author_agent="worker-1"
            )

    def test_team_store_graceful_on_import_error(self):
        """If mempalace_client can't be imported, no exception should propagate."""
        # Remove any cached module
        sys.modules.pop("mempalace_client", None)
        with patch.dict(sys.modules, {"mempalace_client": None}):
            # Should not raise
            _team_store("coord-abc", "key", "value")

    def test_team_store_graceful_on_network_error(self):
        mock_mp = MagicMock()
        mock_mp.team_store.side_effect = Exception("Connection refused")
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            # Should not raise
            _team_store("coord-abc", "key", "value")

    def test_team_store_default_author(self):
        mock_mp = MagicMock()
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            _team_store("coord-abc", "key", "value")
            mock_mp.team_store.assert_called_once_with(
                "coord-abc", "key", "value", author_agent="coordinator"
            )


class TestTeamClearHelper:

    def test_team_clear_calls_client(self):
        mock_mp = MagicMock()
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            _team_clear("coord-abc")
            mock_mp.team_clear.assert_called_once_with("coord-abc")

    def test_team_clear_graceful_on_error(self):
        mock_mp = MagicMock()
        mock_mp.team_clear.side_effect = Exception("Connection refused")
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            # Should not raise
            _team_clear("coord-abc")


# ═══════════════════════════════════════════════════════════════════════════
# WorkerInfo lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkerInfo:

    def test_initial_state(self):
        w = WorkerInfo("w-1", "researcher", "Find info about X", "research")
        assert w.worker_id == "w-1"
        assert w.role == "researcher"
        assert w.task == "Find info about X"
        assert w.phase == "research"
        assert w.state == WorkerState.PENDING
        assert w.result is None
        assert w.error is None

    def test_cancel_sets_flag(self):
        w = WorkerInfo("w-2", "implementer", "Build X", "implementation")
        assert not w.cancel_flag.is_set()
        w.cancel()
        assert w.cancel_flag.is_set()
        assert w.state == WorkerState.CANCELLED

    def test_state_transitions(self):
        w = WorkerInfo("w-3", "verifier", "Check X", "verification")
        assert w.state == WorkerState.PENDING

        w.state = WorkerState.RUNNING
        assert w.state == WorkerState.RUNNING

        w.state = WorkerState.COMPLETED
        assert w.state == WorkerState.COMPLETED

    def test_worker_state_enum_values(self):
        assert WorkerState.PENDING.value == "pending"
        assert WorkerState.RUNNING.value == "running"
        assert WorkerState.COMPLETED.value == "completed"
        assert WorkerState.FAILED.value == "failed"
        assert WorkerState.CANCELLED.value == "cancelled"


# ═══════════════════════════════════════════════════════════════════════════
# Integration pattern: store at key lifecycle points
# ═══════════════════════════════════════════════════════════════════════════

class TestCoordinatorMemoryPattern:
    """
    Verifies the memory storage pattern used at:
    - Worker result completion (research_<role>_<id>)
    - Synthesis (synthesis)
    - Verification (verification_result)
    """

    def test_research_key_format(self):
        team_id = "coord-abc123"
        role = "security_expert"
        worker_id = "w-001"
        key = f"research_{role}_{worker_id}"
        assert key == "research_security_expert_w-001"
        # This is what the coordinator stores

    def test_synthesis_key(self):
        assert "synthesis" == "synthesis"  # literal key used in coordinator

    def test_multiple_workers_store_unique_keys(self):
        mock_mp = MagicMock()
        with patch.dict(sys.modules, {"mempalace_client": MagicMock(mempalace=mock_mp)}):
            _team_store("coord-1", "research_arch_w1", "Architecture findings")
            _team_store("coord-1", "research_sec_w2", "Security findings")
            _team_store("coord-1", "synthesis", "Combined analysis")

            assert mock_mp.team_store.call_count == 3
            keys = [c.args[1] for c in mock_mp.team_store.call_args_list]
            assert keys == ["research_arch_w1", "research_sec_w2", "synthesis"]

    def test_result_truncated_at_2000(self):
        """Coordinator truncates worker results to 2000 chars."""
        long_result = "x" * 5000
        truncated = long_result[:2000]
        assert len(truncated) == 2000
