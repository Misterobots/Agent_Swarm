"""
code_gateway — an OpenAI-compatible front end over Ollama's NATIVE /api/chat.

Why this exists (2026-09-13): coding agents that speak OpenAI (Qwen Code, and anything
else pointed at an OpenAI base_url) cannot talk to Ollama's own /v1/chat/completions
reliably.  Four separate upstream defects bite at once, and all four are fixed here by
translating OpenAI -> /api/chat instead of using /v1 at all:

  1. qwen-code #9438 (OPEN) — after a tool call, Qwen Code rebuilds the follow-up request
     with only system+assistant roles and DROPS the original user turn.  Ollama's chat
     template requires a user turn, so it answers HTTP 500 "no user query found in
     messages".  Every tool-using prompt (@file, file exploration, multi-step work) dies.
     Fixed by _ensure_user_turn() below.

  2. ollama #17825 (OPEN) — on qwen3.8, once a request has failed with a tool-call parse
     500, re-submitting the IDENTICAL request hangs forever: no response, no logs, no slot
     activity, until the runner is recycled.  Qwen Code retries failures every ~400ms, so
     defect 1 feeds straight into this one and wedges a runner holding ~16 GB of VRAM.
     On WDDM that needs a container restart to reclaim.  Fixed by _PoisonGuard below.

  3. ollama #14958 (OPEN) — on /v1 with a large system prompt (~1600+ tokens), tool_calls
     come back empty.  Ollama's streaming also drops tool_calls deltas.  Qwen Code's system
     prompt is far past that.  Fixed by forcing stream:false upstream whenever tools are
     present, then re-emitting as SSE so the client still sees the stream it asked for.

  4. think:false is honoured on /api/chat but ignored for Qwen3-family models on /v1, and
     Qwen3.8's enable_thinking/reasoning_effort ride on chat_template_kwargs which Ollama's
     compat layer does not forward.  Leaving reasoning on cost Friday 3-16s per turn and
     once produced a hallucinated entity_id instead of a clarifying question
     (see services/friday_brain/main.py::_ollama_chat).  Fixed by sending think:false.

Bonus: /v1 has no num_ctx field (OpenAI's schema has none), so an OpenAI client cannot
raise the context window and silently runs at the server default.  Going through /api/chat
lets us inject options.num_ctx per request — no Modelfile variants needed.

Memex itself does NOT need this service: agents/ already calls /api/chat directly via Agno
and was never affected by any of the above.  This is for the OpenAI-speaking clients.
"""

import asyncio
import contextlib
import hashlib
import json
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

# --- Config ----------------------------------------------------------------------------
# Default target is the shared swarm Ollama (ollama_gpu, GPU 0).  Override to ollama_friday
# or a host IP as needed.  Container DNS works because we join execution_net.
OLLAMA_URL = os.getenv("CODE_GATEWAY_OLLAMA_URL", "http://ollama:11434").rstrip("/")

# num_ctx per model.  JSON object, model tag -> int.  Anything not listed uses DEFAULT.
# This is the ONLY place the context window is set for OpenAI clients — they cannot send it.
_NUM_CTX_MAP: dict[str, int] = json.loads(os.getenv("CODE_GATEWAY_NUM_CTX_MAP", "{}"))
NUM_CTX_DEFAULT = int(os.getenv("CODE_GATEWAY_NUM_CTX", "32768"))

# think:false by default.  Set CODE_GATEWAY_THINK=true to let the model reason, or pass
# "reasoning_effort" on the request to override per call.
THINK_DEFAULT = os.getenv("CODE_GATEWAY_THINK", "false").lower() in ("1", "true", "yes")

KEEP_ALIVE = os.getenv("CODE_GATEWAY_KEEP_ALIVE", "1h")
# A dense 27B at ~20-25 tok/s on a long prompt blows past ordinary client defaults.
LLM_TIMEOUT = float(os.getenv("CODE_GATEWAY_TIMEOUT", "900"))
NUM_PREDICT = int(os.getenv("CODE_GATEWAY_NUM_PREDICT", "-1"))

