"""BMO Brain — the canonical conversational brain for both Home Assistant and the Pi
voice satellite (Tier-1 vault-grounded, Tier-2 tool-using).

Takes a transcribed question and produces the answer text, speaking as BMO/Beemo. It
recalls relevant memories from the personal vault, injects them as context, and asks
the LLM to answer in character.

OpenAI-compatible and Ollama-native-compatible, so Home Assistant's "Control Home
Assistant" feature and the BMO Pi's bmo_driver.chat() both use it unchanged.

Two tool-calling modes, both via the shared `_answer()`:
  - Passthrough: caller supplies its own `tools` array (HA's "Control Home Assistant"
    feature does this) — forwarded to Ollama verbatim, any tool_calls propagated back
    UNEXECUTED. HA owns entity resolution/execution/authorization via its own opt-in
    entity-exposure list; bmo_brain never needs its own device-authorization layer here.
  - Self-executing: caller supplies no `tools` (e.g. the Pi driver) — bmo_brain offers
    its own tool set (tools.py: weather/time/news/web search/device control), executes
    any tool_calls itself, and loops until the model produces final text. Callers with
    no way to execute a tool call (like the Pi driver) never see one.
Delegating "build / research" requests to agent_runtime's swarm/coordinate pipeline is
a separate, still-unwired Tier-2 capability.

Personal values (vault URL / owner) come from env — nothing personal is baked into the
shared repo; the shim is inert for vault recall unless VAULT_URL + VAULT_OWNER are set.
"""
import asyncio
import datetime
import json
import os
import re
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from persona import BMO_SYSTEM_PROMPT
from tools import TOOL_SCHEMAS, call_tool

VAULT_URL       = os.getenv("VAULT_URL", "").rstrip("/")
VAULT_OWNER     = os.getenv("VAULT_OWNER", "")
VAULT_LIMIT     = int(os.getenv("VAULT_LIMIT", "6"))
VAULT_MIN_SCORE = float(os.getenv("VAULT_MIN_SCORE", "0.4"))
VAULT_TIMEOUT   = float(os.getenv("VAULT_TIMEOUT", "12"))

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://192.168.2.101:11434").rstrip("/")
MODEL       = os.getenv("BMO_MODEL", "qwen3:8b")
MODEL_NAME  = os.getenv("BMO_MODEL_NAME", "bmo")
LLM_TIMEOUT = float(os.getenv("BMO_LLM_TIMEOUT", "150"))
TEMPERATURE = float(os.getenv("BMO_TEMPERATURE", "0.5"))
SELF_TOOL_MAX_ROUNDS = int(os.getenv("BMO_SELF_TOOL_MAX_ROUNDS", "6"))

# Full override still available for testing/experimentation via BMO_PERSONA.
PERSONA = os.getenv("BMO_PERSONA", BMO_SYSTEM_PROMPT)

app = FastAPI(title="BMO Brain (vault-RAG assistant)")


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL, "vault": bool(VAULT_URL and VAULT_OWNER), "ollama": OLLAMA_URL}


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "bmo"}]}


async def _vault_recall(query: str):
    """Return a list of recalled memory strings for the query (empty on any failure)."""
    if not (VAULT_URL and VAULT_OWNER and query):
        return []
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            r = await c.post(f"{VAULT_URL}/v1/memories/search",
                             json={"query": query, "owner_id": VAULT_OWNER, "limit": VAULT_LIMIT})
        if r.status_code == 200:
            return [m["content"] for m in r.json() if float(m.get("score") or 0) >= VAULT_MIN_SCORE]
        print(f"[bmo-brain] vault search HTTP {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] vault recall failed: {e}", flush=True)
    return []


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


_STATUS_RE = re.compile(
    r"\b(status|health|healthy|degraded|online|offline|operational|reachable|uptime)\b"
    r"|is (it|the [\w .'-]+?) (up|running|online|down|working)"
    r"|are (they|the [\w .'-]+?) (up|running|online)",
    re.IGNORECASE,
)


def _is_status_question(text: str) -> bool:
    return bool(_STATUS_RE.search(text or ""))


async def _live_status() -> str:
    """Probe live health of the vault stack + Ollama; return a short status block.

    BMO otherwise answers status questions from (historical) memories. This gives it
    CURRENT ground truth for "is X up / what's the status" questions.
    """
    checks = []
    async with httpx.AsyncClient(timeout=8.0) as c:
        if VAULT_URL:
            try:
                r = await c.get(f"{VAULT_URL}/health")
                ok = r.status_code == 200 and "ok" in r.text.lower()
                checks.append(f"- Vault API: {'healthy' if ok else f'PROBLEM (HTTP {r.status_code})'}")
            except Exception as e:  # noqa: BLE001
                checks.append(f"- Vault API: UNREACHABLE ({type(e).__name__})")
            try:
                r = await c.post(f"{VAULT_URL}/v1/memories/search",
                                 json={"query": "status", "owner_id": VAULT_OWNER, "limit": 1})
                checks.append(f"- Vault search (Postgres + embeddings): {'working' if r.status_code == 200 else f'FAILING (HTTP {r.status_code})'}")
            except Exception as e:  # noqa: BLE001
                checks.append(f"- Vault search (Postgres + embeddings): FAILING ({type(e).__name__})")
        try:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            checks.append(f"- Ollama (embeddings + BMO model): {'up' if r.status_code == 200 else f'PROBLEM (HTTP {r.status_code})'}")
        except Exception as e:  # noqa: BLE001
            checks.append(f"- Ollama: DOWN ({type(e).__name__})")
    return "\n".join(checks) if checks else "(no live checks configured)"


