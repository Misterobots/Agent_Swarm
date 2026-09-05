# Justin-PC variant disposition

Audited 2026-08-27 from the backend handoff checkout. The repository contains
28 tracked files whose names end in `-Justin-PC`. Each was compared with the
same path after removing that suffix, with CRLF normalized to LF.

## Removed exact duplicates

These seven files were byte-identical to their canonical counterparts after
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

The following 11 older troubleshooting/test copies were also removed after
the same reference check. Their canonical counterparts remain available.

- `scripts/check_hive_routers-Justin-PC.sh`
- `scripts/check_routers-Justin-PC.sh`
- `scripts/check_traefik-Justin-PC.sh`
- `scripts/find_auth_middleware-Justin-PC.sh`
- `scripts/fix_hive_cors-Justin-PC.sh`
- `scripts/fix_hive_proxy-Justin-PC.sh`
- `scripts/fix_hive_proxy_v2-Justin-PC.sh`
- `scripts/fix_hive_proxy_v3-Justin-PC.sh`
- `scripts/fix_tls_warnings-Justin-PC.sh`
- `tests/test_router_phase2-Justin-PC.py`
- `tests/test_routing_regression-Justin-PC.py`

## Retained deployment variant

The only retained `-Justin-PC` variant is the Turing gateway compose file. It
is the intentional live deployment variant and must remain the source used by
Turing until the deployment is migrated to a canonical compose file.

- `turing_gateway/docker-compose-Justin-PC.yml`

## Worktree state

Git now registers two worktrees: the dirty primary `main` worktree, which is
preserved as-is, and the active consolidated worktree. Historical branch refs
remain available without checkout directories; they can be recreated with
`git worktree add` if a specific branch is needed again.

Twenty-seven obsolete suffixed files were deleted after tracked-reference and
deployment checks. The live Turing deployment variant was retained. Eight
redundant clean worktree directories were removed; their branch refs were
retained.
