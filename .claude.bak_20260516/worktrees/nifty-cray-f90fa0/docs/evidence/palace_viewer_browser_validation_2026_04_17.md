# Palace Viewer Browser Validation — 2026-04-17

**Date:** 2026-04-17  
**Component:** Hive UI Palace Viewer (`/palace`) + shared backend proxy  
**Environment:** Local deployment via Next.js dev server on `http://localhost:3005` with `API_BASE_URL=http://localhost:8008` and `MEMPALACE_BASE_URL=http://localhost:8200`; MemPalace served from `control_plane/docker-compose.yml` services `db` and `mempalace`; Agent Runtime served on `http://localhost:8008`  
**Result:** **Pass with multiple deployment and UI fixes applied during validation**

---

## Deployment Setup Used

### Backend

```powershell
cd control_plane
docker compose up -d db mempalace
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8200/health
```

Expected response:

```json
{"status":"ok","service":"mempalace"}
```

### Frontend

```powershell
cd ui
$env:API_BASE_URL='http://localhost:8008'
$env:MEMPALACE_BASE_URL='http://localhost:8200'
$env:NEXT_TELEMETRY_DISABLED='1'
npm run dev -- --port 3005
```

---

## Test Data Used

Three fixture memories were created through the live browser proxy to populate the Palace hierarchy:

- `semantic / operations / navigator`
- `episodic / retrospective / navigator`
- `procedural / playbooks / builder`

Resulting layout:

- `wing_navigator`
  - `hall_facts` → `operations` (1 drawer)
  - `hall_events` → `retrospective` (1 drawer)
- `wing_builder`
  - `hall_advice` → `playbooks` (1 drawer)

---

## Browser Scenarios Verified

1. Opened `/palace` and confirmed the lobby rendered with `3 memories across 2 wings`.
2. Confirmed both wing portals rendered in the 3D scene (`navigator`, `builder`).
3. Clicked the `navigator` portal and confirmed breadcrumb update: `Palace > navigator`.
4. Clicked the `facts` hall portal and confirmed room breadcrumb update: `Palace > navigator > facts > operations`.
5. Confirmed the room loaded one drawer and the drawer label matched the seeded memory.
6. Double-clicked the drawer and confirmed the detail panel opened with content, agent, owner, created time, access count, and wing metadata.
7. Entered `fixture one` in the HUD search box and confirmed the search toast returned matches from the live backend.
8. Pressed `ArrowRight` in room view and confirmed keyboard drawer selection opened the detail panel.
9. Pressed `Escape` and confirmed the detail panel closed cleanly.
10. Confirmed `/api/backend/api/v1/identity` and `/api/backend/v1/palace/layout` both returned `200` through the same UI proxy.
11. Confirmed browser-origin `POST`, `PATCH`, and `DELETE` requests against `/api/backend/v1/memories/*` all succeeded after the proxy fix.

---

## Defect Found During Validation

### React render-time state update in `RoomScene`

Observed in browser console while entering a room:

```text
Cannot update a component while rendering a different component (`CameraController`)...
```

Root cause:

- `RoomScene` called `loadRoomMemories(...)` during render when the room key changed.

Fix applied:

- Moved room-memory loading into a `useEffect` keyed by room coordinates in `ui/src/components/palace/scenes/room-scene.tsx`.

Post-fix validation:

- Replayed `lobby -> navigator -> facts -> operations`.
- The React warning no longer appeared.
- Room loading and drawer interaction still worked.

### Shared backend proxy could not serve a real deployed Palace session

Observed during broader deployment validation:

- `GET /api/backend/api/v1/identity` needed to go to Agent Runtime.
- `GET /api/backend/v1/palace/layout` and Palace memory CRUD needed to go to MemPalace.
- The proxy only supported `GET` and `POST`, so Palace edit/delete operations could not work through the UI route.

Root cause:

- `ui/src/app/api/backend/[...path]/route.ts` forwarded every request to a single backend URL.
- Palace endpoints live on MemPalace, while identity lives on Agent Runtime.
- `PATCH` and `DELETE` handlers were missing entirely.

Fix applied:

- Added split routing in the proxy:
  - general runtime requests -> `API_BASE_URL`
  - Palace and memory requests -> `MEMPALACE_BASE_URL` or `MEMPALACE_URL`
