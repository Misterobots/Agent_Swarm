# Justin-PC variant disposition

Audited 2026-08-27 from the backend handoff checkout. The repository contains
28 tracked files whose names end in `-Justin-PC`. Each was compared with the
same path after removing that suffix, with CRLF normalized to LF.

## Removed exact duplicates

These seven files are byte-identical to their canonical counterparts after
line-ending normalization. They were removed from the repository after a
tracked-reference check found no runtime or operator references outside
generated graph artifacts and this audit document. The canonical counterparts
were retained.

- `agents/bmo_voice/launch_face-Justin-PC.sh`
- `agents/bmo_voice/launch_face_fast-Justin-PC.sh`
- `agents/registry-Justin-PC.py`
- `docs/naming-scheme-options-Justin-PC.html`
- `governance-Justin-PC.json`
- `tests/system_test-Justin-PC.py`
- `tests/test_coordinator_memory-Justin-PC.py`

## Divergent variants requiring review

The remaining 21 files differ from their canonical counterparts. They must
not be bulk-merged or deleted: several are historical repair scripts, while
the Turing gateway compose file is an intentional deployment variant.

- `agents/bmo_voice/bmo-Justin-PC.service`
- `agents/church-Justin-PC.py`
- `agents/grpc/generate-Justin-PC.sh`
- `agents/kay_service-Justin-PC.py`
- `agents/main-Justin-PC.py`
- `control_plane/docker-compose-Justin-PC.yml`
- `scripts/bmo_sandbox-Justin-PC.py`
- `scripts/check_hive_routers-Justin-PC.sh`
- `scripts/check_routers-Justin-PC.sh`
- `scripts/check_traefik-Justin-PC.sh`
- `scripts/deploy_mission_control_home_assistant-Justin-PC.sh`
- `scripts/find_auth_middleware-Justin-PC.sh`
- `scripts/fix_hive_cors-Justin-PC.sh`
- `scripts/fix_hive_proxy-Justin-PC.sh`
- `scripts/fix_hive_proxy_v2-Justin-PC.sh`
- `scripts/fix_hive_proxy_v3-Justin-PC.sh`
- `scripts/fix_tls_warnings-Justin-PC.sh`
- `services/home_assistant/addons/mission-control/run-Justin-PC.sh`
- `tests/test_router_phase2-Justin-PC.py`
- `tests/test_routing_regression-Justin-PC.py`
- `turing_gateway/docker-compose-Justin-PC.yml`

## Worktree state

Git currently registers eight worktrees. Seven are clean branch checkouts:
`codex/android-pipeline`, `codex/backend-handoff-contract`,
`codex/backend-handoff-current`, `codex/integration-backend-gateway`,
`codex/runtime-backend-gateway-integration`, `codex/runtime-core-current`,
and `codex/turing-gateway-envfix`. The `main` worktree is dirty with unrelated
user changes and is preserved as-is.

Seven exact duplicate files were deleted in the follow-up cleanup commit. No
divergent variants or worktrees were deleted or merged.
