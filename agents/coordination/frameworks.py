"""
Thinking frameworks — assignable constraint sets for Collective agents.

A persona says what an agent *is* ("Feynman is playful and first-principles").
A framework says what an agent *may do* and *must do*: a licensed move set,
minimum obligations, prohibitions, and a structured output contract that can be
checked after the fact.  Without the checkable part a framework degrades into a
second persona, so every record here carries either required output keys and/or
``min_counts`` thresholds that :func:`audit_turn` verifies deterministically
before any LLM is asked to judge compliance.

Families (``FRAMEWORK_FAMILIES``) exist so assignment can guarantee cognitive
diversity structurally: collision between agents is the point of a debate, and
collision requires frameworks from different families in the room.

Emergent frameworks are *coined then validated*: a candidate is recorded with
its parent frameworks and the verbatim spans that evidence it, but it only
becomes assignable once a later run applies it and it produces a concession.
"""

import json
import re
import time
from pathlib import Path

from ollama import Client

from config import COORDINATOR_MODEL
from logger_setup import setup_logger
from utils.gpu_queue import get_swarm_worker_host

logger = setup_logger("Lamport")

FRAMEWORK_FAMILIES: list[str] = [
    "critical", "structural", "empirical", "generative", "adjudicative",
]

# Same-family pairs collide weakly; these family combos are the productive ones.
_COLLISION_WEIGHTS: dict[tuple[str, str], float] = {
    ("critical", "generative"): 1.0,
    ("critical", "adjudicative"): 0.95,
    ("critical", "empirical"): 0.85,
    ("critical", "structural"): 0.8,
    ("empirical", "adjudicative"): 0.8,
    ("generative", "structural"): 0.7,
    ("empirical", "generative"): 0.7,
    ("structural", "adjudicative"): 0.65,
    ("empirical", "structural"): 0.6,
    ("generative", "adjudicative"): 0.6,
}
_SAME_FAMILY_WEIGHT = 0.2

# Named pair overrides that beat the family heuristic, positive or negative.
_COLLISION_OVERRIDES: dict[frozenset, float] = {
    frozenset(["falsification", "reframe"]): 1.0,
    frozenset(["presumption_of_error", "first_principles"]): 0.95,
    frozenset(["evidence_ladder", "analogy_transfer"]): 0.95,
    frozenset(["premortem", "base_rate"]): 0.4,
    frozenset(["veil_of_ignorance", "standing"]): 0.9,
}

