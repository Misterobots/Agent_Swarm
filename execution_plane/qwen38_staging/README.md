# Isolated staging authentication

Entry: http://127.0.0.1:3319/api/auth/login . Authenticated workspace: /dev.

Source is codex/qwen38-integration in Memex_Core-qwen38-integration; application
code at 900f484 plus this configuration. UI rebuilt with an empty
NEXT_PUBLIC_GATEWAY_URL, so browser requests stay on the authenticated origin.
UI image ID: sha256:c253b552c87f193ebb7f28213acee9c1889a38fb833126fbfec924485857ab8e.
Backend image ID: sha256:39a8d2022c1ffbd36ff3d94a595c4a780a8d9af692f7861c0e30805ba6618b52.

The proxy alone publishes 127.0.0.1:3319. Backend, UI and OAuth proxy have no
published ports and join only memex_qwen38_private, a separate Docker bridge.
Port 8019 is no longer published. Backend code and workspace mounts are read-only.
No Docker socket is mounted. Shared DB/Redis credentials are deliberately absent;
the backend starts with its existing unavailable-store behavior. Its root status
is not a persistence/queue readiness test. This deployment qualifies auth only.

## Identity and policy

Existing Authentik: https://auth.shivelymedia.com . Dedicated application slug
memex-qwen38-staging, application UUID 76638bb1-581b-4476-8ac0-00a4e4da0a5e,
OAuth provider18, client ID memex-qwen38-staging. Callback is exactly
http://127.0.0.1:3319/oauth2/callback (strict).

Authentication, authorization and logout flows inherit the current Memex provider.
Source Memex application had no policy bindings; staging additionally requires
the real active misterobots user (application policy engine all). No existing
provider, public router, outpost, policy, DNS or tunnel was modified.

OAuth2 Proxy validates issuer/signature, state, nonce and PKCE S256. A fresh,
one-hour HttpOnly SameSite=Lax cookie belongs to loopback staging; Secure=false
is limited to this HTTP loopback origin. Public cookies are never transferred.
Nginx auth_request requires a validated session; upstream client headers are
discarded and an explicit allowlist supplies verified username, subject, email
and groups. Incoming Authorization and identity headers are not forwarded.
The private Docker network and loopback binding form the trust boundary; a user
with Docker administration access remains trusted. Do not attach other workloads.

POST and other write methods remain denied at the edge during auth qualification.
No model inference is authorized by creating this route. Model evaluation also
needs writable isolated state, queue/lease wiring and the separate release gate.

## Operational handling

compose.yml expects QWEN_STAGING_CLIENT_SECRET and QWEN_STAGING_COOKIE_SECRET
in the invoking process. The cookie secret is 32 random bytes encoded with
URL-safe base64. Secrets were generated during provisioning, passed directly
to container creation, and not saved in this repository or printed. Docker
administrators can recover them from memex_qwen38_oauth's environment in memory
for recreation; never print raw docker inspect or compose config output.

provision_authentik.py is a one-time script sent over SSH stdin to the existing
Authentik Django shell. Its STAGING_CREDENTIAL result MUST be captured in memory,
parsed and consumed by compose, never echoed. It refuses duplicate registration.
inspect_authentik.py prints only non-secret inspection fields.

## Verification

Run `python execution_plane/qwen38_staging/check_boundary.py` for anonymous,
forged Authentik/forwarded/bearer/cookie requests and actual port/network checks.
All protected probes must return401. `docker exec memex_qwen38_proxy nginx -t`
checks syntax. Normal login must redirect to the existing Authentik site and
return to loopback. Independent browser verification must inspect /dev,
/api/auth/me and /api/backend/api/v1/identity for the real owner.

Current evidence: 20 protected anonymous/forged-header/forged-cookie probes
return401; actual container ports and network membership pass the boundary
check. SSO start returns302 to auth.shivelymedia.com/application/o/authorize/.
Authenticated owner proof is PENDING USER: D's independent in-app browser was
unavailable. The user must open the login entry in their in-app browser, complete
normal SSO (and any existing MFA/consent), and observe /dev plus the identity
endpoints. No session was copied and no authenticated success is claimed.

## Rollback

Stop/remove only the four created containers:

```powershell
docker rm -f memex_qwen38_proxy memex_qwen38_oauth memex_qwen38_ui_20260915 memex_qwen38_dev_20260915
docker network rm memex_qwen38_private
Get-Content -Raw execution_plane/qwen38_staging/rollback_authentik.py | ssh -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none -i C:/Users/panca/.ssh/id_ed25519 misterobots@192.168.2.103 'docker exec -i authentik ak shell'
```

The rollback script verifies exact staging application/provider IDs before
deleting that registration. Public services stay running. Do not restore the old
unauthenticated all-interface 3319/8019 port mappings. The prior staging image
memex-qwen38-ui:staging remains available; source commits are retained.