# Seconds to remember a failed request signature.  See _PoisonGuard.
POISON_TTL = float(os.getenv("CODE_GATEWAY_POISON_TTL", "90"))


def _log(msg: str) -> None:
    print(f"[code-gateway] {msg}", flush=True)


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    _log(f"up — ollama={OLLAMA_URL} think={THINK_DEFAULT} num_ctx_default={NUM_CTX_DEFAULT} "
         f"num_ctx_map={_NUM_CTX_MAP or '{}'}")
    yield


app = FastAPI(title="code_gateway", lifespan=_lifespan)


# --- Fix 1: qwen-code #9438, the dropped user turn ---------------------------------------
# We cannot recover content the client never sent, so we remember the last user turn we DID
# see, keyed by a hash of the conversation's system prompt.  Qwen Code uses one system prompt
# per session, so this reassociates correctly for a single session per prompt.  Two concurrent
# sessions sharing an identical system prompt would collide; the consequence is a slightly
# stale user turn rather than a 500, and the placeholder covers a cold start.
_USER_TURN_CACHE: dict[str, str] = {}
_USER_TURN_CACHE_MAX = 64

PLACEHOLDER_USER = os.getenv(
    "CODE_GATEWAY_PLACEHOLDER_USER",
    "Continue the task using the tool results above.",
)


def _system_key(messages: list[dict]) -> str:
    sys_text = "\n".join(
        _flatten_content(m.get("content")) for m in messages if m.get("role") == "system"
    )
    return hashlib.sha256(sys_text.encode("utf-8", "replace")).hexdigest()


def _ensure_user_turn(messages: list[dict]) -> tuple[list[dict], bool]:
    """Guarantee at least one user turn.  Returns (messages, repaired)."""
    key = _system_key(messages)
    last_user = next(
        (_flatten_content(m.get("content")) for m in reversed(messages) if m.get("role") == "user"),
        None,
    )
    if last_user:
        # Healthy request — record it so we can repair the follow-up that drops it.
        if len(_USER_TURN_CACHE) >= _USER_TURN_CACHE_MAX:
            _USER_TURN_CACHE.pop(next(iter(_USER_TURN_CACHE)))
        _USER_TURN_CACHE[key] = last_user
        return messages, False

    recovered = _USER_TURN_CACHE.get(key) or PLACEHOLDER_USER
    source = "cached" if key in _USER_TURN_CACHE else "placeholder"
    _log(f"qwen-code #9438 repair: no user turn in {len(messages)} messages; injected {source}")

    # Insert immediately after the leading system block, where the original turn belonged.
    idx = 0
    while idx < len(messages) and messages[idx].get("role") == "system":
        idx += 1
    return messages[:idx] + [{"role": "user", "content": recovered}] + messages[idx:], True


