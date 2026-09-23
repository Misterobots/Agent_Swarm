"""
Debate stage — framework-constrained collision between Collective agents.

Runs after Perspective Research Mode has produced its matrix. Each agent is a
persona from the research phase, equipped with an assigned thinking framework
(see frameworks.py), and the rounds are built so agents attack their most
incompatible counterpart rather than their nearest neighbour.

Every turn is audited against its framework's mandates and retried once on
violation. A turn that fails twice is kept but flagged — a silent pass would
report compliance that never happened.

Emits only event types already on the SSE allowlist (message/status/log/thought)
so no new UI plumbing is required to observe the stage.
"""

import json
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from typing import Generator

from logger_setup import setup_logger

from coordination.frameworks import (
    audit_turn,
    detect_emergent_framework,
    framework_prompt_block,
    load_catalogue,
    most_contested_partner,
    record_candidate_application,
    assign_frameworks,
    structured_llm_call,
)

logger = setup_logger("Lamport")

_MAX_FINDINGS_CHARS = 9000

_TURN_SCHEMA = {
    "type": "object",
    "required": ["claims", "reasoning"],
    "properties": {
        "reasoning": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "string"}},
        "licensed_moves_used": {"type": "array", "items": {"type": "string"}},
        "attacks": {"type": "array", "items": {
            "type": "object",
            "required": ["target", "move", "severity"],
            "properties": {
                "target": {"type": "string"},
                "move": {"type": "string"},
                "severity": {"type": "string", "enum": ["fatal", "serious", "notable"]},
            },
        }},
        "concessions": {"type": "array", "items": {
            "type": "object",
            "required": ["claim_relinquished", "conceded_to", "because_of_move"],
            "properties": {
                "claim_relinquished": {"type": "string"},
                "conceded_to": {"type": "string"},
                "because_of_move": {"type": "string"},
            },
        }},
        "confidence": {"type": "number"},
    },
}


def _brief(text, n: int = 160) -> str:
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= n else s[:n] + "…"


def _agent_system(agent: dict, framework_id: str, secondary_id: str | None,
                  catalogue: dict) -> str:
    pioneer_name = agent.get("pioneer_name") or agent.get("label", "Agent")
    full = agent.get("pioneer_full_name") or pioneer_name
    motto = agent.get("pioneer_motto") or ""
    fw_block = framework_prompt_block(framework_id, catalogue, secondary_id)
    return (
        f"You are {full}, the {agent.get('label', '')} agent in a structured multi-agent debate.\n"
        f'Motto: "{motto}"\n\n'
        f"Your persona gives you a vantage point. Your FRAMEWORK constrains your method — it "
        f"defines which moves you are licensed to make and what you are REQUIRED to produce. "
        f"The framework is not decoration: an auditor checks every turn against its mandates, "
        f"and a turn that fails is sent back to you.\n\n"
        f"{fw_block}\n\n"
        f"Respond with valid JSON matching the requested contract. Stay inside your framework's "
        f"licensed moves — an argument made outside them does not count as yours."
    )


def _generate_turn(system: str, instruction: str, model_name: str | None,
                   num_predict: int = 1200) -> dict | None:
    return structured_llm_call(
        instruction, _TURN_SCHEMA, model_name=model_name, system=system,
        temperature=0.6, num_predict=num_predict, timeout=180,
    )


