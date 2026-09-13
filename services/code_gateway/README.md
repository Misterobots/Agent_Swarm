# code_gateway

OpenAI-compatible front end over Ollama's **native `/api/chat`**, for coding agents that
speak OpenAI (Qwen Code, and anything else you point at an OpenAI `base_url`).

Memex's own `agents/` do **not** need this — they call `/api/chat` directly through Agno and
were never affected by any of the defects below.

## Why not just use Ollama's own `/v1`?

Four open upstream defects, all avoided by never touching `/v1`:

| Defect | Symptom | Fix here |
|---|---|---|
| [qwen-code #9438](https://github.com/QwenLM/qwen-code/issues/9438) | After a tool call, Qwen Code drops the user turn; Ollama answers `500 no user query found in messages`. Kills `@file`, exploration, all multi-step work. | `_ensure_user_turn()` re-injects it |
| [ollama #17825](https://github.com/ollama/ollama/issues/17825) | On qwen3.8, retrying an identical request after a 500 deadlocks the runner **permanently** until recycle. Qwen Code retries every ~400ms, so #9438 feeds straight into it. | `_PoisonGuard` answers the repeat with 409 instead of forwarding |
| [ollama #14958](https://github.com/ollama/ollama/issues/14958) | Large system prompts (~1600+ tokens) return empty `tool_calls` on `/v1`; streaming drops tool-call deltas. | forces `stream:false` upstream when tools are present, re-emits as SSE |
| `think:false` ignored on `/v1` for Qwen3-family | Reasoning tax — cost Friday 3–16s/turn and once produced a hallucinated `entity_id` instead of a clarifying question | sends `think:false` on `/api/chat`, where it works |

**Plus the reason this is load-bearing:** OpenAI's schema has no `num_ctx` field, so an
OpenAI client *cannot* set the context window — it silently runs at the server default.
Going through `/api/chat` lets the gateway inject `options.num_ctx` per request, which is
why no Modelfile variants are needed.

## Config

| Env | Default | Notes |
|---|---|---|
| `CODE_GATEWAY_OLLAMA_URL` | `http://ollama:11434` | Target Ollama. Container DNS on `execution_net`. |
| `CODE_GATEWAY_NUM_CTX_MAP` | `{}` | JSON, model tag → num_ctx. **The only place the window is set for OpenAI clients.** |
| `CODE_GATEWAY_NUM_CTX` | `32768` | Fallback for unmapped models. |
| `CODE_GATEWAY_THINK` | `false` | Per-request override via `reasoning_effort`. |
| `CODE_GATEWAY_KEEP_ALIVE` | `1h` | |
| `CODE_GATEWAY_TIMEOUT` | `900` | A dense 27B on a long prompt exceeds ordinary client defaults. |
| `CODE_GATEWAY_POISON_TTL` | `90` | How long a failed signature stays blocked. |

Keep `num_ctx` values **in sync** with each client's own context accounting
(`generationConfig.contextWindowSize` in Qwen Code). If the client thinks it has more room
than the server allocated, it packs prompts past the window and you get silent truncation.

For **Qwen3.8-27B specifically**, keep it under **~129,864 tokens** —
[llama.cpp #27756](https://github.com/ggml-org/llama.cpp/issues/27756) (open) makes the model
emit an instant EOS with no error above that, as per-layer error accumulates across its 48
Gated DeltaNet layers.

## Endpoints

- `POST /v1/chat/completions` — streaming and non-streaming, tools supported
- `GET /v1/models` — proxies `/api/tags`
- `GET /health` — reports Ollama reachability and model count

## Tests

```
python -m pytest tests/test_code_gateway.py
```

Pure translation logic, no network. Each test names the defect it guards.