FRAMEWORKS: dict[str, dict] = {
    "falsification": {
        "name": "Falsification Testing",
        "family": "critical",
        "summary": "Treat every claim as a conjecture and name the observation that would refute it.",
        "moves": [
            "Restate the claim as a testable proposition",
            "Construct the strongest concrete counter-example",
            "Specify the observation that would refute it and whether it holds",
            "Downgrade a claim to opinion when no refutation condition can be stated",
        ],
        "mandates": [
            "Find at least one flaw in every argument engaged, including your own",
            "Every claim you advance must carry a stated refutation condition",
            "Report which claims survived and which were falsified, separately",
        ],
        "prohibitions": [
            "Do not accept a claim on the strength of consensus or authority alone",
            "Do not state an unfalsifiable condition as a test",
        ],
        "output_contract": ["claims", "refutation_tests", "survived", "falsified"],
        "min_counts": {"refutation_tests": 1, "falsified": 1},
        "affinity": ["scientific", "technical", "verifier", "researcher", "analyst"],
    },
    "presumption_of_error": {
        "name": "Presumption of Error",
        "family": "critical",
        "summary": "Assume the position you were handed is wrong, and build the best case against it.",
        "moves": [
            "Adopt the assigned position as the target, not as your view",
            "Steelman the opposite position harder than its own advocates would",
            "Enumerate the conditions under which the position becomes harmful",
            "Identify who is damaged if the position is acted on",
        ],
        "mandates": [
            "Produce the strongest available objection to the assigned position",
            "Rate your own objection's strength and state what would defeat it",
        ],
        "prohibitions": [
            "Do not defend the assigned position",
            "Do not produce a strawman objection that no serious proponent holds",
        ],
        "output_contract": ["target_position", "strongest_objection", "objection_strength", "what_defeats_it"],
        "min_counts": {"strongest_objection": 1},
        "affinity": ["ethical", "regulatory", "social", "verifier"],
    },
    "logical_consistency": {
        "name": "Logical Consistency Checking",
        "family": "critical",
        "summary": "Audit the set of claims for contradiction, equivocation, and unloaded premises.",
        "moves": [
            "Pair claims and test whether any two can both be true",
            "Detect equivocation — one term carrying two meanings",
            "Make an implicit premise explicit and then attack it",
            "Flag conclusions that do not follow from their stated grounds",
        ],
        "mandates": [
            "Name at least one inconsistency across the claims in play, or state precisely why none exists",
            "Quote the two spans that contradict each other verbatim",
        ],
        "prohibitions": ["Do not report a difference of opinion as a logical contradiction"],
        "output_contract": ["inconsistencies", "contradicted_spans", "implicit_premises"],
        "min_counts": {"implicit_premises": 1},
        "affinity": ["technical", "analyst", "verifier", "researcher", "economic"],
    },
    "premortem": {
        "name": "Pre-Mortem",
        "family": "critical",
        "summary": "Assume the proposal has already failed and reconstruct the causal path.",
        "moves": [
            "Fix the outcome as total failure at a stated horizon",
            "Generate independent failure mechanisms",
            "Rank mechanisms by likelihood and detectability",
            "Mark which failures are visible only after the point of no return",
        ],
        "mandates": [
            "Produce at least three distinct failure mechanisms",
            "Identify the single earliest warning signal and its latency",
        ],
        "prohibitions": ["Do not convert failures into generic risk warnings"],
        "output_contract": ["failure_mechanisms", "ranked_by_likelihood", "earliest_warning_signal"],
        "min_counts": {"failure_mechanisms": 3},
        "affinity": ["technical", "economic", "devops", "architect", "policy"],
    },
    "first_principles": {
        "name": "First-Principles Decomposition",
        "family": "structural",
        "summary": "Break to constraints that cannot be removed, then rebuild without inherited assumptions.",
        "moves": [
            "Decompose until each element is a physical, economic, or logical constraint",
            "Label every inherited assumption and test whether it is actually load-bearing",
            "Rebuild a solution using only the irreducible constraints",
            "Compute the theoretical floor for each scarce quantity",
        ],
        "mandates": [
            "Discard at least one assumption that everyone treats as fixed and show it is contingent",
            "State the irreducible constraints your reconstruction rests on",
        ],
        "prohibitions": ["Do not reason by comparing to existing implementations"],
        "output_contract": ["irreducible_constraints", "dropped_assumptions", "rebuilt_options"],
        "min_counts": {"dropped_assumptions": 1},
        "affinity": ["technical", "scientific", "architect", "engineer", "end_user"],
    },
    "systems_feedback": {
        "name": "Systems Feedback Analysis",
        "family": "structural",
        "summary": "Model loops, delays, and leverage points rather than linear cause and effect.",
        "moves": [
            "Map reinforcing loops and balancing loops",
            "Locate delays and ask what they destabilise",
            "Identify the leverage point with the smallest required intervention",
            "Trace second-order effects onto the original actor",
        ],
        "mandates": [
            "Name at least one reinforcing and one balancing loop present in the situation",
            "Identify at least one delayed effect that will confuse future diagnosis",
        ],
        "prohibitions": ["Do not describe a sequence of events as a causal chain with no return path"],
        "output_contract": ["reinforcing_loops", "balancing_loops", "delays", "leverage_points"],
        "min_counts": {"reinforcing_loops": 1, "balancing_loops": 1},
        "affinity": ["environmental", "economic", "social", "policy", "historical"],
    },
    "tradeoff_ledger": {
        "name": "Trade-off Ledger",
        "family": "structural",
        "summary": "No claim without a named cost, and no cost without a named bearer.",
        "moves": [
            "Enumerate options and score cost against benefit for each",
            "Assign every cost to the specific party who bears it",
            "Mark costs that are concentrated against benefits that are diffuse",
            "State the exchange rate you would need to accept to prefer each option",
        ],
        "mandates": [
            "Attach at least one cost to every option you advance",
            "Name the party bearing the largest cost and whether they consented",
        ],
        "prohibitions": ["Do not present an option as strictly better with no bearer of its cost"],
        "output_contract": ["options", "costs", "benefits", "borne_by", "concentrated_vs_diffuse"],
        "min_counts": {"costs": 1, "borne_by": 1},
        "affinity": ["economic", "policy", "regulatory", "end_user", "architect"],
    },
    "morphological": {
        "name": "Morphological Analysis",
        "family": "structural",
        "summary": "Separate the parameters, enumerate their independent options, and examine untried combinations.",
        "moves": [
            "Decompose the problem into independent parameters",
            "Enumerate 3+ options per parameter without assuming compatibility",
            "Fill the combination grid and mark occupied versus empty cells",
            "Explain why each interesting empty cell is empty",
        ],
        "mandates": [
            "Surface at least one combination nobody in the debate has proposed",
            "State why each surfaced combination is absent — infeasible, unnoticed, or blocked by incentive",
        ],
        "prohibitions": ["Do not collapse parameters back into a single familiar design early"],
        "output_contract": ["parameters", "options_per_parameter", "untried_combinations", "absence_reasons"],
        "min_counts": {"untried_combinations": 1},
        "affinity": ["technical", "architect", "creative", "historical", "scientific"],
    },
    "evidence_ladder": {
        "name": "Evidence Grading",
        "family": "empirical",
        "summary": "Grade every claim by strength of evidence and expose which conclusions rest on weak rungs.",
        "moves": [
            "Grade each claim 1 (assertion) to 5 (controlled or replicated measurement)",
            "Cite the actual source of the grade",
            "Recompute the conclusion using only claims graded 4+",
            "Mark inference as inference wherever measurement is absent",
        ],
        "mandates": [
            "Assign a numeric grade to every claim used, with no ungraded claims",
            "Flag every claim driving the conclusion that sits below grade 3",
        ],
        "prohibitions": ["Do not treat vivid anecdote as measurement", "Do not invent citations"],
        "output_contract": ["graded_claims", "low_grade_drivers", "missing_evidence"],
        "min_counts": {"graded_claims": 1},
        "affinity": ["scientific", "researcher", "analyst", "regulatory", "historical"],
    },
    "base_rate": {
        "name": "Reference-Class Forecasting",
        "family": "empirical",
        "summary": "Start from the outside view of how often this kind of thing works, then adjust.",
        "moves": [
            "Define the reference class explicitly and narrowly enough to be informative",
            "State the prior from that class before any case-specific reasoning",
            "Adjust for distinguishing features and quantify each adjustment",
            "Report the final posterior as a distribution, not a point",
        ],
        "mandates": [
            "Name the reference class and the prior drawn from it",
            "State which inside-view evidence moved you and by how much",
        ],
        "prohibitions": ["Do not begin from the specifics of this case"],
        "output_contract": ["reference_class", "prior", "adjustments", "posterior_range"],
        "min_counts": {"adjustments": 1},
        "affinity": ["economic", "scientific", "analyst", "policy", "devops"],
    },
    "prediction_test": {
        "name": "Committed Predictions",
        "family": "empirical",
        "summary": "Expose a position to being wrong by writing down checkable forecasts.",
        "moves": [
            "Convert the position into numbered predictions with explicit horizons",
            "Attach probabilities and the observable that resolves each",
            "State which prediction you would abandon the position over",
            "Score prior predictions when evidence arrives",
        ],
        "mandates": [
            "Commit to at least two predictions with a horizon and a probability",
            "Name the one prediction whose failure would retire your position",
        ],
        "prohibitions": ["Do not issue predictions that cannot be checked within the stated horizon"],
        "output_contract": ["predictions", "resolution_criteria", "position_killing_prediction"],
        "min_counts": {"predictions": 2},
        "affinity": ["scientific", "economic", "technical", "researcher", "environmental"],
    },
    "inversion": {
        "name": "Inversion",
        "family": "generative",
        "summary": "Solve the reverse problem and let the answer constrain the forward one.",
        "moves": [
            "State the anti-goal precisely",
            "Design the reliable route to the anti-goal",
            "Invert each step of that route into a requirement",
            "Separate requirements that are avoidable from those that are structural",
        ],
        "mandates": [
            "Produce the recipe for guaranteeing failure before discussing success",
            "Derive at least three requirements by inverting that recipe",
        ],
        "prohibitions": ["Do not restate the original goal in negative words"],
        "output_contract": ["anti_goal", "failure_recipe", "inverted_requirements"],
        "min_counts": {"failure_recipe": 3, "inverted_requirements": 3},
        "affinity": ["technical", "devops", "verifier", "architect", "ethical"],
    },
    "analogy_transfer": {
        "name": "Structural Analogy Transfer",
        "family": "generative",
        "summary": "Import the solved structure of another domain and locate exactly where it breaks.",
        "moves": [
            "Map relational structure, not surface features, onto a source domain",
            "Transfer the source domain's solution strategy",
            "Enumerate disanalogies that could invalidate the transfer",
            "State which disanalogy is most likely fatal",
        ],
        "mandates": [
            "Name the source domain and the specific structural mapping used",
            "Identify at least two disanalogies and the one that would break the transfer",
        ],
        "prohibitions": ["Do not transfer vocabulary while calling it structure"],
        "output_contract": ["source_domain", "structural_mapping", "disanalogies", "fatal_disanalogy"],
        "min_counts": {"disanalogies": 2},
        "affinity": ["historical", "scientific", "architect", "policy", "social"],
    },
    "reframe": {
        "name": "Frame Criticism",
        "family": "generative",
        "summary": "Question whether the question on the table is the one worth answering.",
        "moves": [
            "Name the framing that the debate has silently accepted",
            "Identify what that framing makes unaskable",
            "Propose an alternative framing and the different answer it yields",
            "State which framing better matches the stated purpose",
        ],
        "mandates": [
            "Propose at least one alternative framing that changes the conclusion",
            "Name a question the current framing structurally prevents anyone from asking",
        ],
        "prohibitions": ["Do not rename the same question and call it a new frame"],
        "output_contract": ["accepted_frame", "suppressed_questions", "alternative_frame", "changed_conclusion"],
        "min_counts": {"suppressed_questions": 1, "alternative_frame": 1},
        "affinity": ["social", "historical", "ethical", "policy", "creative", "end_user"],
    },
    "veil_of_ignorance": {
        "name": "Veil of Ignorance",
        "family": "adjudicative",
        "summary": "Choose principles without knowing which position you will occupy.",
        "moves": [
            "List the positions the outcome distributes people across",
            "Evaluate each option from the worst-off position",
            "Rank options by their worst-case floor rather than expected value",
            "Identify which compensation would make an unacceptable floor acceptable",
        ],
        "mandates": [
            "Rank every option by outcome for the worst-off party",
            "State the minimum floor below which an option is unacceptable regardless of aggregate gain",
        ],
        "prohibitions": ["Do not average away a position you might occupy"],
        "output_contract": ["positions", "worst_off_ranking", "unacceptable_floor"],
        "min_counts": {"positions": 2, "worst_off_ranking": 1},
        "affinity": ["ethical", "policy", "social", "regulatory", "end_user"],
    },
    "standing": {
        "name": "Interest and Standing",
        "family": "adjudicative",
        "summary": "Ask whose interest a claim serves and who is unrepresented in the room.",
        "moves": [
            "Map each claim to the party benefiting from it being believed",
            "Identify affected parties with no representative in the debate",
            "Separate claims that survive the interest disclosure from those that do not",
            "Trace where the cost of a recommendation lands relative to who recommends it",
        ],
        "mandates": [
            "Name at least one absent party whose interests the debate is silently overriding",
            "State the interest served by the strongest claim currently in play",
        ],
        "prohibitions": ["Do not dismiss a claim solely because it benefits someone"],
        "output_contract": ["claim_beneficiaries", "absent_parties", "surviving_claims"],
        "min_counts": {"absent_parties": 1},
        "affinity": ["social", "economic", "regulatory", "political", "policy", "ethical"],
    },
}