def _audited_turn(*, system: str, instruction: str, framework_id: str, agent_name: str,
                  model_name: str | None, catalogue: dict) -> dict:
    """Generate one debate turn, audit it, retry once with violations named.

    Returns ``{"payload": dict|None, "violations": [str], "attempts": int, "compliant": bool}``.
    """
    payload = _generate_turn(system, instruction, model_name)
    if payload is None:
        return {"payload": None, "violations": ["generation failed"], "attempts": 1,
                "compliant": False, "agent": agent_name, "framework": framework_id}
    audit = audit_turn(framework_id, payload, model_name=model_name, catalogue=catalogue)
    attempts = 1
    if not audit["compliant"]:
        retry_instruction = (
            instruction
            + "\n\nYOUR PREVIOUS TURN WAS REJECTED BY THE FRAMEWORK AUDITOR.\n"
            + "Violations:\n"
            + "\n".join(f"  - {v}" for v in audit["violations"])
            + "\n\nCorrect the process and satisfy every mandate. Do not soften the mandate "
               "to fit your answer; do the work the framework demands."
        )
        payload2 = _generate_turn(system, retry_instruction, model_name)
        attempts = 2
        if payload2 is not None:
            audit2 = audit_turn(framework_id, payload2, model_name=model_name, catalogue=catalogue)
            payload, audit = payload2, audit2
    return {"payload": payload, "violations": audit["violations"], "attempts": attempts,
            "compliant": audit["compliant"], "agent": agent_name, "framework": framework_id,
            "audited_by": audit.get("audited_by", "")}


def _round_instruction(*, round_name: str, topic: str, focus: str, matrix_md: str,
                       agent: dict, roster: list[dict], turns: dict,
                       target_agent: dict | None, round_no: int) -> str:
    own_findings = (agent.get("findings") or "")[:_MAX_FINDINGS_CHARS]
    shared = ""
    if round_no >= 2:
        others = []
        for other in roster:
            label = other.get("label")
            if label == agent.get("label"):
                continue
            prior = turns.get(label, {})
            if not prior:
                continue
            others.append(
                f"--- {other.get('pioneer_name', label)} "
                f"[{other.get('framework_name', '')}] ---\n"
                f"Claims: {json.dumps(prior.get('claims', []), ensure_ascii=False)[:900]}\n"
                f"Attacks: {json.dumps(prior.get('attacks', []), ensure_ascii=False)[:700]}\n"
                f"Conceded: {json.dumps(prior.get('concessions', []), ensure_ascii=False)[:500]}"
            )
        if others:
            shared = "\n\nTHE OTHER AGENTS SO FAR:\n" + "\n".join(others)
    target = ""
    if target_agent is not None:
        tprior = turns.get(target_agent.get("label"), {})
        target = (
            f"\n\nYOUR ASSIGNED OPPONENT is {target_agent.get('pioneer_name')} "
            f"[{target_agent.get('framework_name')}], the agent whose framework is most "
            f"incompatible with yours. Their position:\n"
            f"Claims: {json.dumps(tprior.get('claims', []), ensure_ascii=False)[:1200]}\n"
            f"Reasoning: {str(tprior.get('reasoning', ''))[:1200]}\n"
        )

    if round_name == "positions":
        task = (
            "STATE YOUR POSITION. Advance your claims from your own research findings, under "
            "your framework's constraints. Fill every key your framework's output contract "
            "requires. You may not hedge into agreement — your framework exists to make you "
            "produce something the others cannot."
        )
    elif round_name == "collision":
        task = (
            "CROSS-EXAMINE your assigned opponent. Attack only with moves your framework "
            "licenses, and say which licensed move each attack used. An attack that would "
            "apply to anyone's argument is not an attack on this one."
        )
    elif round_name == "rebuttal":
        task = (
            "RESPOND TO WHAT WAS DONE TO YOU. Rebut the attacks that are answerable within "
            "your framework, and concede precisely what you cannot defeat — a concession must "
            "name the specific move that forced it. Then report any concession you extracted "
            "from others."
        )
    else:
        task = "FINAL POSITION after all exchange."
    return (
        f"DEBATE TOPIC: {topic}\n\n"
        f"FOCUS REQUESTED BY THE USER: {focus or 'resolve the contested points in the matrix'}\n\n"
        f"YOUR RESEARCH FINDINGS ({agent.get('label')}):\n{own_findings}\n\n"
        f"THE PERSPECTIVE MATRIX:\n{(matrix_md or '')[:4000]}"
        f"{shared}{target}\n\nROUND: {round_name.upper()}\n{task}\n\nReturn valid JSON only."
    )


