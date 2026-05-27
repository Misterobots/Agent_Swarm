# Handoff: 3D and ACTION_FIGURE Route Review

**Status:** Open
**Created:** 2026-05-26
**Estimated effort:** 2-4 hours (mostly tracing + a few live tests)

---

## Mission

Perform an end-to-end functionality and workflow review of the `3D` and `ACTION_FIGURE` intent routes. Verify each of:

1. **Intent detection** correctly fires for both routes.
2. **Queue serialization** (concurrency=1) actually blocks parallel work.
3. **GPU zone management** evicts the right services before a job starts.
4. **Handler pipeline** runs each step to completion.
5. **Result delivery** — output (mesh / STL / image) reaches the user.

Don't fix what you find. Flag it. Fixes go in a separate task.

---

## Background — why now

A review of `agents/dispatcher.py` found that intent classification was computed but never used to select a queue. Every task — including 3D and action-figure jobs — went to `queue:default` (5 concurrent workers), bypassing the GPU-protected `queue:3d` and `queue:action_figure` (concurrency=1 each).

That bug is now fixed. `_INTENT_QUEUE_MAP` in `agents/dispatcher.py` (around line 175) routes:

| Intent | Queue | Concurrency |
|---|---|---|
| `3D` | `queue:3d` | 1 |
| `ACTION_FIGURE` | `queue:action_figure` | 1 |
| `IMAGE` | `queue:image` | 2 |
| `VISION` | `queue:vision` | 3 |
| everything else | `queue:default` | 5 |

**The implication for you:** these two routes have likely *never been exercised through their dedicated queues in production*. They worked "accidentally" through `queue:default` until now. We need to confirm they actually function correctly under single-worker serialization and proper GPU zone handoff.

---

## Scope

### In scope
- `3D` intent end-to-end (Klein service)
- `ACTION_FIGURE` intent end-to-end (Klein + post-processing pipeline)
- Concurrency=1 serialization behavior
- GPU zone transitions during these jobs
- Failure modes (Klein down, eviction stalls, handler crashes)

