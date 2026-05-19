# Sparse Attention Upgrade — Pre-Flight Checklist

**Date:** 2026-05-06
**ADR Reference:** `docs/decisions/ADR-005_sparse_attention_retrieval.md`
**Baseline Evidence:** `docs/evidence/sparse_attention_proposal_2026_05_06.md`
**Target:** Phases 1–4 sequential deployment

---

## Pre-Flight: All Phases

Run these checks before starting any phase.

### Environment Health

- [ ] Hopper MemPalace is healthy:
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 "curl -s http://localhost:8200/health"
  ```
  Expected: `{"status":"ok","service":"mempalace"}`

- [ ] Lovelace Ollama is healthy (embedding model available):
  ```powershell
  Invoke-RestMethod http://192.168.2.101:11434/api/tags | Select-Object -ExpandProperty models | Where-Object { $_.name -like "*nomic*" }
  ```
  Expected: `nomic-embed-text` entry present

- [ ] `agent_runtime` container is running on Turing:
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.103 "docker ps --filter name=agent_runtime --format '{{.Status}}'"
  ```
  Expected: `Up ...`

- [ ] Workspace is clean, current HEAD noted:
  ```powershell
  git status ; git rev-parse HEAD
  ```

### Schema Confirmation (run on Hopper)

- [ ] `Memory` table has `domain`, `access_count`, and `created_at` columns:
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "docker exec postgres psql -U mempalace -d mempalace -c `"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='mempalace' AND table_name='memories' AND column_name IN ('domain','access_count','created_at') ORDER BY column_name;`""
  ```
  Expected: 3 rows returned

---

## Phase 1 Pre-Flight — Intent Domain Filter

**Files changed:** `agents/church.py`
**Restart needed:** `docker restart agent_runtime` on Turing

- [ ] Confirm intent is fully resolved before the MemPalace POST block by checking execution order:
  intent override block ends at ~line 1346; MemPalace recall block starts at ~line 1027 but
  executes after routing (inside `chat_swarm()` generator flow — routing resolves at ~line 1265,
  overrides at ~lines 1274–1346, MemPalace recall at ~lines 1027–1050 in declared order but
  reached after routing in execution flow). **Verify** by adding a temporary log line before the
  POST to print `intent` and confirming it is the final overridden value.

- [ ] Confirm which `domain` values currently exist in the database (so the map covers real data):
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "docker exec postgres psql -U mempalace -d mempalace -c `"SELECT domain, COUNT(*) FROM mempalace.memories GROUP BY domain ORDER BY COUNT(*) DESC;`""
  ```

- [ ] Verify `SearchQuery.domain` filter passes through to SQL by sending a test request:
  ```powershell
  Invoke-RestMethod -Method POST http://192.168.2.102:8200/v1/memories/search `
    -ContentType "application/json" `
    -Body '{"query":"test","domain":"nonexistent_domain_xyz","limit":5}'
  ```
  Expected: empty array `[]` (proves filter is active)

---

## Phase 2 Pre-Flight — Composite Scoring

**Files changed:** `control_plane/mempalace/app/main.py`
**Restart needed:** `docker restart mempalace` on Hopper

- [ ] Confirm `access_count` is being incremented (not stuck at 0):
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "docker exec postgres psql -U mempalace -d mempalace -c `"SELECT content, access_count, created_at FROM mempalace.memories ORDER BY access_count DESC LIMIT 5;`""
  ```
  Expected: at least some rows with `access_count > 0`

- [ ] Confirm `created_at` is populated for existing memories (same query, verify non-NULL timestamps)

- [ ] Note: adding `min_score` to `SearchQuery` is backward-compatible (Optional field with no
  default enforcement). The existing caller-side `score > 0.5` in `church.py` line 1039 can be
  replaced by passing `"min_score": 0.3` in the POST body after Phase 2 is deployed.

- [ ] Verify composite score formula does not break existing tests:
  ```powershell
  cd C:\Users\panca\Documents\Github\Agent_Swarm
  python -m pytest tests/ -q -k "mempalace" 2>&1 | Select-Object -Last 10
  ```

---

## Phase 3 Pre-Flight — Cross-Encoder Re-Ranker

**Files changed:** `control_plane/mempalace/app/reranker.py` (new), `main.py`, `requirements.txt`, `Dockerfile`; `agents/church.py`
**Restart needed:** Full rebuild and redeploy of `mempalace` on Hopper + `docker restart agent_runtime` on Turing