EMERGENT_CATALOGUE_PATH = Path(__file__).parent / "frameworks_emergent.json"


# ---------------------------------------------------------------------------
# Catalogue loading and persistence
# ---------------------------------------------------------------------------

def load_emergent(path: Path | None = None) -> list[dict]:
    """Read the emergent-framework ledger. Returns [] on missing or corrupt file."""
    p = path or EMERGENT_CATALOGUE_PATH
    try:
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("frameworks", []) if isinstance(data, dict) else []
    except Exception as e:
        logger.warning(f"[Frameworks] Emergent ledger unreadable (treating as empty): {e}")
        return []


def save_emergent_framework(spec: dict, path: Path | None = None) -> dict:
    """Upsert an emergent framework into the ledger by id and return the stored record."""
    p = path or EMERGENT_CATALOGUE_PATH
    entries = load_emergent(p)
    record = dict(spec)
    record.setdefault("status", "candidate")
    record["updated_at"] = int(time.time())
    for i, existing in enumerate(entries):
        if existing.get("id") == record.get("id"):
            entries[i] = {**existing, **record}
            break
    else:
        record.setdefault("created_at", int(time.time()))
        entries.append(record)
    payload = {"frameworks": entries, "schema_version": 1}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return record


def load_catalogue(include_emergent: bool = True, path: Path | None = None) -> dict[str, dict]:
    """Merged assignable catalogue: curated frameworks plus validated emergent ones.

    Candidates are deliberately excluded — an emergent framework becomes
    assignable only after a later run applies it and it produces a concession.
    """
    catalogue = dict(FRAMEWORKS)
    if not include_emergent:
        return catalogue
    for entry in load_emergent(path):
        fid = entry.get("id")
        if not fid or entry.get("status") != "validated" or fid in catalogue:
            continue
        catalogue[fid] = {
            "name": entry.get("name", fid),
            "family": entry.get("family", "generative"),
            "summary": entry.get("summary", ""),
            "moves": entry.get("moves", []),
            "mandates": entry.get("mandates", []),
            "prohibitions": entry.get("prohibitions", []),
            "output_contract": entry.get("output_contract", []),
            "min_counts": entry.get("min_counts", {}),
            "affinity": entry.get("affinity", []),
            "emergent": True,
            "parents": entry.get("parents", []),
        }
    return catalogue