### Out of scope
- `VISION` / `IMAGE` queue changes — already verified separately.
- The `redis.ConnectionError` bug in `_consumer_loop` — separate fix in progress (see review item #2).
- General GPU eviction logic and the `request_lock()` mutex — covered by existing behavior; only test it in the context of these two routes.
- Tuning concurrency limits — flag issues, but don't tune.

---

## Files to read

### Intent detection
- `agents/dispatcher.py` lines 78-108 — `detect_intent()` (keyword classifier used by dispatcher)
- `agents/dispatcher.py` line ~175 — `_INTENT_QUEUE_MAP` (the new routing dict)
- `agents/semantic_router.py` lines 17-50 — `_FAST_PATH_RULES` regex list. Note the `ACTION_FIGURE` rule at line 27 and the LLM-fallback category list at lines 82-83.

### Queue dispatch
- `agents/dispatcher.py` lines 195-230 — `start_consumers()` and `_consumer_loop()`.

### GPU zone management
- `agents/utils/gpu_queue.py` line 498 — `request_lock(context)` context manager (the redis mutex + zone-switching dispatcher)
- `agents/utils/gpu_queue.py` line 332 — `evict_klein()`
- `agents/utils/gpu_queue.py` line 382 — `warmup_klein()`
- Watch the `context == "image"` and `context == "compose"` branches around line 543 — figure out which one(s) the 3D/ACTION_FIGURE handlers actually request.

### Handlers (you'll need to discover these)
- Likely under `agents/handlers/` — grep for `"3D"`, `"ACTION_FIGURE"`, `Klein`, `evict_klein`, `warmup_klein`.
- Also check `agents/main.py` startup for the `USER_TASK` handler registration to trace the entry point.

### Services
- 3D: Klein at `KLEIN_HOST` (default `http://klein_service:8189`) — endpoints to find: `/generate`, `/evict`, `/warmup`, `/health`.
- ACTION_FIGURE: **pipeline unknown — discover it.** May involve Klein + a mesh-splitting/joint-rigging post-processor.

---

## Specific verifications

### Both routes
1. **Intent stickiness.** Run 5-10 phrasings per route through `detect_intent()` and the `SemanticRouter`. For 3D try: "make a 3d model of a dragon", "generate a mesh of a cube", "I want a glb of a tree", "blender model of...", "forge me a 3d thing". For ACTION_FIGURE: "make an action figure of Spider-Man", "posable figurine", "articulated 3d print of a robot", "ball-jointed figure". Confirm correct intent every time.
2. **Queue routing.** After `dispatcher.emit()`, inspect Redis: `redis-cli LRANGE queue:3d 0 -1` and `redis-cli LRANGE queue:action_figure 0 -1`. The event should land there, **not** in `queue:default`.
3. **Serialization.** Submit two requests for the same intent back-to-back. Confirm the second is held until the first completes. Easy check: timestamps in the log; the second handler shouldn't start until the first emits a "done" log line.
4. **Zone handoff.** Watch for `[GPU Queue] Context switch detected: 'X' -> 'image'` (or `'compose'`). Confirm the correct evict calls fire (e.g., `evict_ollama`, `evict_comfyui`, `evict_omnigen`) in the order shown around `gpu_queue.py:543`.
5. **Failure modes.**
   - Kill the Klein container mid-job — does the handler error gracefully, or hang?
   - Hold the Redis lock externally for 60s — does `request_lock()`'s timeout kick in?
   - Force a handler exception — does the queue's consumer thread recover or die silently?

### 3D-specific
- Which Klein endpoint does the handler hit (likely `/generate` or `/forge`)? Confirm by inspecting outbound HTTP from the handler or Klein's access log.
- How is the resulting mesh (GLB/OBJ) returned to the user — SSE chunk, file URL, chat attachment?
- What happens when `evict_klein` Phase 2 (container restart) is needed but `EVICT_CONTAINER_RESTART` isn't set? Does the next job's warmup succeed anyway?

### ACTION_FIGURE-specific
- **Discover the pipeline first.** Probable steps: image input → 3D mesh → joint segmentation → posable rigging → STL export. Document each stage with the file/function that owns it.
- Is there a post-processing step that runs on CPU after the GPU stage? If yes, the concurrency=1 cap may be over-restrictive (the GPU is free during CPU post-processing — flag this for follow-up).
- Does it ever invoke OmniGen for multi-view input? If so, the GPU zone needs to be `compose`, not `image`. Confirm which zone the handler requests.
- How long does an end-to-end job actually take? (Use this to sanity-check whether concurrency=1 is right.)

---

## Known unknowns to resolve

- [ ] Where is the `ACTION_FIGURE` handler registered? (Grep `ACTION_FIGURE` and `action_figure` under `agents/handlers/`.)
- [ ] Is there a separate ACTION_FIGURE worker process, or does it run inside the main agent runtime?
- [ ] Does it call Klein, OmniGen, or both?
- [ ] Typical end-to-end duration for each route?
- [ ] How are partial failures surfaced to the user? (Toast? SSE error? Silent retry?)

---

## What to deliver

A short report (under one page) covering:

1. **Intent classification accuracy** — per route, with the phrasings you tested.
2. **Queue routing** — confirmed working / broken, with Redis evidence.
3. **Pipeline trace** — each step + service called, in order, for each route.
4. **Failure modes encountered** — what broke under the stress tests.
5. **Recommendations** — concurrency tuning, missing error handling, dead code, or anything else worth a follow-up task.

Drop the report into `docs/handoffs/3d-action-figure-route-review-FINDINGS.md` and mark this handoff `Closed` at the top.

---

## Related context

- Originating review: see chat transcript, "Model & Queue Review" chapter (2026-05-26).
- Queue config: `agents/dispatcher.py:144-152`
- Routing map: `agents/dispatcher.py:175-186`
- Doc updates from the routing fix: `docs/admin/agent_training_reference.md`, `docs-site/docs/modules/dispatcher.md`, `docs-site/docs/architecture/data-flow.md`.
