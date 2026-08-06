---
title: "Troubleshooting: Agent Runtime"
---

# Agent Runtime Troubleshooting

## Runtime Won't Start

**Symptom**: Container exits immediately or fails health check.

**Diagnose**:

```bash
docker logs agent-runtime --tail 50
```

**Common causes**:

- Missing environment variables in `network.env`
- Port conflict on 8000
- Python import errors (missing dependencies)

**Fix**:

- Verify `network.env` has all required variables
- Rebuild the image: `docker compose build agent-runtime`
- Check for syntax errors in agent code

---

## Intent Misclassification

**Symptom**: Messages routed to wrong agent (e.g., "draw a cat" goes to general chat).

**Diagnose**:

Check Langfuse traces for the intent classification scores.

**Fix**:

1. Add better examples to `agents/intent_capabilities.py`
2. Try a larger router model
3. Adjust confidence thresholds in the Router

---

## Response Timeout

**Symptom**: Chat hangs or returns timeout error.

**Diagnose**:

```bash
# Check if Ollama is responsive
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags

# Check agent runtime logs
docker logs agent-runtime --tail 20
```

**Fix**:

1. Increase `STREAM_TIMEOUT` in agent configuration
2. Check Ollama health and restart if needed
3. A very large context may cause slow responses — reduce history

---

## MarsRL Verification Loop

**Symptom**: Response takes very long, logs show multiple "Verifier: FAIL" entries.

**Fix**:

1. Reduce `max_iter` in MarsRL config (try 1 instead of 2)
2. Lower `pass_threshold` (try 0.50 instead of 0.70)
3. Check if the verifier model is the right size for the task

### Loop Hangs Indefinitely ("Solver is generating...")

**Symptom**: Status shows "Solver is generating..." with no progress.

A **stream timeout** is logged when the solver stream produces no tokens for 60 seconds — the loop then breaks and returns whatever it has. This is usually GPU memory pressure.

**Diagnose**:

```bash
# Query Loki for stream timeout messages
curl -s 'http://{{ hopper_ip }}:3100/loki/api/v1/query_range?query=%7Bcontainer%3D%22agent_runtime%22%7D%20%7C~%20%22stream%20idle%22' | python -m json.tool
```

**Fix**: Reduce the number of active models or restart Ollama to relieve VRAM pressure.

---

## Chat Returns Empty or "Solver Failed"

**Symptom**: Response is empty, or chat shows `Solver failed: ...`.

**Diagnose**:

```bash
docker logs ollama --tail 30

# Check which model is currently loaded
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/ps

# Confirm the expected model is pulled
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags | python -m json.tool
```

**Common causes**:

| Cause | Fix |
|-------|-----|
| Expected model not pulled | `docker exec ollama ollama pull <model>` |
| VRAM OOM — model evicted mid-request | Reduce `OLLAMA_KEEP_ALIVE`, restart Ollama |
| Training runtime holds the GPU mutex | Wait for training to finish, or `docker compose stop training-runtime` |
| Secondary/fast-path Ollama host used but the model isn't loaded there | Pull the model on that host specifically, e.g. `docker exec ollama-turing ollama pull <model>` |

---

## Memory/Context Issues

**Symptom**: Agent doesn't remember previous messages in conversation.

**Check**:

- Session ID is being passed correctly
- Context window isn't exceeded
- Memory system (PostgreSQL + pgvector) is healthy


