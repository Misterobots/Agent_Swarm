"""
tests/test_frameworks.py

Unit tests for the framework layer: catalogue integrity, collision geometry,
assignment invariants, compliance auditing, and emergent-framework admission.

No live model calls — structured_llm_call is patched throughout.

Run:
    pytest tests/test_frameworks.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

# ollama/phi are not installed in every dev environment; stub before import.
for _mod, _mock in {
    "ollama": MagicMock(),
    "phi": MagicMock(),
    "phi.agent": MagicMock(),
    "phi.model.ollama": MagicMock(),
    "config": MagicMock(COORDINATOR_MODEL="test-model", CONTEXT_WINDOWS={}),
    "utils.gpu_queue": MagicMock(get_swarm_worker_host=MagicMock(return_value="http://localhost:11434")),
    "logger_setup": MagicMock(setup_logger=MagicMock(return_value=MagicMock())),
}.items():
    sys.modules.setdefault(_mod, _mock)

from coordination import frameworks as fw


REQUIRED_FIELDS = (
    "name", "family", "summary", "moves", "mandates",
    "prohibitions", "output_contract", "affinity",
)


# ---------------------------------------------------------------------------
# Catalogue integrity
# ---------------------------------------------------------------------------

class TestCatalogueIntegrity:

    @pytest.mark.unit
    def test_every_framework_has_required_fields(self):
        for fid, spec in fw.FRAMEWORKS.items():
            for field in REQUIRED_FIELDS:
                assert field in spec, f"{fid} missing '{field}'"

    @pytest.mark.unit
    def test_families_are_declared(self):
        for fid, spec in fw.FRAMEWORKS.items():
            assert spec["family"] in fw.FRAMEWORK_FAMILIES, f"{fid} has unknown family"

    @pytest.mark.unit
    def test_every_framework_is_checkable(self):
        """The whole premise is that a framework can be audited — a framework with
        no output contract and no mandates is just a persona wearing a label."""
        for fid, spec in fw.FRAMEWORKS.items():
            assert spec["output_contract"], f"{fid} has no output contract"
            assert spec["mandates"] or spec["prohibitions"], f"{fid} is unauditable"

    @pytest.mark.unit
    def test_min_counts_reference_contracted_keys(self):
        for fid, spec in fw.FRAMEWORKS.items():
            for key in spec.get("min_counts", {}):
                assert key in spec["output_contract"], f"{fid}: min_counts '{key}' not in contract"

    @pytest.mark.unit
    def test_families_are_populated(self):
        present = {spec["family"] for spec in fw.FRAMEWORKS.values()}
        assert present == set(fw.FRAMEWORK_FAMILIES), f"families missing: {set(fw.FRAMEWORK_FAMILIES) - present}"

    @pytest.mark.unit
    def test_catalogue_is_large_enough_for_diverse_assignment(self):
        # 6 debating agents need 6 distinct primaries across >=3 families.
        assert len(fw.FRAMEWORKS) >= 12
        assert len({s["family"] for s in fw.FRAMEWORKS.values()}) >= 3


# ---------------------------------------------------------------------------
# Collision geometry
# ---------------------------------------------------------------------------

class TestCollisionGeometry:

    @pytest.mark.unit
    def test_identical_frameworks_cannot_collide(self):
        assert fw.collision_score("falsification", "falsification") < 0

    @pytest.mark.unit
    def test_unknown_framework_scores_below_known_pair(self):
        assert fw.collision_score("falsification", "not_a_framework") < \
               fw.collision_score("falsification", "reframe")

    @pytest.mark.unit
    def test_same_family_friction_is_lower_than_cross_family(self):
        same = fw.collision_score("falsification", "premortem")        # both critical
        cross = fw.collision_score("falsification", "first_principles")  # critical x structural
        assert cross > same

    @pytest.mark.unit
    def test_critical_generative_is_the_hardest_collision(self):
        assert fw.collision_score("falsification", "reframe") >= \
               fw.collision_score("first_principles", "systems_feedback")

    @pytest.mark.unit
    def test_partner_selection_skips_self_and_picks_max(self):
        ids = ["falsification", "veil_of_ignorance", "first_principles"]
        # falsification (critical) should be matched with the adjudicative one
        assert fw.most_contested_partner(0, ids) == 1

    @pytest.mark.unit
    def test_partner_returns_none_for_a_solo_agent(self):
        assert fw.most_contested_partner(0, ["falsification"]) is None


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------

class TestPromptBlock:

    @pytest.mark.unit
    def test_block_carries_the_constraint_not_a_description(self):
        block = fw.framework_prompt_block("falsification")
        assert "LICENSED MOVES" in block
        assert "MANDATES" in block
        assert "refutation_tests" in block          # output contract surfaced
        assert "falsified" in block

    @pytest.mark.unit
    def test_secondary_is_marked_subordinate(self):
        block = fw.framework_prompt_block("falsification", secondary_id="reframe")
        assert "SECONDARY FRAMEWORK" in block
        assert "does not conflict with the primary" in block

    @pytest.mark.unit
    def test_unknown_framework_yields_no_block(self):
        assert fw.framework_prompt_block("nonexistent") == ""


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

PERSP = [
    {"label": "Technical Analysis", "role": "technical"},
    {"label": "Ethical Analysis", "role": "ethical"},
    {"label": "Economic Analysis", "role": "economic"},
]


class TestAssignment:

    @pytest.mark.unit
    def test_prefilter_is_family_capped(self):
        short = fw.prefilter_frameworks(["technical", "ethical"], limit=8)
        families = [fw.FRAMEWORKS[f]["family"] for f in short]
        assert len(short) <= 8
        for fam in set(families):
            assert families.count(fam) <= 2 or len(fw.FRAMEWORK_FAMILIES) < 3

    @pytest.mark.unit
    def test_validate_rejects_duplicate_primaries(self):
        bad = [{"primary": "falsification"}, {"primary": "falsification"},
               {"primary": "reframe"}]
        assert "duplicate primary frameworks" in fw.validate_assignment(bad)

    @pytest.mark.unit
    def test_validate_rejects_single_family_room(self):
        bad = [{"primary": "falsification"}, {"primary": "premortem"},
               {"primary": "logical_consistency"}]
        assert any("families" in p for p in fw.validate_assignment(bad))

    @pytest.mark.unit
    def test_validate_rejects_room_without_an_attacker(self):
        bad = [{"primary": "first_principles"}, {"primary": "reframe"},
               {"primary": "veil_of_ignorance"}]
        assert any("critical" in p for p in fw.validate_assignment(bad))

    @pytest.mark.unit
    def test_validate_rejects_unknown_ids(self):
        bad = [{"primary": "invented"}, {"primary": "also_invented"},
               {"primary": "falsification"}]
        assert any("unknown framework" in p for p in fw.validate_assignment(bad))

    @pytest.mark.unit
    def test_a_diverse_room_passes(self):
        good = [{"primary": "falsification"}, {"primary": "first_principles"},
                {"primary": "veil_of_ignorance"}]
        assert fw.validate_assignment(good) == []

    @pytest.mark.unit
    def test_llm_result_is_used_when_valid(self):
        payload = {"assignments": [
            {"index": 0, "primary": "falsification", "secondary": "reframe", "rationale": "x"},
            {"index": 1, "primary": "veil_of_ignorance", "secondary": "", "rationale": "y"},
            {"index": 2, "primary": "first_principles", "secondary": "premortem", "rationale": "z"},
        ]}
        with patch.object(fw, "structured_llm_call", return_value=payload):
            out = fw.assign_frameworks(PERSP, problem_type="policy")
        assert [a["primary"] for a in out] == ["falsification", "veil_of_ignorance", "first_principles"]
        assert all(a["primary_name"] for a in out)

    @pytest.mark.unit
    def test_model_outage_still_produces_a_valid_diverse_room(self):
        """Assignment must never abort a run and never silently collapse diversity."""
        with patch.object(fw, "structured_llm_call", return_value=None):
            out = fw.assign_frameworks(PERSP, problem_type="policy")
        assert len(out) == len(PERSP)
        assert fw.validate_assignment(out) == []

    @pytest.mark.unit
    def test_rule_violating_llm_output_is_discarded(self):
        bad = {"assignments": [
            {"index": 0, "primary": "falsification", "secondary": "", "rationale": "x"},
            {"index": 1, "primary": "falsification", "secondary": "", "rationale": "y"},
            {"index": 2, "primary": "premortem", "secondary": "", "rationale": "z"},
        ]}
        with patch.object(fw, "structured_llm_call", return_value=bad):
            out = fw.assign_frameworks(PERSP)
        assert fw.validate_assignment(out) == []
        assert len({a["primary"] for a in out}) == 3

    @pytest.mark.unit
    def test_partial_llm_output_falls_back(self):
        partial = {"assignments": [{"index": 0, "primary": "falsification",
                                   "secondary": "", "rationale": "x"}]}
        with patch.object(fw, "structured_llm_call", return_value=partial):
            out = fw.assign_frameworks(PERSP)
        assert len(out) == 3
        assert fw.validate_assignment(out) == []

    @pytest.mark.unit
    def test_empty_roster_is_not_an_error(self):
        assert fw.assign_frameworks([]) == []


# ---------------------------------------------------------------------------
# Compliance audit
# ---------------------------------------------------------------------------

class TestAudit:

    @pytest.mark.unit
    def test_missing_contract_key_is_caught_without_an_llm(self):
        with patch.object(fw, "structured_llm_call") as call:
            result = fw.audit_turn("falsification", {"claims": ["a"]})
        assert result["compliant"] is False
        assert any("refutation_tests" in v for v in result["violations"])
        call.assert_not_called()

    @pytest.mark.unit
    def test_min_counts_threshold_is_enforced(self):
        payload = {
            "claims": ["a"], "refutation_tests": ["t1"], "survived": ["a"],
            "falsified": [],   # falsification requires >=1
        }
        violations = fw.check_contract("falsification", payload)
        assert any("falsified" in v for v in violations)

    @pytest.mark.unit
    def test_unparseable_turn_is_a_violation(self):
        assert fw.check_contract("falsification", None) == ["no parsed output to audit"]

    @pytest.mark.unit
    def test_contract_pass_then_llm_names_a_mandate_gap(self):
        payload = {
            "claims": ["a"], "refutation_tests": ["t1"],
            "survived": ["a"], "falsified": ["b"],
        }
        with patch.object(fw, "structured_llm_call",
                          return_value={"compliant": False, "violations": ["mandate 2 skipped"]}):
            result = fw.audit_turn("falsification", payload)
        assert result["compliant"] is False
        assert result["audited_by"] == "contract+llm"
        assert "mandate 2 skipped" in result["violations"]

    @pytest.mark.unit
    def test_compliant_turn_passes_both_stages(self):
        payload = {
            "claims": ["a"], "refutation_tests": ["t1"],
            "survived": ["a"], "falsified": ["b"],
        }
        with patch.object(fw, "structured_llm_call",
                          return_value={"compliant": True, "violations": []}):
            assert fw.audit_turn("falsification", payload)["compliant"] is True

    @pytest.mark.unit
    def test_auditor_being_unavailable_does_not_block_the_debate(self):
        """Process audit is best-effort: a dead model must not fail a valid turn."""
        payload = {
            "claims": ["a"], "refutation_tests": ["t1"],
            "survived": ["a"], "falsified": ["b"],
        }
        with patch.object(fw, "structured_llm_call", return_value=None):
            result = fw.audit_turn("falsification", payload)
        assert result["compliant"] is True
        assert "unavailable" in result["audited_by"]


# ---------------------------------------------------------------------------
# Emergence
# ---------------------------------------------------------------------------

TWO_AGENT_TRANSCRIPTS = [
    {"agent": "Feynman", "framework": "falsification", "text": "we cross-checked the refutation"},
    {"agent": "Norman", "framework": "reframe", "text": "then we cross-checked the refutation"},
]

QUALIFIED = {
    "found": True,
    "name": "Reciprocal Refutation",
    "family": "critical",
    "summary": "Each agent states the refutation condition for the other's claim.",
    "moves": ["cross-audit the opposing agent's refutation condition before defending your own"],
    "observed_in_agents": ["Feynman", "Norman"],
    "evidence_spans": ["we cross-checked the refutation"],
    "parent_frameworks": ["falsification", "reframe"],
    "drove_concession": True,
}
CONCESSIONS = [{"by": "Norman", "relinquished": "x", "conceded_to": "Feynman", "move": "cross-audit"}]


class TestEmergence:

    @pytest.mark.unit
    def test_subsumed_candidate_moves_are_detected_free_of_charge(self):
        parents = ["falsification"]
        parent_moves = fw.FRAMEWORKS["falsification"]["moves"]
        fully, residual = fw.subsumed(parent_moves[:2], parents)
        assert fully is True
        assert residual == []

    @pytest.mark.unit
    def test_novel_move_survives_the_subsumption_filter(self):
        _, residual = fw.subsumed(
            ["cross-audit the opposing agent's refutation condition before replying"],
            ["falsification", "reframe"],
        )
        assert residual

    @pytest.mark.unit
    def test_a_single_voice_cannot_produce_emergence(self):
        with patch.object(fw, "structured_llm_call") as call:
            assert fw.detect_emergent_framework(
                [{"agent": "A", "framework": "falsification", "text": "x"}],
                ["falsification"], CONCESSIONS) is None
        call.assert_not_called()

    @pytest.mark.unit
    def test_found_false_is_not_an_emergent_framework(self, tmp_path):
        with patch.object(fw, "structured_llm_call", return_value={"found": False}), \
             patch.object(fw, "EMERGENT_CATALOGUE_PATH", tmp_path / "led.json"):
            assert fw.detect_emergent_framework(
                TWO_AGENT_TRANSCRIPTS, ["falsification", "reframe"], CONCESSIONS) is None
        assert not (tmp_path / "led.json").exists()

    @pytest.mark.unit
    def test_not_load_bearing_is_rejected(self, tmp_path):
        weak = {**QUALIFIED, "drove_concession": False}
        with patch.object(fw, "structured_llm_call", return_value=weak), \
             patch.object(fw, "EMERGENT_CATALOGUE_PATH", tmp_path / "led.json"):
            assert fw.detect_emergent_framework(
                TWO_AGENT_TRANSCRIPTS, ["falsification", "reframe"], CONCESSIONS) is None

    @pytest.mark.unit
    def test_only_one_observed_agent_is_rejected(self, tmp_path):
        thin = {**QUALIFIED, "observed_in_agents": ["Feynman"]}
        with patch.object(fw, "structured_llm_call", return_value=thin), \
             patch.object(fw, "EMERGENT_CATALOGUE_PATH", tmp_path / "led.json"):
            assert fw.detect_emergent_framework(
                TWO_AGENT_TRANSCRIPTS, ["falsification", "reframe"], CONCESSIONS) is None

    @pytest.mark.unit
    def test_move_that_is_just_the_parents_rejected(self, tmp_path):
        borrowed = {**QUALIFIED,
                    "moves": list(fw.FRAMEWORKS["falsification"]["moves"][:2])}
        with patch.object(fw, "structured_llm_call", return_value=borrowed), \
             patch.object(fw, "EMERGENT_CATALOGUE_PATH", tmp_path / "led.json"):
            assert fw.detect_emergent_framework(
                TWO_AGENT_TRANSCRIPTS, ["falsification", "reframe"], CONCESSIONS) is None

    @pytest.mark.unit
    def test_qualified_candidate_is_recorded_as_candidate_not_assignable(self, tmp_path):
        ledger = tmp_path / "led.json"
        with patch.object(fw, "structured_llm_call", return_value=QUALIFIED), \
             patch.object(fw, "EMERGENT_CATALOGUE_PATH", ledger):
            spec = fw.detect_emergent_framework(
                TWO_AGENT_TRANSCRIPTS, ["falsification", "reframe"],
                CONCESSIONS, coordination_id="coord-x")
        assert spec and spec["status"] == "candidate"
        assert spec["parents"] == ["falsification", "reframe"]
        assert spec["first_seen_run"] == "coord-x"
        assert ledger.exists()
        # A candidate must not be selectable yet.
        assert spec["id"] not in fw.load_catalogue(path=ledger)

    @pytest.mark.unit
    def test_candidate_becomes_assignable_only_after_it_bites(self, tmp_path):
        ledger = tmp_path / "led.json"
        fw.save_emergent_framework(
            {"id": "reciprocal_refutation", "name": "Reciprocal Refutation",
             "moves": ["cross-audit the opposing claim"], "output_contract": ["claims"],
             "status": "candidate"}, path=ledger)
        assert "reciprocal_refutation" not in fw.load_catalogue(path=ledger)

        fw.record_candidate_application("reciprocal_refutation", False, path=ledger)
        assert "reciprocal_refutation" not in fw.load_catalogue(path=ledger)

        fw.record_candidate_application("reciprocal_refutation", True, path=ledger)
        assert "reciprocal_refutation" in fw.load_catalogue(path=ledger)

    @pytest.mark.unit
    def test_missing_ledger_is_not_an_error(self, tmp_path):
        assert fw.load_emergent(tmp_path / "nope.json") == []

    @pytest.mark.unit
    def test_corrupt_ledger_degrades_to_empty(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert fw.load_emergent(bad) == []

    @pytest.mark.unit
    def test_upsert_is_idempotent_by_id(self, tmp_path):
        ledger = tmp_path / "led.json"
        fw.save_emergent_framework({"id": "alpha", "name": "A"}, path=ledger)
        fw.save_emergent_framework({"id": "alpha", "name": "A2", "status": "validated"}, path=ledger)
        entries = fw.load_emergent(ledger)
        assert len(entries) == 1
        assert entries[0]["name"] == "A2" and entries[0]["status"] == "validated"