# ---------------------------------------------------------------------------
# Collision geometry
# ---------------------------------------------------------------------------

def collision_score(a_id: str, b_id: str, catalogue: dict | None = None) -> float:
    """How much productive friction two frameworks generate when pointed at each other."""
    cat = catalogue or FRAMEWORKS
    if not a_id or not b_id or a_id == b_id:
        return -1.0
    override = _COLLISION_OVERRIDES.get(frozenset([a_id, b_id]))
    if override is not None:
        return override
    fam_a = cat.get(a_id, {}).get("family")
    fam_b = cat.get(b_id, {}).get("family")
    if not fam_a or not fam_b or fam_a == fam_b:
        return _SAME_FAMILY_WEIGHT
    return _COLLISION_WEIGHTS.get((fam_a, fam_b), _COLLISION_WEIGHTS.get((fam_b, fam_a), 0.5))


def most_contested_partner(own_index: int, assigned_ids: list[str],
                           catalogue: dict | None = None) -> int | None:
    """Index of the other agent this one should cross-examine for maximum friction."""
    if len(assigned_ids) < 2:
        return None
    best_idx, best_score = None, -2.0
    for j, other in enumerate(assigned_ids):
        if j == own_index:
            continue
        score = collision_score(assigned_ids[own_index], other, catalogue)
        if score > best_score:
            best_idx, best_score = j, score
    return best_idx


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------

