"""Friday's "consult Claude" offload.

When Friday's local model (qwen3:8b) hits a genuine dead end, she can ask the Anthropic API
(Claude Opus 4.8) for help — but ONLY after the user explicitly opts in on that turn. The
offer→consent gate lives in main.py; this module only performs the call, the fail-closed
budget accounting, secret scrubbing, and logging.

Security posture (from the adversarial review):
- The model cannot self-invoke: there is NO consult tool in TOOL_SCHEMAS/_DISPATCH. The only
  call site is main.py's gated branch, so qwen3:8b has nothing to emit and cannot reach Claude
  without a real human "yes" this turn.
- Hard no-op unless FRIDAY_CONSULT_ENABLED is truthy AND ANTHROPIC_API_KEY is set AND the
  anthropic SDK imports. When off, consult_available() is False and no offer is ever made.
- The API key is read only from the environment by the SDK; it is never in a payload, a reply,
  a log line, or the budget file.
- Data minimization + secret scrubbing: only the question + minimal caller-supplied context are
  sent, and both are run through a redactor that strips anything resembling a token/key/JWT.
- Budget guard is fail-CLOSED (review fix #1): if the ledger can't be read, parsed, OR its
  directory isn't writable (e.g. a lost bind-mount after redeploy), consults are REFUSED rather
  than proceeding with a spend counter that never accumulates.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

# ---- config (env-driven; safe defaults; feature OFF unless explicitly enabled) ----
_ENABLED = os.getenv("FRIDAY_CONSULT_ENABLED", "false").lower() in ("true", "1", "yes")
CONSULT_MODEL = os.getenv("FRIDAY_CONSULT_MODEL", "claude-opus-4-8")
CONSULT_EFFORT = os.getenv("FRIDAY_CONSULT_EFFORT", "high")  # low|medium|high|xhigh|max
# thinking tokens count against max_tokens and bill as OUTPUT — size for adaptive thinking
# plus a short spoken answer. ~$0.20 worst case at 8k output on Opus 4.8 ($25/1M output).
CONSULT_MAX_TOKENS = int(os.getenv("FRIDAY_CONSULT_MAX_TOKENS", "8000"))
CONSULT_TIMEOUT = float(os.getenv("FRIDAY_CONSULT_TIMEOUT", "90"))
MONTHLY_BUDGET_USD = float(os.getenv("FRIDAY_CONSULT_MONTHLY_BUDGET_USD", "5.0"))
BUDGET_FILE = os.getenv("FRIDAY_CONSULT_BUDGET_FILE", "/app/data/consult_budget.json")
LOG_FILE = os.getenv("FRIDAY_CONSULT_LOG", "/app/data/consult_log.jsonl")

# Opus 4.8 pricing, USD per 1M tokens (thinking tokens bill as output).
_PRICE_IN_PER_M = 5.0
_PRICE_OUT_PER_M = 25.0

_SYSTEM = (
    "You are Claude, being consulted by Friday, a small local voice assistant that got stuck. "
    "Give Friday one clear, correct, concise answer she can act on or relay. She speaks it aloud, "
    "so keep it plain, brief, and free of markdown — one to three sentences."
)

# Defense-in-depth: never forward anything resembling a token/key to Anthropic or the log,
# even if it slipped into conversation text (HA long-lived JWTs, sk-ant- keys, bearer headers).
_SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9_\-]+"
    r"|eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]+"   # JWT
    r"|Bearer\s+[A-Za-z0-9._\-]+"
    r"|Authorization:\s*\S+"
    r"|\b[A-Fa-f0-9]{32,}\b"                                          # long hex blobs
)


def _scrub(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text or "")


_sdk_ok = None


def _sdk() -> bool:
    """Lazy import so a missing anthropic package is a clean no-op, not a boot failure."""
    global _sdk_ok
    if _sdk_ok is None:
        try:
            import anthropic  # noqa: F401
            _sdk_ok = True
        except Exception:
            _sdk_ok = False
    return _sdk_ok


class _BudgetError(Exception):
    pass


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _ensure_ledger_writable() -> None:
    """Fail-CLOSED cornerstone: the spend guard is only meaningful if we can PERSIST spend.
    If the ledger dir is missing/unwritable (the realistic 'lost /app/data mount after redeploy'
    case, where a missing file would otherwise read as $0 forever), raise so consults refuse."""
    d = os.path.dirname(BUDGET_FILE) or "."
    if not os.path.isdir(d) or not os.access(d, os.W_OK):
        raise _BudgetError(f"budget ledger dir not writable: {d}")
    if os.path.exists(BUDGET_FILE) and not os.access(BUDGET_FILE, os.W_OK):
        raise _BudgetError(f"budget ledger file not writable: {BUDGET_FILE}")


def _read_budget():
    """Return (month_key, spent_usd). Raise _BudgetError if the ledger can't be persisted or
    parsed — a cost control that stops enforcing when its state file breaks is not a control."""
    _ensure_ledger_writable()
    mk = _month_key()
    if not os.path.exists(BUDGET_FILE):
        return mk, 0.0
    try:
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return mk, float(data.get(mk, 0.0))
    except Exception as e:
        raise _BudgetError(f"budget ledger unreadable/corrupt: {e}")


def _write_budget(mk: str, new_total: float) -> None:
    data = {}
    if os.path.exists(BUDGET_FILE):
        try:
            with open(BUDGET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[mk] = round(new_total, 6)
    tmp = BUDGET_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, BUDGET_FILE)  # atomic; last-writer-wins is fine for a single voice user


def _log(entry: dict) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:  # logging must never break the turn
        print(f"[friday-brain] consult log write failed: {e}", flush=True)


def consult_available() -> bool:
    """True only if fully armed: enabled + key present + SDK importable + this month's budget is
    persistable, readable, AND under cap. Fail-CLOSED on any ledger problem."""
    if not (_ENABLED and os.getenv("ANTHROPIC_API_KEY") and _sdk()):
        return False
    try:
        _, spent = _read_budget()
    except _BudgetError as e:
        print(f"[friday-brain] consult disabled (budget guard fail-closed): {e}", flush=True)
        return False
    return spent < MONTHLY_BUDGET_USD


async def consult_claude(question: str, context: str = "") -> str:
    """The ONE Anthropic call site. Returns a short, secret-scrubbed, spoken-friendly answer.
    Never raises to the caller — every failure path returns a plain spoken line and logs."""
    ts = datetime.now(timezone.utc).isoformat()
    base = {"ts": ts, "model": CONSULT_MODEL, "effort": CONSULT_EFFORT,
            "question": _scrub(question)[:500]}

    # Re-verify at the call site (not just at offer time): available + budget, both fail-closed.
    if not (_ENABLED and os.getenv("ANTHROPIC_API_KEY") and _sdk()):
        _log({**base, "outcome": "skipped_disabled"})
        return "I can't reach Claude right now."
    try:
        mk, spent = _read_budget()
    except _BudgetError as e:
        _log({**base, "outcome": "skipped_budget_guard"})
        print(f"[friday-brain] consult refused (budget guard): {e}", flush=True)
        return "I couldn't check my Claude budget, so I'll hold off."
    if spent >= MONTHLY_BUDGET_USD:
        _log({**base, "outcome": "skipped_budget", "month_to_date_usd": round(spent, 6)})
        return "I've used up this month's Claude budget."

    q = _scrub(question).strip()
    ctx = _scrub(context).strip()
    if not q:
        return "I'm not sure what to ask Claude — can you say that again?"
    user_content = q if not ctx else f"{q}\n\nRelevant context:\n{ctx}"

    t0 = time.time()
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(timeout=CONSULT_TIMEOUT)  # key read from env by SDK
        async with client.messages.stream(
            model=CONSULT_MODEL,
            max_tokens=CONSULT_MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": CONSULT_EFFORT},
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            msg = await stream.get_final_message()
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        _log({**base, "outcome": f"error:{type(e).__name__}", "latency_ms": latency_ms})
        print(f"[friday-brain] consult_claude {type(e).__name__}: {e}", flush=True)
        return "I couldn't reach Claude just now."

    latency_ms = int((time.time() - t0) * 1000)
    stop = getattr(msg, "stop_reason", None)
    if stop == "refusal":
        _log({**base, "outcome": "refusal", "latency_ms": latency_ms})
        return "Claude declined that one."

    # Answer = concatenated text blocks (thinking blocks carry empty text under display=omitted).
    answer = " ".join(
        b.text for b in getattr(msg, "content", [])
        if getattr(b, "type", "") == "text" and getattr(b, "text", "")
    ).strip()

    usage = getattr(msg, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    cost = in_tok / 1e6 * _PRICE_IN_PER_M + out_tok / 1e6 * _PRICE_OUT_PER_M
    new_total = spent + cost

    try:
        _write_budget(mk, new_total)
    except Exception as e:
        # We already incurred this cost; return the answer but flag that spend didn't persist.
        # The fail-closed READ guard will refuse the NEXT consult if the ledger stays broken.
        print(f"[friday-brain] consult budget WRITE FAILED (spend not persisted): {e}", flush=True)
        _log({**base, "outcome": "ok_budget_write_failed", "cost_usd": round(cost, 6),
              "input_tokens": in_tok, "output_tokens": out_tok, "latency_ms": latency_ms,
              "stop_reason": stop})
        return answer or "Claude didn't have a clear answer for that one."

    outcome = "ok" if stop != "max_tokens" else "ok_truncated"
    _log({**base, "outcome": outcome, "cost_usd": round(cost, 6), "input_tokens": in_tok,
          "output_tokens": out_tok, "month_to_date_usd": round(new_total, 6),
          "latency_ms": latency_ms, "stop_reason": stop})
    print(f"[friday-brain] consult_claude {outcome} tokens={in_tok}+{out_tok} "
          f"cost=${cost:.4f} mtd=${new_total:.4f}", flush=True)

    if stop == "max_tokens":
        return (answer + " That's as far as Claude got before running long.").strip()
    return answer or "Claude didn't have a clear answer for that one."