def _turn_claims(payload: dict | None) -> list:
    return list((payload or {}).get("claims") or [])


def _turn_attacks(payload: dict | None) -> list:
    return list((payload or {}).get("attacks") or [])


def _turn_concessions(payload: dict | None) -> list:
    return list((payload or {}).get("concessions") or [])


def _parallel_round(*, agents: list[dict], systems: dict, instructions: dict,
                    frameworks: dict, model_name: str | None, catalogue: dict,
                    cancel_check) -> list[dict]:
    """Run one debate round; agents are independent within a round, so they overlap."""
    ordered = [a["label"] for a in agents]
    if cancel_check:
        cancel_check()
    results: dict[str, dict] = {}
    if len(ordered) == 1:
        label = ordered[0]
        results[label] = _audited_turn(
            system=systems[label], instruction=instructions[label],
            framework_id=frameworks[label], agent_name=label,
            model_name=model_name, catalogue=catalogue,
        )
        return [results[label]]

    with ThreadPoolExecutor(max_workers=min(len(ordered), 3)) as pool:
        futures = {
            pool.submit(
                _audited_turn, system=systems[label], instruction=instructions[label],
                framework_id=frameworks[label], agent_name=label,
                model_name=model_name, catalogue=catalogue,
            ): label
            for label in ordered
        }
        pending = set(futures)
        while pending:
            if cancel_check:
                cancel_check()
            done, pending = futures_wait(pending, timeout=30)
            if not done:
                continue
            for fut in done:
                label = futures[fut]
                try:
                    results[label] = fut.result()
                except Exception as e:
                    logger.warning(f"[Debate] turn for {label} failed: {e}")
                    results[label] = {"payload": None, "violations": [str(e)],
                                      "attempts": 0, "compliant": False, "agent": label,
                                      "framework": frameworks.get(label, "")}
    return [results[label] for label in ordered if label in results]