def framework_prompt_block(framework_id: str, catalogue: dict | None = None,
                           secondary_id: str | None = None) -> str:
    """Composable constraint block — also the injection point for research lenses."""
    cat = catalogue or FRAMEWORKS
    fw = cat.get(framework_id)
    if not fw:
        return ""
    lines = [
        f"YOUR ASSIGNED FRAMEWORK: {fw['name']} (family: {fw['family']})",
        fw.get("summary", ""),
        "",
        "LICENSED MOVES — these are the operations you may perform:",
    ]
    lines += [f"  - {m}" for m in fw.get("moves", [])]
    lines += ["", "MANDATES — non-negotiable. Your turn is audited against these:", ""]
    lines += [f"  {i + 1}. {m}" for i, m in enumerate(fw.get("mandates", []))]
    if fw.get("prohibitions"):
        lines += ["", "PROHIBITED:"]
        lines += [f"  - {p}" for p in fw["prohibitions"]]
    contract = fw.get("output_contract") or []
    if contract:
        lines += ["", f"YOUR TURN MUST END WITH VALID JSON CONTAINING THESE KEYS: {', '.join(contract)}"]
    secondary = cat.get(secondary_id or "")
    if secondary:
        lines += [
            "",
            f"SECONDARY FRAMEWORK (apply only where it does not conflict with the primary): "
            f"{secondary['name']} — {secondary.get('summary', '')}",
        ]
        if secondary.get("mandates"):
            lines += [f"  - {m}" for m in secondary["mandates"][:2]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Structured LLM call
# ---------------------------------------------------------------------------

def structured_llm_call(prompt: str, schema: dict, model_name: str | None = None,
                        system: str = "", temperature: float = 0.3,
                        num_predict: int = 1400, timeout: int = 120) -> dict | None:
    """One structured-output ollama chat call. Returns parsed JSON or None."""
    _model = model_name or COORDINATOR_MODEL
    try:
        client = Client(host=get_swarm_worker_host(_model), timeout=timeout)
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = client.chat(
            model=_model,
            messages=messages,
            format=schema,
            options={"temperature": temperature, "num_predict": num_predict},
        )
        raw = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[Frameworks] structured LLM call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48] or "unnamed"


def prefilter_frameworks(roles: list[str], catalogue: dict | None = None,
                         limit: int = 8) -> list[str]:
    """Deterministic shortlist: affinity hits across all roles, family-diverse."""
    cat = catalogue or FRAMEWORKS
    scored: dict[str, tuple[int, str]] = {}
    for fid, fw in cat.items():
        affinity = set(fw.get("affinity", []))
        hits = sum(1 for r in roles if r and (r.lower() in affinity or r.lower() in fid))
        scored[fid] = (hits, fw.get("family", ""))
    ranked = sorted(scored, key=lambda f: (-scored[f][0], f))
    picked: list[str] = []
    families: dict[str, int] = {}
    for fid in ranked:
        fam = scored[fid][1]
        if families.get(fam, 0) >= 2:
            continue
        families[fam] = families.get(fam, 0) + 1
        picked.append(fid)
        if len(picked) >= limit:
            break
    for fid in ranked:
        if len(picked) >= limit:
            break
        if fid not in picked:
            picked.append(fid)
    return picked


def validate_assignment(assignments: list[dict], catalogue: dict | None = None) -> list[str]:
    """Return the list of violated invariants for an assignment (empty = valid).

    Invariants, in priority order:
      1. no two agents share a primary framework — identical primaries mean no collision
      2. at least min(3, n) distinct families present
      3. at least one `critical` framework in the room — a debate needs an attacker
    """
    cat = catalogue or FRAMEWORKS
    problems: list[str] = []
    primaries = [a.get("primary") for a in assignments]
    if not all(primaries):
        problems.append("every agent must have a primary framework")
        return problems
    if len(set(primaries)) != len(primaries):
        problems.append("duplicate primary frameworks")
    if any(p not in cat for p in primaries):
        problems.append("assignment references unknown framework ids")
    families = {cat[p].get("family") for p in primaries if p in cat}
    if len(families) < min(3, len(primaries)):
        problems.append(f"only {len(families)} families represented")
    if "critical" not in families and len(primaries) >= 2:
        problems.append("no critical-family framework assigned")
    return problems


def _fallback_assignment(perspectives: list[dict], catalogue: dict | None = None) -> list[dict]:
    """Family-rotation assignment used when the LLM path fails or violates invariants."""
    cat = catalogue or load_catalogue()
    roles = [p.get("role", "") for p in perspectives]
    shortlist = prefilter_frameworks(roles, cat, limit=max(len(perspectives) * 2, 6))
    by_family: dict[str, list[str]] = {}
    for fid in shortlist:
        by_family.setdefault(cat[fid].get("family", "other"), []).append(fid)
    order = [f for f in FRAMEWORK_FAMILIES if by_family.get(f)] + \
            [f for f in by_family if f not in FRAMEWORK_FAMILIES]
    cursor = {fam: 0 for fam in by_family}
    out: list[dict] = []
    for i, persp in enumerate(perspectives):
        fam = order[i % len(order)] if order else "critical"
        pool = by_family.get(fam) or next(iter(by_family.values()), [])
        primary = pool[cursor.get(fam, 0) % max(len(pool), 1)] if pool else "falsification"
        cursor[fam] = cursor.get(fam, 0) + 1
        others = [f for f in shortlist if f != primary]
        secondary = others[i % len(others)] if others else None
        out.append({
            "perspective_label": persp.get("perspective_label", persp.get("role", f"agent_{i}")),
            "primary": primary,
            "secondary": secondary,
            "rationale": "deterministic family-rotation fallback",
        })
    return out