- [ ] Confirm Hopper has internet access for model download (model is ~90 MB):
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "curl -s -o /dev/null -w '%{http_code}' https://huggingface.co"
  ```
  Expected: `200` or `301`

- [ ] Check available disk on Hopper (need ~500 MB free for model + image layer):
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "df -h /var/lib/docker | tail -1"
  ```

- [ ] Confirm Python version in MemPalace container supports `sentence-transformers`:
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "docker exec mempalace python --version"
  ```
  Expected: Python 3.10 or higher

- [ ] Confirm CPU-only PyTorch is available (cross-encoder runs on CPU — no GPU needed on Hopper):
  ```powershell
  & "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 `
    "docker exec mempalace python -c 'import torch; print(torch.__version__)'"
  ```
  If PyTorch is absent, `sentence-transformers` will pull it automatically during `pip install`.

- [ ] Rollback path confirmed: `rerank=False` is the `SearchQuery` default. If re-ranker causes
  issues after deployment, setting `"rerank": False` (or omitting it) in the `church.py` POST
  payload immediately disables it — **no Hopper rebuild required for rollback**.

---

## Phase 4 Pre-Flight — Context Budget Manager

**Files changed:** `agents/context_budget.py` (new), `agents/church.py`
**Restart needed:** `docker restart agent_runtime` on Turing

- [ ] Confirm `CONTEXT_WINDOWS` values in `agents/config.py` match all currently deployed models:
  ```powershell
  Get-Content agents\config.py | Select-String -Pattern "CONTEXT_WINDOWS" -Context 0,15
  ```
  Verify each key matches an actual model name returned by:
  ```powershell
  (Invoke-RestMethod http://192.168.2.101:11434/api/tags).models.name
  ```

- [ ] Identify `active_model` variable name used per intent in `church.py` — the `ContextBudget`
  constructor must receive the same model name string used for the actual inference call.
  Check that model names in `config.py` (`ARCHITECT_MODEL`, `CODER_MODEL`, etc.) match
  `CONTEXT_WINDOWS` keys exactly (case-sensitive).

- [ ] Confirm `history` list structure is consistent dicts before `trim_history()` is applied:
  ```powershell
  # Search for any place history items might be non-dict objects
  Select-String -Path agents\church.py -Pattern "history\.append" | Select-Object -First 10
  ```

- [ ] Test `trim_history()` locally with a synthetic long history before deploying:
  ```python
  from agents.context_budget import trim_history, ContextBudget
  history = [{"role": "system", "content": "You are helpful."}]
  history += [{"role": "user" if i%2==0 else "assistant", "content": "x" * 500} for i in range(100)]
  budget = ContextBudget("qwen3:14b")
  trimmed = trim_history(history, budget.history_budget)
  assert trimmed[0]["role"] == "system", "System message must survive trim"
  print(f"Trimmed {len(history)} → {len(trimmed)} messages  PASS")
  ```

---

## Deployment Order and Restart Commands

```
Phase 1 (church.py only)
  → docker restart agent_runtime on Turing

Phase 2 (mempalace main.py)
  → docker restart mempalace on Hopper

Phase 3 (reranker.py + requirements.txt + Dockerfile)
  → on Hopper: docker compose build mempalace && docker compose up -d mempalace
  → docker restart agent_runtime on Turing (for church.py change)

Phase 4 (context_budget.py + church.py)
  → docker restart agent_runtime on Turing
```

**Restart commands (from Lovelace):**

```powershell
# Restart agent_runtime on Turing
& "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.103 "docker restart agent_runtime"

# Restart mempalace on Hopper
& "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 "cd /home/misterobots/Agent_Swarm/control_plane && docker compose restart mempalace"

# Full rebuild of mempalace on Hopper (Phase 3 only)
& "C:\Windows\System32\OpenSSH\ssh.exe" -o StrictHostKeyChecking=no -o BatchMode=yes misterobots@192.168.2.102 "cd /home/misterobots/Agent_Swarm/control_plane && docker compose build mempalace && docker compose up -d mempalace"
```

---

## Rollback Plan

| Phase | Rollback Action | Rebuild? |
|-------|----------------|---------|
| 1 | Remove `domain=` from church.py POST payload → restart agent_runtime | No |
| 2 | Revert `search_memories()` scoring to `1.0 - dist` → restart mempalace | No |
| 3 | Set `"rerank": False` in church.py POST payload → restart agent_runtime | No |
| 4 | Remove `trim_history()` call from church.py → restart agent_runtime | No |

All phases are independently revertible. No database migrations are involved.