def run_debate(*, topic: str, focus: str, roster: list[dict], matrix_md: str = "",
               model_name: str | None = None, coordination_id: str = "",
               problem_type: str = "", rounds: int = 3,
               cancel_check=None, sink: dict | None = None) -> Generator[dict, None, None]:
    """Generator driving the debate. Yields message/status/log/thought events.

    ``roster`` entries need at minimum ``label``, ``role``, ``findings`` and the
    pioneer fields carried over from the research phase, so a debating agent is
    the same voice the user already read — not a new one.

    ``sink`` is filled in place: ``sink["markdown"]``, ``sink["transcript"]``,
    ``sink["emergent"]``, ``sink["assignments"]`` — matching the in-place
    ``result`` dict convention used by routing/gates.py.

    Rounds: 1 positions → 2 collision → 3 rebuttal/concession (+emergence).
    ``rounds=1`` gives positions only, which is the cheap probe path.
    """
    sink = sink if sink is not None else {}
    catalogue = load_catalogue()
    agents = [r for r in roster if r.get("label")][:6]
    if len(agents) < 2:
        yield {"type": "message",
               "content": "⚠️ **Debate needs at least 2 agents** — the perspective findings "
                          "from the previous run could not be recovered.\n\n"}
        sink["markdown"] = ""
        return

    yield {"type": "status", "content": "🥊 Assigning thinking frameworks..."}
    assignments = assign_frameworks(agents, problem_type=problem_type,
                                    model_name=model_name, catalogue=catalogue)
    by_label = {a["perspective_label"]: a for a in assignments}
    for agent in agents:
        a = by_label.get(agent["label"], {})
        agent["framework"] = a.get("primary")
        agent["framework_name"] = a.get("primary_name", a.get("primary", ""))
        agent["framework_family"] = a.get("primary_family", "")
        agent["framework_secondary"] = a.get("secondary")
    assigned_ids = [a.get("framework", "") for a in agents]

    yield {
        "type": "message",
        "content": (
            "**🧠 Framework Assignment** — constraints, not costumes\n\n"
            + "\n".join(
                f"- **{a.get('pioneer_name', a['label'])}** ({a['label']}) → "
                f"`{a['framework']}` [{a['framework_family']}]"
                + (f" + `{a['framework_secondary']}`" if a.get("framework_secondary") else "")
                for a in agents
            )
            + "\n\nEach agent's turn is audited against its framework's mandates.\n\n"
        ),
    }
    yield {"type": "log", "content": f"[Debate] {len(agents)} agents, {rounds} round(s)"}

    partner_index = {
        a["label"]: most_contested_partner(i, assigned_ids, catalogue)
        for i, a in enumerate(agents)
    }
    systems = {
        a["label"]: _agent_system(a, a["framework"], a.get("framework_secondary"), catalogue)
        for a in agents
    }
    turns: dict[str, dict] = {}
    transcripts: list[dict] = []
    concessions: list[dict] = []
    violations: list[dict] = []
    round_names = ["positions", "collision", "rebuttal", "final"][:max(1, min(rounds, 4))]

    for r_no, round_name in enumerate(round_names, start=1):
        yield {"type": "thought", "content": f"→ Debate round {r_no}/{len(round_names)}: {round_name}"}
        yield {"type": "status", "content": f"🗣️ Round {r_no} — {round_name.title()}"}
        instructions = {
            a["label"]: _round_instruction(
                round_name=round_name, topic=topic, focus=focus, matrix_md=matrix_md,
                agent=a, roster=agents, turns=turns,
                target_agent=(
                    agents[partner_index[a["label"]]]
                    if round_name == "collision" and partner_index.get(a["label"]) is not None
                    else None
                ),
                round_no=r_no,
            )
            for a in agents
        }
        results = _parallel_round(
            agents=agents, systems=systems, instructions=instructions,
            frameworks={a["label"]: a["framework"] for a in agents},
            model_name=model_name, catalogue=catalogue, cancel_check=cancel_check,
        )
        for agent in agents:
            res = next((x for x in results if x["agent"] == agent["label"]), None)
            if res is None:
                continue
            payload = res["payload"] or {}
            turns[agent["label"]] = {
                "reasoning": payload.get("reasoning", ""),
                "claims": _turn_claims(payload),
                "attacks": _turn_attacks(payload),
                "concessions": _turn_concessions(payload),
                "compliant": res["compliant"],
                "framework": agent["framework"],
                "round": r_no,
            }
            transcripts.append({
                "agent": agent["label"], "round": r_no,
                "framework": f"{agent['framework']}[{agent['framework_family']}]",
                "text": (json.dumps(payload, ensure_ascii=False)
                         if payload else res.get("violations", ["no output"])[0]),
            })
            for c in turns[agent["label"]]["concessions"]:
                if isinstance(c, dict) and str(c.get("claim_relinquished", "")).strip():
                    concessions.append({
                        "by": agent.get("pioneer_name", agent["label"]),
                        "relinquished": _brief(c.get("claim_relinquished"), 200),
                        "conceded_to": _brief(c.get("conceded_to"), 80),
                        "move": _brief(c.get("because_of_move"), 200),
                        "round": r_no,
                    })
            if not res["compliant"]:
                violations.append({
                    "agent": agent.get("pioneer_name", agent["label"]),
                    "framework": agent["framework"], "round": r_no,
                    "violations": res["violations"],
                })
            yield {
                "type": "message",
                "content": (
                    f"### R{r_no} · {agent.get('pioneer_name', agent['label'])} "
                    f"_( {agent['framework']} )_\n\n"
                    + (f"{payload.get('reasoning', '').strip()}\n\n" if payload.get("reasoning") else "")
                    + ("".join(f"- {c}\n" for c in _turn_claims(payload)[:6]) or "")
                    + ("**Concessions**\n\n" + "".join(
                        f"- `{_brief(c.get('claim_relinquished'), 120)}` → "
                        f"{_brief(c.get('because_of_move'), 120)}\n"
                        for c in _turn_concessions(payload) if isinstance(c, dict)
                    ) if _turn_concessions(payload) else "")
                    + ("" if res["compliant"] else
                       f"\n> ⚠️ Framework audit failed even after retry: "
                       f"{'; '.join(res['violations'])}\n")
                    + "\n"
                ),
            }

    emergent = None
    if len(round_names) >= 2:
        yield {"type": "status", "content": "🧬 Checking for frameworks that emerged from collision..."}
        try:
            emergent = detect_emergent_framework(
                transcripts, assigned_ids, concessions,
                model_name=model_name, coordination_id=coordination_id, catalogue=catalogue,
            )
        except Exception as e:
            logger.warning(f"[Debate] emergence detection failed: {e}")
        if emergent:
            yield {
                "type": "message",
                "content": (
                    f"**🧬 Emergent framework candidate: `{emergent['id']}`** — {emergent['name']}\n\n"
                    f"{emergent['summary']}\n\n"
                    f"Parents: {', '.join(emergent['parents'])} · observed in "
                    f"{', '.join(emergent['observed_in'])}\n"
                    f"Recorded as a *candidate*; it becomes assignable only after a later run "
                    f"applies it and it produces a concession.\n\n"
                ),
            }
            for agent in agents:
                if agent.get("framework") == emergent["id"]:
                    record_candidate_application(emergent["id"], bool(concessions))
        else:
            yield {"type": "log", "content": "[Debate] no emergent framework qualified this round"}

    yield {"type": "status", "content": "⚖️ Adjudicating..."}
    verdict = _adjudicate(topic=topic, focus=focus, agents=agents, turns=turns,
                          concessions=concessions, model_name=model_name)

    markdown = render_debate_markdown(
        topic=topic, focus=focus, agents=agents, turns=turns, concessions=concessions,
        violations=violations, emergent=emergent, verdict=verdict, partner_index=partner_index,
    )
    sink["markdown"] = markdown
    sink["transcript"] = transcripts
    sink["emergent"] = emergent
    sink["assignments"] = assignments
    sink["concessions"] = concessions
    sink["violations"] = violations
    yield {"type": "log", "content": f"[Debate] complete: {len(concessions)} concession(s), "
                                     f"{len(violations)} audit failure(s)"}