def assign_frameworks(perspectives: list[dict], problem_type: str = "",
                     model_name: str | None = None,
                     catalogue: dict | None = None) -> list[dict]:
    """Assign each debating agent a primary + secondary framework with guaranteed diversity.

    Deterministic prefilter first, then one coordinator call constrained to the
    shortlist, then the invariants are checked in code. A violating or failed LLM
    result is replaced by the deterministic fallback — framework assignment must
    never abort a run.

    Returns::
        [{"perspective_label": str, "primary": str, "secondary": str, "rationale": str}, ...]
    """
    cat = catalogue or load_catalogue()
    if not perspectives:
        return []
    roles = [p.get("role", "") for p in perspectives]
    shortlist = prefilter_frameworks(roles, cat, limit=max(len(perspectives) * 3, 8))
    if len(shortlist) < len(perspectives):
        shortlist = list(cat.keys())[:max(len(perspectives), 6)]

    fw_lines = "\n".join(
        f"  - {fid} [{cat[fid].get('family')}] {cat[fid].get('name')}: {cat[fid].get('summary', '')}"
        for fid in shortlist
    )
    persp_lines = "\n".join(
        f"  {i}. {p.get('perspective_label', p.get('role', '?'))} (lens role={p.get('role', '?')})"
        for i, p in enumerate(perspectives)
    )
    schema = {
        "type": "object",
        "required": ["assignments"],
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["index", "primary", "secondary", "rationale"],
                    "properties": {
                        "index":     {"type": "integer"},
                        "primary":   {"type": "string", "enum": shortlist},
                        "secondary": {"type": "string", "enum": shortlist + [""]},
                        "rationale": {"type": "string"},
                    },
                },
            }
        },
    }
    prompt = (
        f"You are assigning thinking frameworks to agents who will debate a question.\n\n"
        f"A framework is a constraint on cognition: it fixes which moves are licensed and what "
        f"the agent is REQUIRED to produce. Agents are not choosing personas — they are being "
        f"equipped with incompatible methods so their methods collide.\n\n"
        f"PROBLEM TYPE: {problem_type or 'unspecified'}\n\n"
        f"AGENTS (one entry required per index):\n{persp_lines}\n\n"
        f"AVAILABLE FRAMEWORKS (choose ONLY from this list):\n{fw_lines}\n\n"
        f"HARD REQUIREMENTS:\n"
        f"1. No two agents may share a primary framework.\n"
        f"2. Use at least {min(3, len(perspectives))} distinct families.\n"
        f"3. At least one agent must get a `critical`-family framework.\n"
        f"4. Match each framework to what that agent's lens can actually see, not to a stereotype.\n"
        f"5. Give each agent a secondary framework from a DIFFERENT family from its primary "
        f"(or an empty string if none fits).\n\n"
        f"Return valid JSON only."
    )
    result = structured_llm_call(prompt, schema, model_name=model_name,
                                 system="You are a debate designer. Return JSON only.",
                                 temperature=0.5, num_predict=900)

    assignments: list[dict] = []
    if isinstance(result, dict):
        by_index = {int(a.get("index", -1)): a for a in result.get("assignments", [])
                    if isinstance(a, dict)}
        for i, persp in enumerate(perspectives):
            a = by_index.get(i)
            if not a:
                assignments = []
                break
            assignments.append({
                "perspective_label": persp.get("perspective_label", persp.get("role", f"agent_{i}")),
                "primary": (a.get("primary") or "").strip(),
                "secondary": (a.get("secondary") or "").strip() or None,
                "rationale": a.get("rationale", ""),
            })

    if not assignments or validate_assignment(assignments, cat):
        problems = validate_assignment(assignments, cat) if assignments else ["no result"]
        logger.warning(f"[Frameworks] assignment invalid ({problems}) — using deterministic fallback")
        assignments = _fallback_assignment(perspectives, cat)

    for a in assignments:
        cat_entry = cat.get(a["primary"], {})
        a["primary_name"] = cat_entry.get("name", a["primary"])
        a["primary_family"] = cat_entry.get("family", "")
        a["secondary_name"] = cat.get(a.get("secondary") or "", {}).get("name", "")
    return assignments


# ---------------------------------------------------------------------------
# Compliance audit
# ---------------------------------------------------------------------------

def check_contract(framework_id: str, payload: dict,
                   catalogue: dict | None = None) -> list[str]:
    """Deterministic contract check — free, and runs before any LLM audit."""
    cat = catalogue or FRAMEWORKS
    fw = cat.get(framework_id)
    if not fw or not isinstance(payload, dict):
        return ["no parsed output to audit"]
    violations: list[str] = []
    for key in fw.get("output_contract", []):
        if key not in payload:
            violations.append(f"missing required key '{key}'")
    for key, minimum in (fw.get("min_counts") or {}).items():
        value = payload.get(key)
        actual = len(value) if isinstance(value, (list, dict, str)) else (0 if value is None else 1)
        if actual < minimum:
            violations.append(f"'{key}' has {actual} item(s), framework requires >= {minimum}")
    return violations


