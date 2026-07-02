"""BMO Brain — Tier-1 vault-grounded conversational assistant (OpenAI-compatible).

The "brain" stage of the voice pipeline: takes a transcribed question and produces the
answer text. It is a clean, purpose-built personal assistant (NOT the agent_runtime dev
router): it recalls relevant memories from the personal vault, injects them as context,
and asks the LLM to answer in BMO's persona — concise, conversational, spoken-friendly.

OpenAI-compatible so Home Assistant's "OpenAI Conversation" agent and the BMO Pi's
bmo_driver.chat() can both use it unchanged.

Tier-2, first slice: HA device control via tool-calling passthrough. When a caller
sends a "tools" array, it's forwarded to Ollama verbatim; any tool_calls Ollama
returns are propagated instead of collapsed to text, so HA's own "Control Home
Assistant" feature can execute them against entities it has chosen to expose.
Delegating "build / research" requests to agent_runtime's swarm/coordinate
pipeline is a separate, still-unwired Tier-2 capability.

Personal values (vault URL / owner) come from env — nothing personal is baked into the
shared repo; the shim is inert for vault recall unless VAULT_URL + VAULT_OWNER are set.
"""
import datetime
import json
import os
import re
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

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

# The assistant currently goes by "Claude" (after Claude Shannon). The BMO persona will
# be layered onto this pipeline later; nothing personal is baked into the default.
ASSISTANT_NAME = os.getenv("BMO_ASSISTANT_NAME", "Claude")
OWNER_NAME     = os.getenv("BMO_OWNER_NAME", "your user")

_NAME_ORIGIN = " (named after Claude Shannon)" if ASSISTANT_NAME == "Claude" else ""
PERSONA = os.getenv("BMO_PERSONA", (
    f"You are {ASSISTANT_NAME}{_NAME_ORIGIN} — a warm, concise personal AI "
    f"assistant for {OWNER_NAME}'s home lab. You have access to a private memory vault; the "
    "memories below are the source of truth about your user, their projects, their "
    "infrastructure, and their recent work. Ground your answers in them. If they don't cover "
    "the question, answer from general knowledge and briefly say so. Reply in plain spoken "
    "prose — this is read aloud — so no markdown, no bullet lists, no code blocks; usually "
    "one to three sentences unless more detail is clearly needed. Speak directly to your user."
))

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


async def _answer(client_messages, tools=None):
    """Recall vault context, build the BMO prompt, call the LLM, return (text, tool_calls).

    `tools` is forwarded to Ollama verbatim (OpenAI-style function-calling schema) when
    the caller supplies one — e.g. HA's "Control Home Assistant" feature. tool_calls is
    Ollama's native shape (list of {"function": {"name", "arguments"}}) or None.
    """
    convo = [m for m in client_messages if m.get("role") in ("user", "assistant") and m.get("content")]
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
    parts.append("Recalled memories from the personal vault:\n" + ctx)
    parts.append("/no_think")
    system = "\n\n".join(parts)
    messages = [{"role": "system", "content": system}] + convo

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
    if not text and not tool_calls:
        text = "(no response)"
    print(f"[bmo-brain] memories={len(mems)} status_probe={status_q} "
          f"tool_calls={len(tool_calls) if tool_calls else 0} answer_chars={len(text)}", flush=True)
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
        print(f"[bmo-brain] ERROR: {e}", flush=True)

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
        print(f"[bmo-brain] /api/chat ERROR: {e}", flush=True)

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