async def _ollama_chat(messages: list, tools=None):
    """One raw call to Ollama's /api/chat. Returns (text, tool_calls) — tool_calls is
    Ollama's native shape (list of {"function": {"name", "arguments"}}) or None."""
    payload = {"model": MODEL, "messages": messages, "stream": False,
               "options": {"temperature": TEMPERATURE}}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as c:
        r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
        r.raise_for_status()
        message = r.json().get("message", {})
    text = _strip_think(message.get("content", "") or "")
    tool_calls = message.get("tool_calls") or None
    return text, tool_calls


async def _self_execute_tools(messages: list):
    """Offer bmo_brain's own tool set (tools.py), executing any tool_calls server-side
    and looping until the model produces a final text-only response. Used only when the
    caller supplied no `tools` of its own — see _answer()'s docstring. Always returns
    tool_calls=None: a caller with no `tools` array has no way to execute one itself.
    """
    convo = list(messages)
    for _round in range(SELF_TOOL_MAX_ROUNDS):
        text, tool_calls = await _ollama_chat(convo, TOOL_SCHEMAS)
        if not tool_calls:
            return text, None
        convo.append({"role": "assistant", "content": text, "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            result = await call_tool(name, args)
            print(f"[bmo-brain] self-executed tool={name} args={args} -> {result[:120]!r}", flush=True)
            convo.append({"role": "tool", "content": result})
    print(f"[bmo-brain] self-executing tool loop exhausted {SELF_TOOL_MAX_ROUNDS} rounds "
          f"without a final answer", flush=True)
    return "Beemo tried a few things there but could not finish that one. Try asking again?", None


async def _store_memory(user_text: str, response_text: str):
    """Fire-and-forget: store the exchange back to the vault. Non-fatal on any failure —
    inert (like _vault_recall) unless VAULT_URL + VAULT_OWNER are set."""
    if not (VAULT_URL and VAULT_OWNER and user_text and response_text):
        return
    try:
        async with httpx.AsyncClient(timeout=VAULT_TIMEOUT) as c:
            await c.post(f"{VAULT_URL}/v1/extract",
                         json={"conversation": f"User: {user_text}\nBMO: {response_text}",
                               "owner_id": VAULT_OWNER})
    except Exception as e:  # noqa: BLE001
        print(f"[bmo-brain] memory store failed (non-fatal): {e}", flush=True)


async def _answer(client_messages, tools=None):
    """Recall vault context, build the BMO prompt, call the LLM, return (text, tool_calls).

    `tools`, when supplied by the caller, is forwarded to Ollama verbatim (OpenAI-style
    function-calling schema) and any tool_calls are propagated back UNEXECUTED —
    passthrough mode, e.g. HA's "Control Home Assistant" feature, which owns entity
    resolution/execution/authorization itself. When the caller supplies no `tools`,
    bmo_brain offers its own tool set (tools.py) and executes any tool_calls itself,
    looping until the model produces a final text-only response — self-executing mode,
    e.g. the Pi driver, which has no way to execute a tool call itself. tool_calls in the
    return value is always None in self-executing mode.
    """
    # Keep tool-result turns (role "tool") and the assistant's own prior tool_calls turn
    # (content is empty when it emits tool_calls) so multi-round tool-calling loops — e.g.
    # HA retrying entity resolution after a failed target — carry forward instead of
    # silently resetting to the original prompt on every round.
    convo = [m for m in client_messages
             if m.get("role") in ("user", "assistant", "tool")
             and (m.get("content") or m.get("tool_calls"))]
    last_user = next((m["content"] for m in reversed(convo) if m.get("role") == "user"), "")
    mems = await _vault_recall(last_user)
    ctx = ("\n".join(f"- {c}" for c in mems)
           if mems else "(no specific vault memories matched this question)")
    parts = [PERSONA]
    status_q = _is_status_question(last_user)
    if status_q:
        live = await _live_status()
        parts.append("LIVE SYSTEM STATUS — probed just now. Treat this as CURRENT ground truth "
                     "and base any status/health answer on THIS, not on recalled memories:\n" + live)
    parts.append(
        "Beemo has access to a personal memory vault (also called MemPalace) — facts about "
        "your user, their projects, and their infrastructure. If asked whether Beemo has a "
        "vault or MemPalace, the answer is yes; below is whatever it recalled for this "
        "question specifically:\n" + ctx
    )
    parts.append("/no_think")
    system = "\n\n".join(parts)
    messages = [{"role": "system", "content": system}] + convo

    if tools:
        text, tool_calls = await _ollama_chat(messages, tools)
    else:
        text, tool_calls = await _self_execute_tools(messages)

    if not text and not tool_calls:
        text = "(no response)"
    print(f"[bmo-brain] memories={len(mems)} status_probe={status_q} "
          f"tool_calls={len(tool_calls) if tool_calls else 0} answer_chars={len(text)}", flush=True)
    asyncio.create_task(_store_memory(last_user, text))
    return text, tool_calls


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    client_messages = body.get("messages", [])
    stream = bool(body.get("stream", False))
    model = body.get("model") or MODEL_NAME
    tools = body.get("tools")
    cid = "chatcmpl-bmo-" + uuid.uuid4().hex[:12]
    created = int(time.time())

    tool_calls = None
    try:
        text, tool_calls = await _answer(client_messages, tools=tools)
    except Exception as e:  # noqa: BLE001
        text = f"(BMO brain error: {e})"
        print(f"[bmo-brain] ERROR: {type(e).__name__}: {e}", flush=True)

    # Ollama's tool_calls.function.arguments is a parsed object; OpenAI's is a JSON string.
    openai_tool_calls = None
    if tool_calls:
        openai_tool_calls = [{
            "id": "call_" + uuid.uuid4().hex[:12],
            "type": "function",
            "function": {
                "name": tc.get("function", {}).get("name", ""),
                "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
            },
        } for tc in tool_calls]
        print(f"[bmo-brain] emitting tool_calls={[tc['function']['name'] for tc in openai_tool_calls]}", flush=True)
    finish_reason = "tool_calls" if openai_tool_calls else "stop"

    if stream:
        async def gen():
            if openai_tool_calls:
                yield ("data: " + json.dumps({
                    "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0,
                                 "delta": {"role": "assistant", "tool_calls": openai_tool_calls},
                                 "finish_reason": None}],
                }) + "\n\n")
            else:
                for delta in ({"role": "assistant"}, {"content": text}):
                    yield ("data: " + json.dumps({
                        "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                    }) + "\n\n")
            yield ("data: " + json.dumps({
                "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            }) + "\n\n")
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    message = {"role": "assistant", "content": None if openai_tool_calls else text}
    if openai_tool_calls:
        message["tool_calls"] = openai_tool_calls

    return JSONResponse({
        "id": cid, "object": "chat.completion", "created": created, "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


# ---------------------------------------------------------------------------
# Ollama-compatible surface — lets Home Assistant's native (no-HACS) Ollama
# integration use this shim as a local "model" by URL. Same vault-RAG core.
# ---------------------------------------------------------------------------
def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@app.get("/api/version")
async def ollama_version():
    return {"version": "0.5.0"}


@app.get("/api/tags")
async def ollama_tags():
    return {"models": [{
        "name": f"{MODEL_NAME}:latest", "model": f"{MODEL_NAME}:latest",
        "modified_at": _now_iso(), "size": 0, "digest": "bmo",
        "details": {"parent_model": "", "format": "gguf", "family": "bmo",
                    "families": ["bmo"], "parameter_size": "8B", "quantization_level": ""},
    }]}


@app.post("/api/show")
async def ollama_show(req: Request):
    # HA probes model capabilities here during setup; "tools" must be advertised for HA
    # to offer "Control Home Assistant" tool-calling for this model.
    return {
        "license": "", "modelfile": "", "parameters": "", "template": "{{ .Prompt }}",
        "details": {"parent_model": "", "format": "gguf", "family": "bmo",
                    "families": ["bmo"], "parameter_size": "8B", "quantization_level": ""},
        "model_info": {}, "capabilities": ["completion", "tools"],
    }


@app.post("/api/chat")
async def ollama_chat(req: Request):
    body = await req.json()
    messages = body.get("messages", [])
    stream = body.get("stream", True)
    model = body.get("model") or f"{MODEL_NAME}:latest"
    tools = body.get("tools")
    now = _now_iso()
    tool_calls = None
    try:
        text, tool_calls = await _answer(messages, tools=tools)
    except Exception as e:  # noqa: BLE001
        text = f"(BMO brain error: {e})"
        print(f"[bmo-brain] /api/chat ERROR: {type(e).__name__}: {e}", flush=True)

    if tool_calls:
        print(f"[bmo-brain] /api/chat emitting tool_calls="
              f"{[tc.get('function', {}).get('name') for tc in tool_calls]}", flush=True)

    # Ollama's native tool_calls shape is passed through verbatim — HA's native Ollama
    # integration talks to this endpoint directly, so no translation is needed.
    message_body = {"role": "assistant", "content": text}
    if tool_calls:
        message_body["tool_calls"] = tool_calls

    if stream:
        async def gen():
            yield json.dumps({"model": model, "created_at": now,
                              "message": message_body, "done": False}) + "\n"
            yield json.dumps({"model": model, "created_at": _now_iso(),
                              "message": {"role": "assistant", "content": ""},
                              "done": True, "done_reason": "stop"}) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    return JSONResponse({"model": model, "created_at": now,
                         "message": message_body,
                         "done": True, "done_reason": "stop"})