def audit_turn(framework_id: str, payload: dict, turn_text: str = "",
               model_name: str | None = None,
               catalogue: dict | None = None) -> dict:
    """Judge a debate turn against its framework's mandates.

    Returns ``{"compliant": bool, "violations": [str], "audited_by": "contract"|"contract+llm"}``.
    The LLM mandate check is skipped when the deterministic contract check already
    failed — there is no point paying tokens to judge a turn that is structurally short.
    """
    fw = (catalogue or FRAMEWORKS).get(framework_id, {})
    violations = check_contract(framework_id, payload, catalogue)
    if violations:
        return {"compliant": False, "violations": violations, "audited_by": "contract"}
    mandates = fw.get("mandates", [])
    if not mandates:
        return {"compliant": True, "violations": [], "audited_by": "contract"}

    schema = {
        "type": "object",
        "required": ["compliant", "violations"],
        "properties": {
            "compliant": {"type": "boolean"},
            "violations": {"type": "array", "items": {"type": "string"}},
        },
    }
    prompt = (
        f"An agent was operating under the framework '{fw.get('name', framework_id)}'. "
        f"Audit its turn against the framework's mandates.\n\n"
        f"MANDATES:\n" + "\n".join(f"  {i + 1}. {m}" for i, m in enumerate(mandates)) + "\n\n"
        f"PROHIBITIONS:\n" + "\n".join(f"  - {p}" for p in fw.get("prohibitions", [])) + "\n\n"
        f"AGENT TURN:\n{(turn_text or json.dumps(payload, ensure_ascii=False))[:6000]}\n\n"
        f"Judge ONLY whether each mandate was satisfied and each prohibition respected. "
        f"Do not judge the quality of the reasoning or whether you agree with the conclusion. "
        f"A mandate counts as satisfied if the agent made a genuine attempt at it. "
        f"For each violation, name the mandate number and quote the shortfall in a few words. "
        f"Return valid JSON only."
    )
    result = structured_llm_call(prompt, schema, model_name=model_name,
                                 system="You are a strict but fair process auditor.",
                                 temperature=0.0, num_predict=400)
    if not isinstance(result, dict):
        return {"compliant": True, "violations": [], "audited_by": "contract+llm_unavailable"}
    violations = [str(v) for v in result.get("violations", []) if str(v).strip()]
    return {"compliant": bool(result.get("compliant", True)) and not violations,
            "violations": violations, "audited_by": "contract+llm"}


# ---------------------------------------------------------------------------
# Emergence
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "that", "this", "with", "from", "them", "they", "then", "than", "when",
    "where", "what", "who", "why", "how", "which", "would", "could", "should",
    "before", "after", "into", "about", "other", "others", "each", "every",
    "both", "also", "only", "must", "your", "yours", "their", "there", "here",
    "make", "makes", "made", "make", "using", "used", "uses", "upon", "because",
})


def _terms(moves: list) -> set[str]:
    """Distinctive (long, non-stopword) terms of a move list, stemmed loosely."""
    out: set[str] = set()
    for move in moves or []:
        norm = re.sub(r"[^a-z0-9 ]", " ", str(move).lower())
        for word in norm.split():
            if len(word) > 4 and word not in _STOPWORDS:
                out.add(word.rstrip("s") if len(word) > 5 else word)
    return out


def subsumed(candidate_moves: list[str], parent_ids: list[str],
             catalogue: dict | None = None) -> tuple[bool, list[str]]:
    """Deterministic first pass: is the candidate merely a restatement of its parents?

    Returns ``(fully_subsumed, residual_moves)``. A move counts as derivative when
    nearly all of its distinctive terms already appear somewhere in the parents'
    licensed moves or mandates. Anything with a genuinely novel term survives as
    residual, and a candidate with no residual cannot be emergent — rejected here,
    for free, before any model is asked to judge it.

    Term *coverage* rather than term *presence*: a single shared word like
    "condition" must not be enough to call a new method derivative, or the filter
    would reject almost every real emergence.
    """
    cat = catalogue or FRAMEWORKS
    vocab: set[str] = set()
    for pid in parent_ids:
        entry = cat.get(pid, {})
        vocab |= _terms(entry.get("moves", []))
        vocab |= _terms(entry.get("mandates", []))

    residual: list[str] = []
    for move in candidate_moves or []:
        terms = _terms([move])
        if not terms:
            residual.append(move)
            continue
        covered = sum(1 for t in terms if t in vocab)
        if covered / len(terms) < 0.8:
            residual.append(move)
    return (not residual, residual)