def _adjudicate(*, topic: str, focus: str, agents: list[dict], turns: dict,
                concessions: list[dict], model_name: str | None) -> dict:
    """Judge what actually survived, weighted by which claims were audited-compliant."""
    schema = {
        "type": "object",
        "required": ["settled", "still_contested", "verdict", "confidence", "next_probe"],
        "properties": {
            "settled": {"type": "array", "items": {"type": "string"}},
            "still_contested": {"type": "array", "items": {"type": "string"}},
            "verdict": {"type": "string"},
            "confidence": {"type": "number"},
            "next_probe": {"type": "array", "items": {"type": "string"}},
        },
    }
    roll = "\n\n".join(
        f"=== {a.get('pioneer_name', a['label'])} [{a['framework']},"
        f" compliance={'PASS' if turns.get(a['label'], {}).get('compliant') else 'FAIL'}] ===\n"
        f"Claims: {json.dumps(turns.get(a['label'], {}).get('claims', []), ensure_ascii=False)[:1200]}\n"
        f"Reasoning: {str(turns.get(a['label'], {}).get('reasoning', ''))[:1200]}"
        for a in agents
    )
    prompt = (
        f"A multi-agent debate finished. Adjudicate on the merits.\n\n"
        f"TOPIC: {topic}\nFOCUS: {focus or 'the contested points'}\n\n"
        f"CONCESSIONS RECORDED:\n{json.dumps(concessions, ensure_ascii=False)[:3000]}\n\n"
        f"{roll}\n\n"
        f"Rules: a claim from an agent whose framework audit FAILED carries less weight than a "
        f"compliant agent's claim. A concession is evidence the conceding agent changed its "
        f"position — count it. List what is genuinely settled versus what remains contested, and "
        f"give next_probe as concrete things worth investigating further. Return valid JSON only."
    )
    result = structured_llm_call(prompt, schema, model_name=model_name,
                                 system="You are an impartial adjudicator of a structured debate.",
                                 temperature=0.2, num_predict=1000)
    return result if isinstance(result, dict) else {
        "settled": [], "still_contested": [],
        "verdict": "Adjudication unavailable — the exchange is presented without a verdict.",
        "confidence": 0.0, "next_probe": [],
    }


