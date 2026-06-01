# Agents Runtime — Coordination Notes

This directory hosts the Memex agent runtime (FastAPI, single process). Multiple
agents may be working in parallel worktrees. **Read this before editing.**

---

## ⚠️ Don't touch `main.py` (except for one-line router mounts)

`agents/main.py` is ~5,300 lines and the highest-contention file in the repo.
**Do not add new endpoints to it.** Add a new router module instead:

1. Create `agents/{your_feature}/{__init__.py, routes.py}` with a
   `router = APIRouter(prefix="/v1/...")`
2. Add **one line** to `main.py` (find the "Goals router" block as a model):
   ```python
   try:
       from your_feature.routes import router as your_feature_router
       app.include_router(your_feature_router)
   except Exception as _e:
       _logging.getLogger("main").warning(f"Your feature router not loaded: {_e}")
   ```

After the one-line registration, all logic lives in your module — no further
`main.py` edits required.

### Existing routers to model after

| Module | Prefix | Notes |
|--------|--------|-------|
| `goals/routes.py` | `/v1/goals` | Reference implementation |
| `dev_sessions/routes.py` | `/v1/dev/sessions` | ⚙️ stub — implement task F1 |
| `dev_files/routes.py` | `/v1/dev/files` | ⚙️ stub — implement task F2 |
| `dev_projects/routes.py` | `/v1/dev/projects` | ⚙️ stub — implement task F3 |

---

## Identity convention

Authentik forward-auth headers are set by the gateway and forwarded by the
Next.js proxy. **Never require callers to set these manually.**

| Header | Use |
|--------|-----|
| `x-authentik-uid` | Stable user id — use for DB scoping (preferred) |
| `x-authentik-username` | Display name fallback |
| `x-authentik-groups` | Comma-separated; check for admin gates |
| `x-authentik-email` | Email |
| `x-authentik-name` | Full display name |

Use the `_owner(request)` helper pattern from `goals/routes.py` for consistent
UID resolution. **Cross-UID access must return 404, not 403** — avoid
disclosing existence of other users' resources.

---

## Dev sandbox file operations

`dev_sandbox` is a Docker container holding per-user project directories under
`/workspace/{uid}/{project_id}/`. Use the helper in `dev_files/docker_exec.py`:

```python
from dev_files.docker_exec import exec_in_sandbox, exec_in_project

result = exec_in_project(uid, project_id, "git status -b --porcelain")
```

**Security rules (enforced in `docker_exec.py` — do not bypass):**
- All paths are normalized and checked for `..` traversal before exec
- Absolute paths in `path` params are rejected with `400`
- Max file read/write size: 5 MB
- Binary files are base64-encoded in responses

---

## Database migrations

Schema changes go in `agents/migrations/` following the existing numbered
pattern (e.g. `0042_*.sql`). The Postgres connection is configured via
`DATABASE_URL`; default Saltbox password is `password4321` unless overridden
by the `postgres_role_docker_env_password` Saltbox var.

---

## GPU arbitration

If your endpoint runs any model inference, request a lock via the existing
`request_lock(context="text"|"image"|"vision")` pattern before calling Ollama
or ComfyUI. GPUs are shared across handlers via a Redis mutex on Hopper. Racing
the lock will cause model eviction and 20–30s cold-reload stalls.

---

## Active initiative — Dev workspace continuity

**Phase 2 backend tasks (all parallel-safe):**

| Task | File | Status |
|------|------|--------|
| F1 — Dev sessions | `dev_sessions/routes.py` | ⚙️ stub, blocked on P0 merge |
| F2 — Dev files | `dev_files/routes.py` | ⚙️ stub, blocked on P0 merge |
| F3 — Dev projects | `dev_projects/routes.py` | ⚙️ stub, blocked on P0 merge |

Each task has a one-line router mount already in `main.py`. The 501 stubs are
replaced with real implementations — no merging or file-conflict risk between
F1, F2, and F3.