# --- Fix 2: ollama #17825, the poisoned retry ---------------------------------------------
class _PoisonGuard:
    """Remember request signatures that just failed upstream.

    On qwen3.8 a re-submitted identical request after a 500 deadlocks the runner permanently.
    Qwen Code retries in ~400ms bursts, so without this the first tool-parse failure takes the
    whole model offline.  We answer the repeat ourselves with a 503+Retry-After instead of forwarding
    it, which keeps the runner alive and gives the client something actionable.
    """

    def __init__(self) -> None:
        self._failed: dict[str, float] = {}

    @staticmethod
    def signature(model: str, messages: list[dict], tools: Any) -> str:
        blob = json.dumps(
            {"m": model, "msgs": messages, "t": tools}, sort_keys=True, default=str
        )
        return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()

    def _sweep(self) -> None:
        now = time.monotonic()
        for sig, ts in list(self._failed.items()):
            if now - ts > POISON_TTL:
                self._failed.pop(sig, None)

    def is_poisoned(self, sig: str) -> bool:
        self._sweep()
        return sig in self._failed

    @staticmethod
    def should_poison(status: int, body: str, has_tools: bool) -> bool:
        """Only block retries of a genuinely #17825-shaped failure.

        Observed 2026-09-13 on a live qwen3.8 session: at a 64k prompt llama.cpp saves ~2.5 GiB
        of prompt-cache state and 360 MiB context checkpoints, and requests intermittently 500
        under that pressure — then RECOVER on their own a minute later. Poisoning those turned a
        transient blip into a hard 90s outage and blocked a retry that would have succeeded.

        #17825 is narrower: a tool-call PARSE failure, after which the identical request deadlocks
        the runner. So require tools in play and a parse-shaped error before blocking anything.
        Everything else (memory pressure, timeouts, template errors) is left retryable — the cost
        of being wrong that way is one slow request, not a wedged runner.
        """
        if status != 500 or not has_tools:
            return False
        low = (body or "").lower()
        return any(k in low for k in ("parse", "tool call", "tool_call", "unmarshal", "invalid character"))

    def mark(self, sig: str) -> None:
        self._sweep()
        self._failed[sig] = time.monotonic()

    def clear(self, sig: str) -> None:
        self._failed.pop(sig, None)


_poison = _PoisonGuard()