def render_debate_markdown(*, topic: str, focus: str, agents: list[dict], turns: dict,
                           concessions: list[dict], violations: list[dict],
                           emergent: dict | None, verdict: dict,
                           partner_index: dict) -> str:
    """Markdown brief for the debate, delivered through the existing response channel."""
    parts: list[str] = [
        "## ⚔️ Framework Debate\n\n",
        f"**Topic:** {topic}\n\n",
    ]
    if focus:
        parts.append(f"**Focus:** {focus}\n\n")

    parts.append("### Frameworks assigned\n\n| Agent | Lens | Framework | Family | Cross-examined |\n|---|---|---|---|---|\n")
    for i, a in enumerate(agents):
        pi = partner_index.get(a["label"])
        opponent = agents[pi].get("pioneer_name", agents[pi]["label"]) if pi is not None else "—"
        parts.append(
            f"| {a.get('pioneer_name', a['label'])} | {a['label']} | `{a['framework']}` | "
            f"{a['framework_family']} | {opponent} |\n"
        )

    parts.append("\n### What moved\n\n")
    if concessions:
        parts.append("| Relinquished by | Claim | Forced by |\n|---|---|---|\n")
        for c in concessions[:12]:
            parts.append(f"| {c['by']} | {c['relinquished']} | {c['move']} |\n")
    else:
        parts.append("_No agent conceded anything. Either the positions were never in "
                     "genuine contact, or the frameworks did not bite hard enough — treat "
                     "the absence of movement as a finding, not a clean result._\n")

    parts.append("\n### Positions after exchange\n\n")
    for a in agents:
        t = turns.get(a["label"], {})
        flag = "" if t.get("compliant") else " ⚠️ _audit failed_"
        parts.append(
            f"- **{a.get('pioneer_name', a['label'])}** (`{a['framework']}`){flag}: "
            f"{_brief('; '.join(str(c) for c in t.get('claims', [])), 400) or '_no claims recorded_'}\n"
        )

    parts.append("\n### Adjudication\n\n")
    parts.append(f"{verdict.get('verdict', '')}\n\n")
    settled = verdict.get("settled") or []
    contested = verdict.get("still_contested") or []
    if settled:
        parts.append("**Settled**\n\n" + "".join(f"- {s}\n" for s in settled[:8]) + "\n")
    if contested:
        parts.append("**Still contested**\n\n" + "".join(f"- {s}\n" for s in contested[:8]) + "\n")
    probes = verdict.get("next_probe") or []
    if probes:
        parts.append("**Worth digging into**\n\n" + "".join(f"- {p}\n" for p in probes[:6]) + "\n")

    if emergent:
        parts.append(
            "\n### 🧬 Emergent framework\n\n"
            f"`{emergent['id']}` — **{emergent['name']}** ({emergent['family']} family)\n\n"
            f"{emergent['summary']}\n\n"
            f"Licensed moves:\n\n"
            + "".join(f"- {m}\n" for m in emergent.get("moves", []))
            + f"\nGrew out of: {', '.join(emergent.get('parents', []))} · "
              f"observed in {', '.join(emergent.get('observed_in', []))} · "
              f"status: **{emergent.get('status', 'candidate')}**\n"
        )

    if violations:
        parts.append("\n### Framework compliance failures\n\n")
        for v in violations[:10]:
            parts.append(f"- **{v['agent']}** (`{v['framework']}`, round {v['round']}): "
                         f"{'; '.join(str(x)[:120] for x in v['violations'])}\n")
        parts.append("\n_Those turns are included above but carry less weight in the "
                     "adjudication._\n")

    return "".join(parts)