def detect_emergent_framework(round_transcripts: list[dict], assigned_ids: list[str],
                              concessions: list[dict], model_name: str | None = None,
                              coordination_id: str = "",
                              catalogue: dict | None = None) -> dict | None:
    """Look for a method that emerged from framework collision in one round.

    Admission requires all three criteria, and the first two are checked in code:
      observable   — the move pattern appears in >= 2 distinct agents' turns
      non-derivable— it is not a subset of the union of the parent move sets
      load-bearing — at least one concession in the round cites it
    Returns the candidate spec, or None when nothing qualifies.
    """
    cat = catalogue or FRAMEWORKS
    agents = {t.get("agent") for t in round_transcripts if t.get("agent")}
    if len(agents) < 2 or len(round_transcripts) < 2:
        return None

    schema = {
        "type": "object",
        "required": ["found", "name", "family", "summary", "moves",
                     "observed_in_agents", "evidence_spans", "parent_frameworks",
                     "drove_concession"],
        "properties": {
            "found": {"type": "boolean"},
            "name": {"type": "string"},
            "family": {"type": "string", "enum": FRAMEWORK_FAMILIES},
            "summary": {"type": "string"},
            "moves": {"type": "array", "items": {"type": "string"}},
            "observed_in_agents": {"type": "array", "items": {"type": "string"}},
            "evidence_spans": {"type": "array", "items": {"type": "string"}},
            "parent_frameworks": {"type": "array", "items": {"type": "string"}},
            "drove_concession": {"type": "boolean"},
        },
    }
    transcripts = "\n\n".join(
        f"=== {t.get('agent')} (framework: {t.get('framework')}) ===\n{t.get('text', '')[:2500]}"
        for t in round_transcripts
    )
    concession_note = json.dumps(concessions[:8], ensure_ascii=False) if concessions else "[]"
    prompt = (
        f"Several agents debated, each under an explicit thinking framework. Look for a NEW "
        f"method that emerged from their collision — a move pattern that agents had to invent "
        f"to survive cross-examination, which no single assigned framework licenses.\n\n"
        f"ASSIGNED FRAMEWORKS: {', '.join(assigned_ids)}\n\n"
        f"A candidate qualifies only if ALL THREE hold:\n"
        f"1. OBSERVABLE — it appears in the turns of at least 2 different agents; quote the "
        f"verbatim spans.\n"
        f"2. NON-DERIVABLE — it is not simply one parent framework's move, or a restatement of "
        f"the union of them. Name the parents it is NOT reducible to.\n"
        f"3. LOAD-BEARING — at least one concession or reversal in the round depended on it.\n\n"
        f"CONCESSIONS RECORDED: {concession_note}\n\n"
        f"TRANSCRIPTS:\n{transcripts[:16000]}\n\n"
        f"If nothing genuinely qualifies, return found=false. Do not manufacture an emergent "
        f"framework to satisfy the request. Return valid JSON only."
    )
    result = structured_llm_call(prompt, schema, model_name=model_name,
                                 system="You identify reusable method that agents were forced to invent.",
                                 temperature=0.4, num_predict=1200)
    if not isinstance(result, dict) or not result.get("found"):
        return None

    observed = {str(a) for a in result.get("observed_in_agents", [])}
    if len(observed & agents) < 2:
        logger.info("[Frameworks] emergence candidate failed the observability test")
        return None
    parents = [p for p in result.get("parent_frameworks", []) if p] or assigned_ids
    is_subsumed, residual = subsumed(result.get("moves", []), parents, cat)
    if is_subsumed:
        logger.info("[Frameworks] emergence candidate is the union of its parents — rejected")
        return None
    if not result.get("drove_concession"):
        logger.info("[Frameworks] emergence candidate is not load-bearing — rejected")
        return None

    spec = {
        "id": _slug(result.get("name", "emergent")),
        "name": str(result.get("name", "Emergent Framework")).strip()[:80],
        "family": result.get("family") if result.get("family") in FRAMEWORK_FAMILIES else "generative",
        "summary": str(result.get("summary", "")).strip()[:400],
        "moves": [str(m)[:300] for m in result.get("moves", [])][:8],
        "mandates": [f"Every turn must exercise at least one of: {str(m)[:120]}"
                     for m in (result.get("moves") or [])[:2]],
        "prohibitions": [],
        "output_contract": ["method_applied", "licensed_moves_used", "claims"],
        "min_counts": {"licensed_moves_used": 1},
        "affinity": [],
        "status": "candidate",
        "parents": parents,
        "residual_moves": residual,
        "evidence": [str(s)[:400] for s in result.get("evidence_spans", [])][:6],
        "observed_in": sorted(observed & agents),
        "first_seen_run": coordination_id,
    }
    save_emergent_framework(spec)
    return spec


def promote_emergent(framework_id: str, reason: str = "applied and produced a concession",
                     path: Path | None = None) -> bool:
    """Graduate a candidate to assignable status once it proves load-bearing in use."""
    entries = load_emergent(path)
    for i, entry in enumerate(entries):
        if entry.get("id") != framework_id or entry.get("status") == "validated":
            continue
        entry["status"] = "validated"
        entry["validated_reason"] = reason
        entries[i] = entry
        (path or EMERGENT_CATALOGUE_PATH).write_text(
            json.dumps({"frameworks": entries, "schema_version": 1}, indent=2),
            encoding="utf-8",
        )
        return True
    return False


def record_candidate_application(framework_id: str, produced_concession: bool,
                                 path: Path | None = None) -> dict | None:
    """Track how often an emergent candidate was used and whether it ever bit.

    A candidate that is applied and produces a concession is promoted — that is the
    validation step that keeps emergence from being decorative.
    """
    entries = load_emergent(path)
    for i, entry in enumerate(entries):
        if entry.get("id") != framework_id:
            continue
        entry["applications"] = int(entry.get("applications", 0)) + 1
        entry["concessions_caused"] = int(entry.get("concessions_caused", 0)) + (1 if produced_concession else 0)
        entries[i] = entry
        (path or EMERGENT_CATALOGUE_PATH).write_text(
            json.dumps({"frameworks": entries, "schema_version": 1}, indent=2),
            encoding="utf-8",
        )
        if entry["concessions_caused"] >= 1 and entry["status"] == "candidate":
            promote_emergent(framework_id,
                             f"applied {entry['applications']}x, caused {entry['concessions_caused']} concession(s)",
                             path)
        return entry
    return None
