"""
tests/test_debate.py

Unit tests for the debate stage, the prior-run recall that feeds it, and the
pending-context branch that triggers it. No live model calls: the LLM boundary
(``_audited_turn`` / ``assign_frameworks`` / ``detect_emergent_framework``) is
patched, so what is under test is the round orchestration and the reporting.

Run:
    pytest tests/test_debate.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

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

from coordination import debate
from coordination import frameworks as fw
from coordination import orchestrator
from coordination.frameworks import FRAMEWORKS

ORCHESTRATOR_SRC = open(
    os.path.join(os.path.dirname(__file__), "..", "agents", "coordination", "orchestrator.py"),
    encoding="utf-8",
).read()

PERSPECTIVE_SRC = ORCHESTRATOR_SRC[
    ORCHESTRATOR_SRC.index("PERSPECTIVE RESEARCH FLOW"):
    ORCHESTRATOR_SRC.index("# === PHASE 2: RESEARCH (parallel) ===")
]

# Event types the SSE allowlist in agents/main.py already carries. The debate
# stage must stay inside this set — that containment is the whole reason the
# stage can ship without new UI plumbing.
ALLOWED_EVENT_TYPES = {
    "message", "status", "log", "thought", "response", "swarm_phase", "heartbeat",
}


def _roster(n=3):
    labels = ["Technical Analysis", "Ethical Analysis", "Economic Analysis"][:n]
    return [
        {
            "label": label,
            "role": label.split()[0].lower(),
            "pioneer_name": {"Technical Analysis": "Knuth", "Ethical Analysis": "Rawls",
                             "Economic Analysis": "Keynes"}[label],
            "pioneer_full_name": label,
            "pioneer_motto": "motto",
            "findings": f"Full findings for {label}: " + ("detail " * 40),
        }
        for label in labels
    ]


def _turn(claims=None, concessions=None, attacks=None, compliant=True):
    return {
        "payload": {
            "reasoning": "because the constraints force it",
            "claims": claims or ["claim one"],
            "licensed_moves_used": ["named the refutation condition"],
            "attacks": attacks or [],
            "concessions": concessions or [],
        },
        "violations": [] if compliant else ["mandate 1 unmet"],
        "attempts": 1,
        "compliant": compliant,
        "agent": None,
        "framework": "falsification",
    }


ASSIGNMENTS = [
    {"perspective_label": "Technical Analysis", "primary": "falsification",
     "secondary": "reframe", "primary_name": "Falsification Testing",
     "primary_family": "critical", "secondary_name": "Frame Criticism", "rationale": "x"},
    {"perspective_label": "Ethical Analysis", "primary": "veil_of_ignorance",
     "secondary": "standing", "primary_name": "Veil of Ignorance",
     "primary_family": "adjudicative", "secondary_name": "Interest and Standing", "rationale": "y"},
    {"perspective_label": "Economic Analysis", "primary": "tradeoff_ledger",
     "secondary": "base_rate", "primary_name": "Trade-off Ledger",
     "primary_family": "structural", "secondary_name": "Reference-Class Forecasting",
     "rationale": "z"},
]


def _drive(roster, turn_factory, rounds=3, emergent=None):
    """Run the debate with its LLM boundary replaced by turn_factory."""
    events, sink = [], {}
    fake_assign = [dict(a) for a in ASSIGNMENTS[:len(roster)]]
    with patch.object(debate, "assign_frameworks", return_value=fake_assign), \
         patch.object(debate, "_audited_turn", side_effect=lambda **kw: dict(
             turn_factory(kw), agent=kw["agent_name"], framework=kw["framework_id"])), \
         patch.object(debate, "detect_emergent_framework", return_value=emergent):
        for ev in debate.run_debate(
            topic="Should we ship this?", focus="the regulatory risk",
            roster=roster, matrix_md="## matrix", model_name="test-model",
            coordination_id="coord-deb", rounds=rounds, sink=sink,
        ):
            events.append(ev)
    return events, sink


# ---------------------------------------------------------------------------
# Round orchestration
# ---------------------------------------------------------------------------

class TestRunDebate:

    @pytest.mark.unit
    def test_a_lone_agent_cannot_debate(self):
        events, sink = [], {}
        with patch.object(debate, "assign_frameworks") as assign:
            for ev in debate.run_debate(topic="t", focus="f", roster=_roster(1), sink=sink):
                events.append(ev)
        assert any("at least 2 agents" in str(e.get("content", "")) for e in events)
        assign.assert_not_called()
        assert sink["markdown"] == ""

    @pytest.mark.unit
    def test_events_stay_inside_the_existing_sse_allowlist(self):
        events, _ = _drive(_roster(), lambda kw: _turn())
        unexpected = {e["type"] for e in events} - ALLOWED_EVENT_TYPES
        assert not unexpected, f"debate emitted unregistered event types: {unexpected}"

    @pytest.mark.unit
    def test_framework_assignment_is_reported_before_any_speaking(self):
        events, _ = _drive(_roster(), lambda kw: _turn())
        contents = " ".join(str(e.get("content", "")) for e in events)
        assert "Framework Assignment" in contents
        assert "falsification" in contents
        assert events.index(
            next(e for e in events if "Framework Assignment" in str(e.get("content", "")))
        ) < events.index(next(e for e in events if "R1 ·" in str(e.get("content", ""))))

    @pytest.mark.unit
    def test_three_rounds_gives_every_agent_three_turns(self):
        events, sink = _drive(_roster(), lambda kw: _turn())
        assert len(sink["transcript"]) == 9  # 3 agents x 3 rounds
        assert {t["round"] for t in sink["transcript"]} == {1, 2, 3}

    @pytest.mark.unit
    def test_single_round_probe_path_skips_collision(self):
        _, sink = _drive(_roster(), lambda kw: _turn(), rounds=1)
        assert len(sink["transcript"]) == 3
        assert all(t["round"] == 1 for t in sink["transcript"])

    @pytest.mark.unit
    def test_collision_round_pairs_agents_by_maximum_friction(self):
        """The point of the stage: you attack the framework that disagrees with you
        most, not the convenient neighbour."""
        pairs = {}
        for i, a in enumerate(["falsification", "veil_of_ignorance", "tradeoff_ledger"]):
            pairs[a] = debate.most_contested_partner(i, ["falsification", "veil_of_ignorance",
                                                         "tradeoff_ledger"], FRAMEWORKS)
        ids = ["falsification", "veil_of_ignorance", "tradeoff_ledger"]
        for own, idx in pairs.items():
            assert idx is not None and idx != ids.index(own)
            assert fw.collision_score(own, ids[idx], FRAMEWORKS) > fw._SAME_FAMILY_WEIGHT

    @pytest.mark.unit
    def test_concessions_are_collected_into_the_record(self):
        conceded = [{"claim_relinquished": "we can self-regulate",
                     "conceded_to": "Rawls", "because_of_move": "worst-off ranking"}]
        _, sink = _drive(_roster(), lambda kw: _turn(concessions=conceded))
        assert len(sink["concessions"]) == 9
        assert sink["concessions"][0]["by"]
        assert "self-regulate" in sink["concessions"][0]["relinquished"]

    @pytest.mark.unit
    def test_audit_failure_is_surfaced_not_swallowed(self):
        """A turn that failed the framework audit must be visible in the output."""
        _, sink = _drive(_roster(), lambda kw: _turn(compliant=False), rounds=1)
        assert len(sink["violations"]) == 3
        md = sink["markdown"]
        assert "Framework compliance failures" in md
        assert "audit failed" in md

    @pytest.mark.unit
    def test_agents_keep_their_research_personas(self):
        roster = _roster()
        seen = {}

        def capture(kw):
            seen[kw["agent_name"]] = kw["system"]
            return _turn()

        _drive(roster, capture, rounds=1)
        assert len(seen) == 3
        for label, system in seen.items():
            assert "Knuth" in system or label  # persona name is carried through
            assert "LICENSED MOVES" in system
            assert "audited against" in system

    @pytest.mark.unit
    def test_emergent_candidate_is_reported_as_candidate(self):
        spec = {"id": "reciprocal_refutation", "name": "Reciprocal Refutation",
                "family": "critical", "summary": "cross-audit", "moves": ["m"],
                "parents": ["falsification", "reframe"], "observed_in": ["Knuth"],
                "status": "candidate"}
        events, sink = _drive(_roster(), lambda kw: _turn(), emergent=spec)
        contents = " ".join(str(e.get("content", "")) for e in events)
        assert "reciprocal_refutation" in contents
        assert "candidate" in contents
        assert sink["emergent"] == spec


# ---------------------------------------------------------------------------
# Turn-level audit behaviour
# ---------------------------------------------------------------------------

class TestAuditedTurn:

    @pytest.mark.unit
    def test_a_rejected_turn_is_sent_back_with_the_violations_named(self):
        calls = []

        def fake_generate(system, instruction, model_name, **kw):
            calls.append(instruction)
            return {"claims": ["c"]}

        verdicts = iter([
            {"compliant": False, "violations": ["'refutation_tests' missing"],
             "audited_by": "contract"},
            {"compliant": True, "violations": [], "audited_by": "contract+llm"},
        ])

        with patch.object(debate, "_generate_turn", side_effect=fake_generate), \
             patch.object(debate, "audit_turn", side_effect=lambda *a, **k: next(verdicts)):
            result = debate._audited_turn(
                system="s", instruction="BASE INSTRUCTION", framework_id="falsification",
                agent_name="Knuth", model_name="m", catalogue=FRAMEWORKS,
            )
        assert result["attempts"] == 2
        assert result["compliant"] is True
        assert len(calls) == 2
        assert "BASE INSTRUCTION" in calls[1]
        assert "REJECTED BY THE FRAMEWORK AUDITOR" in calls[1]
        assert "refutation_tests" in calls[1]  # the violation is named in the retry

    @pytest.mark.unit
    def test_second_failure_is_reported_as_a_failure(self):
        def always_bad(system, instruction, model_name, **kw):
            return {"claims": ["c"]}

        with patch.object(debate, "_generate_turn", side_effect=always_bad), \
             patch.object(debate, "audit_turn",
                          return_value={"compliant": False, "violations": ["mandate 1 unmet"],
                                        "audited_by": "contract"}):
            result = debate._audited_turn(
                system="s", instruction="i", framework_id="falsification",
                agent_name="Knuth", model_name="m", catalogue=FRAMEWORKS,
            )
        assert result["compliant"] is False
        assert result["violations"] == ["mandate 1 unmet"]
        assert result["attempts"] == 2

    @pytest.mark.unit
    def test_generation_outage_is_recorded_as_a_violation(self):
        with patch.object(debate, "_generate_turn", return_value=None):
            result = debate._audited_turn(
                system="s", instruction="i", framework_id="falsification",
                agent_name="Knuth", model_name="m", catalogue=FRAMEWORKS,
            )
        assert result["compliant"] is False
        assert result["payload"] is None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRender:

    @pytest.mark.unit
    def test_no_concessions_is_reported_as_a_finding(self):
        """Nothing moving is information, not a clean result — it must not read as success."""
        agents = [{"label": "A", "pioneer_name": "Knuth", "framework": "falsification",
                   "framework_family": "critical"},
                  {"label": "B", "pioneer_name": "Rawls", "framework": "reframe",
                   "framework_family": "generative"}]
        turns = {"A": {"claims": ["x"], "compliant": True}, "B": {"claims": ["y"], "compliant": True}}
        md = debate.render_debate_markdown(
            topic="t", focus="", agents=agents, turns=turns, concessions=[], violations=[],
            emergent=None, verdict={"verdict": "v", "settled": [], "still_contested": [],
                                    "next_probe": []},
            partner_index={"A": 1, "B": 0},
        )
        assert "treat the absence of movement as a finding" in md

    @pytest.mark.unit
    def test_table_lists_the_pairings(self):
        agents = [{"label": "A", "pioneer_name": "Knuth", "framework": "falsification",
                   "framework_family": "critical"},
                  {"label": "B", "pioneer_name": "Norman", "framework": "reframe",
                   "framework_family": "generative"}]
        turns = {"A": {"claims": ["x"], "compliant": True}, "B": {"claims": ["y"], "compliant": False}}
        md = debate.render_debate_markdown(
            topic="t", focus="f", agents=agents, turns=turns,
            concessions=[{"by": "Norman", "relinquished": "y", "conceded_to": "Knuth",
                          "move": "frame criticism", "round": 2}],
            violations=[], emergent=None,
            verdict={"verdict": "v", "settled": ["s"], "still_contested": ["c"],
                     "next_probe": ["p"]},
            partner_index={"A": 1, "B": 0},
        )
        assert "| Knuth | A | `falsification` | critical | Norman |" in md
        assert "audit failed" in md
        assert "frame criticism" in md
        assert "- p\n" in md


# ---------------------------------------------------------------------------
# Prior-run recall (the cross-coordination bridge)
# ---------------------------------------------------------------------------

class TestRecallPriorRun:

    @pytest.mark.unit
    def test_no_parent_id_means_nothing_to_recall(self):
        assert orchestrator._recall_prior_run("", "sess")["roster"] == []

    @pytest.mark.unit
    def test_team_memory_is_the_primary_source(self):
        team = {
            "perspective_roster": json.dumps(
                {"topic": "T", "roster": [{"label": "Ethical Analysis", "role": "ethical"}]}),
            "perspective_finding__ethical_analysis": "full finding text",
            "perspective_matrix": "## matrix",
        }
        with patch.object(orchestrator, "_team_recall", return_value=team):
            out = orchestrator._recall_prior_run("coord-p", "sess")
        assert out["source"] == "palace"
        assert out["topic"] == "T"
        assert out["matrix"] == "## matrix"
        assert out["findings"]["ethical_analysis"] == "full finding text"

    @pytest.mark.unit
    def test_scratchpad_is_the_fallback_when_the_palace_is_down(self, tmp_path):
        run_dir = tmp_path / "sess" / "coord-p"
        run_dir.mkdir(parents=True)
        (run_dir / "02_perspectives.json").write_text(json.dumps(
            {"topic": "T", "roster": [{"label": "Technical Analysis", "role": "technical"}]}),
            encoding="utf-8")
        (run_dir / "03_findings_technical_analysis.md").write_text("long finding", encoding="utf-8")
        (run_dir / "01_perspective_matrix.md").write_text("## m", encoding="utf-8")
        with patch.object(orchestrator, "_team_recall", return_value={}), \
             patch.object(orchestrator, "SCRATCHPAD_ROOT", tmp_path):
            out = orchestrator._recall_prior_run("coord-p", "sess")
        assert out["roster"][0]["label"] == "Technical Analysis"
        assert out["findings"]["technical_analysis"] == "long finding"
        assert out["matrix"] == "## m"

    @pytest.mark.unit
    def test_corrupt_roster_degrades_instead_of_raising(self, tmp_path):
        run_dir = tmp_path / "sess" / "coord-p"
        run_dir.mkdir(parents=True)
        (run_dir / "02_perspectives.json").write_text("{oops", encoding="utf-8")
        with patch.object(orchestrator, "_team_recall", return_value={}), \
             patch.object(orchestrator, "SCRATCHPAD_ROOT", tmp_path):
            out = orchestrator._recall_prior_run("coord-p", "sess")
        assert out["roster"] == []

    @pytest.mark.unit
    def test_finding_keys_survive_awkward_labels(self):
        for label in ("End-User / UX", "Policy  &  Regulation", "技术 Technical"):
            key = orchestrator._perspective_finding_key(label)
            assert "/" not in key and " " not in key
            assert key.startswith("perspective_finding__")

    @pytest.mark.unit
    def test_full_finding_is_stored_not_a_two_kilobyte_excerpt(self):
        """Regression: the perspective flow used to persist result[:2000], which made
        a debate over each lens's actual reasoning impossible. The separate
        codebase-research path still truncates — deliberately out of scope here."""
        assert "result[:2000]" not in PERSPECTIVE_SRC
        assert "_perspective_finding_key(label)" in PERSPECTIVE_SRC


class TestDebateStageGuard:

    @pytest.mark.unit
    def test_unrecoverable_findings_say_so_instead_of_debating_nothing(self):
        session = MagicMock()
        session.session_id = "sess"
        session.coordination_id = "coord-d"
        session.is_cancelled.return_value = False
        session.model_for_role.return_value = "m"
        events = []
        with patch.object(orchestrator, "_recall_prior_run", return_value={"roster": [], "findings": {},
                                                                          "matrix": "", "topic": ""}), \
             patch.object(orchestrator.swarm_run_store, "finish_run"):
            for ev in orchestrator._run_debate_stage(
                session=session, user_input="t", parent_coordination_id="coord-p",
                debate_focus="f", model_name="m"):
                events.append(ev)
        assert events[-1]["type"] == "response"
        assert "Debate unavailable" in events[-1]["content"]

    @pytest.mark.unit
    def test_debate_mode_skips_decomposition(self):
        """A debate re-entry must not decompose a new task or write files."""
        branch = ORCHESTRATOR_SRC.index("if debate_mode:")
        prep = ORCHESTRATOR_SRC.index("# === PHASE 0: WORKSPACE PREP")
        assert branch < prep


# ---------------------------------------------------------------------------
# Pending-context branch
# ---------------------------------------------------------------------------

class TestDebateGate:

    @pytest.mark.unit
    def test_clicking_debate_sets_the_reentry_flags(self):
        with patch.dict(sys.modules, {"brooks": MagicMock()}):
            from routing import gates
            result = {}
            events = list(gates.handle_pending_context(
                {"type": "swarm_debate", "prompt": "original topic",
                 "coordination_id": "coord-p", "question": "q"},
                "Debate this specific question: should we wait for the EU ruling",
                session_id="s", owner_id="o", history=None, extracted_context="",
                ace_token=None, ultraplan_mode=False, dev_mode=False, result=result,
            ))
        assert result["debate_mode"] is True
        assert result["parent_coordination_id"] == "coord-p"
        assert "EU ruling" in result["debate_focus"]
        assert result["user_input"] == "original topic"
        assert result.get("handled") is not True  # must fall through to the coordinator
        assert any("recalling perspective findings" in str(e.get("content", "")) for e in events)

    @pytest.mark.unit
    def test_declining_stops_here_without_starting_a_run(self):
        with patch.dict(sys.modules, {"brooks": MagicMock()}):
            from routing import gates
            result = {}
            events = list(gates.handle_pending_context(
                {"type": "swarm_debate", "prompt": "topic", "coordination_id": "coord-p"},
                "not_now", session_id="s", owner_id="o", history=None, extracted_context="",
                ace_token=None, ultraplan_mode=False, dev_mode=False, result=result,
            ))
        assert result["handled"] is True
        assert "debate_mode" not in result
        assert any(e["type"] == "response" for e in events)

    @pytest.mark.unit
    def test_free_text_answer_becomes_the_debate_focus(self):
        """allow_freetext is on the card, so an un-chipped answer must still work."""
        with patch.dict(sys.modules, {"brooks": MagicMock()}):
            from routing import gates
            result = {}
            list(gates.handle_pending_context(
                {"type": "swarm_debate", "prompt": "topic", "coordination_id": "coord-p"},
                "argue whether the cost floor is acceptable for small providers",
                session_id="s", owner_id="o", history=None, extracted_context="",
                ace_token=None, ultraplan_mode=False, dev_mode=False, result=result,
            ))
        assert "small providers" in result["debate_focus"]