# --- Message translation ------------------------------------------------------------------
def _flatten_content(content: Any) -> str:
    """OpenAI allows content as a list of typed parts; Ollama wants a string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


def _extract_images(content: Any) -> list[str]:
    """Pull base64 image payloads out of OpenAI multimodal content.

    OpenAI sends images as content parts: {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}
    Ollama's /api/chat instead wants a sibling "images": ["<raw base64>"] on the message, WITHOUT
    the data: prefix. Without this translation the images are silently dropped and the model
    answers as if it were blind — which is worse than an error, because the reply looks fine.

    qwen3.8:27b reports capabilities ['completion','vision','tools','thinking'] and loads a CLIP
    vision encoder, so this path is live for it.
    """
    if not isinstance(content, list):
        return []
    images: list[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            continue
        url = (part.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            # data:image/png;base64,AAAA -> AAAA
            _, _, b64 = url.partition(",")
            if b64:
                images.append(b64)
        elif url:
            # Ollama needs bytes, not a URL. Fetching remote URLs server-side would be an SSRF
            # vector, so refuse loudly rather than quietly sending a blind request.
            _log(f"WARNING: dropping non-data image URL ({url[:60]!r}); "
                 "send images as base64 data: URIs")
    return images


def _tool_name_for_id(messages: list[dict], call_id: str) -> str:
    """Ollama's /api/chat identifies a tool result by tool_name; OpenAI uses tool_call_id.
    Resolve by scanning back for the assistant turn that issued that id."""
    for msg in reversed(messages):
        for call in msg.get("tool_calls") or []:
            if call.get("id") == call_id:
                return (call.get("function") or {}).get("name", "") or ""
    return ""


def _to_ollama_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            out.append({
                "role": "tool",
                "content": _flatten_content(msg.get("content")),
                "tool_name": msg.get("name") or _tool_name_for_id(messages, msg.get("tool_call_id", "")),
            })
            continue

        converted: dict[str, Any] = {"role": role, "content": _flatten_content(msg.get("content"))}
        if images := _extract_images(msg.get("content")):
            converted["images"] = images
        if msg.get("tool_calls"):
            calls = []
            for call in msg["tool_calls"]:
                fn = call.get("function") or {}
                args = fn.get("arguments")
                # OpenAI sends arguments as a JSON *string*; Ollama wants a real object.
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        _log(f"unparseable tool arguments for {fn.get('name')!r}; forwarding as raw")
                        args = {"_raw": args}
                calls.append({"function": {"name": fn.get("name", ""), "arguments": args or {}}})
            converted["tool_calls"] = calls
        out.append(converted)
    return out


def _to_openai_tool_calls(ollama_calls: list[dict] | None) -> list[dict]:
    calls = []
    for call in ollama_calls or []:
        fn = call.get("function") or {}
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {
                "name": fn.get("name", ""),
                # OpenAI clients expect a JSON string here, not an object.
                "arguments": json.dumps(fn.get("arguments") or {}),
            },
        })
    return calls


_FINISH = {"stop": "stop", "length": "length"}


def _build_payload(body: dict, messages: list[dict], stream: bool) -> dict:
    model = body.get("model", "")
    options: dict[str, Any] = {"num_ctx": _NUM_CTX_MAP.get(model, NUM_CTX_DEFAULT)}

    # Modelfile sampling params are dropped on /v1 (ollama #17744); we are on /api/chat, but
    # forward whatever the client set so A/B runs stay comparable.
    if body.get("temperature") is not None:
        options["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        options["top_p"] = body["top_p"]
    if (max_tokens := body.get("max_tokens") or body.get("max_completion_tokens")) is not None:
        options["num_predict"] = max_tokens
    elif NUM_PREDICT != -1:
        options["num_predict"] = NUM_PREDICT

    think: Any = THINK_DEFAULT
    if (effort := body.get("reasoning_effort")) is not None:
        think = False if effort in ("none", "minimal") else effort

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "think": think,
        "keep_alive": KEEP_ALIVE,
        "options": options,
    }
    if body.get("tools"):
        payload["tools"] = body["tools"]
    return payload


def _openai_response(model: str, data: dict) -> dict:
    message = data.get("message") or {}
    tool_calls = _to_openai_tool_calls(message.get("tool_calls"))

    if (thinking := message.get("thinking")):
        _log(f"WARNING: {len(thinking)} chars of reasoning returned despite think:false; discarded")

    out_message: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
    if tool_calls:
        out_message["tool_calls"] = tool_calls

    prompt_tokens = data.get("prompt_eval_count", 0) or 0
    completion_tokens = data.get("eval_count", 0) or 0
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": out_message,
            "finish_reason": "tool_calls" if tool_calls else _FINISH.get(data.get("done_reason", "stop"), "stop"),
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _sse(chunk: dict) -> bytes:
    return f"data: {json.dumps(chunk)}\n\n".encode()


def _chunk(cid: str, model: str, delta: dict, finish: str | None = None) -> dict:
    return {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


# --- Endpoints -----------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
        return {"status": "ok", "ollama": OLLAMA_URL, "models": len(r.json().get("models", []))}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "ollama": OLLAMA_URL, "error": str(e)}


@app.get("/v1/models")
async def list_models() -> dict:
    """Qwen Code and most OpenAI clients probe this on startup."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
        tags = r.json().get("models", [])
    return {
        "object": "list",
        "data": [
            {"id": m["name"], "object": "model", "created": int(time.time()), "owned_by": "ollama"}
            for m in tags
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "")
    wants_stream = bool(body.get("stream"))
    has_tools = bool(body.get("tools"))

    messages, repaired = _ensure_user_turn(list(body.get("messages") or []))
    ollama_messages = _to_ollama_messages(messages)

    sig = _PoisonGuard.signature(model, ollama_messages, body.get("tools"))
    if _poison.is_poisoned(sig):
        # Forwarding this would deadlock the runner (ollama #17825).  Refuse loudly instead.
        _log(f"BLOCKED poisoned retry for {model} (ollama #17825); returned 503+Retry-After without forwarding")
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": str(int(POISON_TTL))},
            content={"error": {
                "message": (
                    "code_gateway refused an identical retry of a request that just failed "
                    "upstream. Re-sending it would hang the Ollama runner permanently "
                    "(ollama #17825). Change the prompt or wait "
                    f"{int(POISON_TTL)}s."
                ),
                "type": "poisoned_retry_blocked",
                "code": "code_gateway_17825",
            }},
        )

    # Tools + streaming loses tool_calls deltas (ollama #14958 and Ollama's streaming tool
    # handling generally).  Call upstream non-streamed, then re-emit as SSE if asked.
    upstream_stream = wants_stream and not has_tools
    payload = _build_payload(body, ollama_messages, upstream_stream)

    if repaired:
        _log(f"repaired request for {model} (tools={has_tools}, stream={wants_stream})")

    if upstream_stream:
        return StreamingResponse(
            _stream_upstream(payload, model, sig),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as c:
            r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
            if r.status_code >= 500:
                body = r.text[:500]
                # Log the body: without it a 500 is undiagnosable after the fact, which is exactly
                # what happened on 2026-09-13 when memory-pressure 500s looked like #17825.
                if _PoisonGuard.should_poison(r.status_code, body, has_tools):
                    _poison.mark(sig)
                    _log(f"upstream {r.status_code} for {model} looks like ollama #17825 "
                         f"(tool-call parse); blocking identical retries. body={body!r}")
                else:
                    _log(f"upstream {r.status_code} for {model}; RETRYABLE (not #17825-shaped). "
                         f"body={body!r}")
                return JSONResponse(status_code=r.status_code, content={"error": {
                    "message": f"Ollama returned {r.status_code}: {body}",
                    "type": "upstream_error",
                }})
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        # Deliberately NOT poisoned: a timeout means slow, not wedged. Blocking the retry of a
        # long-running generation would be self-inflicted damage.
        _log(f"upstream TIMEOUT after {LLM_TIMEOUT}s for {model} (retryable)")
        return JSONResponse(status_code=504, content={"error": {
            "message": f"Ollama did not respond within {LLM_TIMEOUT}s.", "type": "upstream_timeout",
        }})

    _poison.clear(sig)
    result = _openai_response(model, data)

    if not wants_stream:
        return JSONResponse(content=result)

    # Client asked for a stream but tools forced a non-streamed upstream call: hand the
    # finished message back in the SSE shape the client expects.
    async def replay():
        cid = result["id"]
        msg = result["choices"][0]["message"]
        yield _sse(_chunk(cid, model, {"role": "assistant"}))
        if msg.get("content"):
            yield _sse(_chunk(cid, model, {"content": msg["content"]}))
        if msg.get("tool_calls"):
            for i, call in enumerate(msg["tool_calls"]):
                yield _sse(_chunk(cid, model, {"tool_calls": [{"index": i, **call}]}))
        yield _sse(_chunk(cid, model, {}, result["choices"][0]["finish_reason"]))
        yield b"data: [DONE]\n\n"

    return StreamingResponse(replay(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _stream_upstream(payload: dict, model: str, sig: str):
    """Translate Ollama's NDJSON stream into OpenAI SSE chunks. Tool-free path only."""
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    first = True
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as c:
            async with c.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
                if r.status_code >= 400:
                    await r.aread()
                    # The streaming path is only taken when there are NO tools, so a failure here
                    # cannot be the #17825 tool-parse case. Never poison it.
                    _log(f"stream upstream {r.status_code} for {model} (retryable)")
                    yield _sse({"error": {"message": f"Ollama returned {r.status_code}",
                                          "type": "upstream_error"}})
                    yield b"data: [DONE]\n\n"
                    return

                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if first:
                        yield _sse(_chunk(cid, model, {"role": "assistant"}))
                        first = False

                    message = data.get("message") or {}
                    if content := message.get("content"):
                        yield _sse(_chunk(cid, model, {"content": content}))

                    if data.get("done"):
                        finish = _FINISH.get(data.get("done_reason", "stop"), "stop")
                        yield _sse(_chunk(cid, model, {}, finish))
                        yield b"data: [DONE]\n\n"
                        _poison.clear(sig)
                        return
    except (httpx.TimeoutException, asyncio.TimeoutError):
        _log(f"stream TIMEOUT after {LLM_TIMEOUT}s for {model} (retryable)")
        yield _sse({"error": {"message": "upstream timeout", "type": "upstream_timeout"}})
        yield b"data: [DONE]\n\n"

