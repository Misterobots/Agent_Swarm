# Friday Bambu bridge

This is the Windows-local boundary between Friday and the P1S.  It does not
accept arbitrary paths, commands, or G-code.  It only exposes jobs listed in
`jobs.json`, requires a short-lived approval token to start or cancel, and
keeps P1S credentials out of Agent_Swarm.

## First run

1. Copy `.env.example` to a private environment file and set `BAMBU_BRIDGE_TOKEN`.
2. Create a Bambu Studio project for an approved job, slice it with the chosen
   P1S/filament profile, and save the resulting `.gcode.3mf` beside the source
   model in `cad/print_jobs/`.
3. Add its SHA-256 and metadata to `jobs.json`.
4. Run `uvicorn app:app --host 127.0.0.1 --port 8791` from this folder.
5. Set `BAMBU_BRIDGE_URL` and `BAMBU_BRIDGE_TOKEN` in Agent_Swarm's private
   runtime environment; restart Agent_Swarm.

Until a LAN connector is paired, `start` safely opens the approved model in
Bambu Studio for final human review and returns `manual_handoff_required`.
That is intentional: no inferred printer IP, access code, or unofficial start
command is allowed.

## Endpoint contract

- `GET /status` — bridge configuration and connector state.
- `GET /list_jobs` — allow-listed jobs only.
- `POST /preflight {"job_id"}` — validates the job file and SHA-256.
- `POST /request_approval {"job_id"}` — creates a 10-minute one-time token.
- `POST /start {"job_id","approval_token","confirmed":true}` — consumes the
  approval; calls the configured connector or opens the approved project.
- `POST /cancel {"approval_token","confirmed":true}` — connector-only,
  confirmation-gated cancellation.