- Added `PATCH`, `PUT`, `DELETE`, and `OPTIONS` handlers to the proxy route.

Post-fix validation:

- `/api/backend/api/v1/identity` returned anonymous identity from Agent Runtime.
- `/api/backend/v1/palace/layout` returned live MemPalace data.
- Browser-origin `POST`, `PATCH`, and `DELETE` to `/api/backend/v1/memories/*` all returned `200`.

### Production build blockers in training UI

Observed during validation:

- The Palace Viewer code built, but unrelated training UI type errors blocked a full production build.

Fixes applied:

- `ui/src/lib/api/training.ts`: aligned `TrainingReport.live` with `Partial<LiveTrainingMetrics>`.
- `ui/src/components/training/training-run-history.tsx`: fixed nullable phase access.

Post-fix validation:

- `npm run build` completed successfully.

---

## Theme Variation Validation

Additional live browser validation was performed after the themed atmosphere pass on `/palace`.

Scenarios verified:

1. Switched the live page theme to `ember` and confirmed the Palace retained warm forge-like rings and warm portal framing.
2. Switched to `hacker` and confirmed the Palace shifted to a stronger green terminal-like mood with visibly different atmospheric bars.
3. Switched to `star-trek` and confirmed LCARS-style side columns became visible in the lobby after the follow-up visibility adjustment.
4. Switched to `minimal` and confirmed the Palace collapsed to a sparse gallery-like white/gray presentation without interaction regressions.
5. Confirmed the route still rendered with a single canvas during theme switching.

Observed browser sample during the theme pass:

- `canvasCount: 1`
- `usedJSHeapSize: ~27-29 MB`

Result:

- Theme changes now affect more than palette alone; the Palace atmosphere has distinct low-cost motif geometry per theme while remaining within the same practical render budget.

---

## Architectural Visual Pass Validation

An additional visual upgrade pass was validated live in the browser to move the Palace away from flat debug-like geometry toward a more contemporary architectural look.

Changes validated visually:

1. Lobby: deeper portal framing, suspended halo rings, vertical ribs, richer floor treatment, and layered atmospheric shells.
2. Wing corridor: framed portal doors, repeated corridor ribs, side light washes, stronger runner treatment, and a more deliberate tunnel silhouette.
3. Room: wall paneling, side coves, a central dais, animated halo treatment, and stronger trim/floor composition.
4. Shared materials: wall, floor, accent, and drawer materials now use more polished physical shading instead of flatter standard shading.

Live browser walkthrough performed:

1. Reloaded `/palace` in the browser and verified the upgraded lobby rendered successfully.
2. Clicked into `builder` from the canvas and verified the upgraded corridor shell rendered without errors.
3. Clicked into `advice -> playbooks` and verified the upgraded room shell rendered successfully.

Observed browser sample after the architectural pass:

- `theme: ember`
- `canvasCount: 1`
- `fpsApprox: ~62`
- `usedJSHeapSize: ~32.9 MB`

Result:

- The Palace now reads as a more intentional stylized environment rather than bare early-era box geometry, while still staying comfortably within the current render budget.

---

## Residual Notes

- A Three.js warning was observed:

```text
THREE.THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.
```

This did not block Palace Viewer functionality, but it should be cleaned up in a future pass if the dependency path is under project control.

---

## Coverage Gaps

The following flows were **not** validated in this browser run:

- Admin-only owner switching
- Admin create flow through the modal
- Edit/delete permissions through the visual UI under authenticated identity
- Audit history population from an in-UI edit action
- Authentik-backed admin identity propagation end-to-end through the browser session

---

## Source References

| Source | Type | Relevance |
|--------|------|----------|
| `ui/src/components/palace/` | Implementation | Browser-tested Palace Viewer UI |
| `ui/src/lib/api/palace.ts` | API client | Proxy calls exercised by the browser |
| `ui/src/app/api/backend/[...path]/route.ts` | Proxy | Split routing for runtime identity + MemPalace data, plus added verbs |
| `ui/src/lib/api/training.ts` | Type contract | Fixed report/live type mismatch that blocked production build |
| `ui/src/components/training/training-run-history.tsx` | Training UI | Fixed nullable phase access that blocked production build |
| `control_plane/mempalace/app/main.py` | Backend | Palace layout, room, search, and CRUD endpoints |
| `control_plane/docker-compose.yml` | Deployment | Services used for this validation |
