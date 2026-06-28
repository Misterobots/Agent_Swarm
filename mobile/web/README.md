# Memex Mobile Web App (mxmobile.shivelymedia.com)

Serves the **Memex Desktop renderer** as a mobile-first web app and reverse-proxies
the backends same-origin (so the browser makes no cross-origin calls; Authentik
gates at the Traefik edge). This is what the Android TWA points at.

```
phone APK / browser ─► mxmobile.shivelymedia.com (Authentik)
                          ├─ /            → SPA (Memex Desktop UI)
                          ├─ /v1/*        → agent_runtime  (chat SSE, conversations, models)
                          ├─ /mp/*        → MemPalace
                          ├─ /ollama/*    → Ollama
                          └─ /.well-known/assetlinks.json (no-auth bypass, for the TWA)
```

## Contents
- `Dockerfile` — nginx image: serves `spa/` + the reverse proxy (`nginx.conf`).
- `nginx.conf` — SPA fallback + SSE/WebSocket-aware proxying with dynamic upstream
  resolution (starts even if a backend is momentarily down).
- `spa/` — the built Memex Desktop renderer (checked in so Turing can build the
  image without the `memex-desktop` source).

## Updating the UI
The SPA is a build artifact from the separate `memex-desktop` repo:

```bash
# in memex-desktop/
npx vite build
# copy the fresh build into this context:
rm -rf <Agent_Swarm>/mobile/web/spa && cp -r dist/. <Agent_Swarm>/mobile/web/spa/
cp <Agent_Swarm>/mobile/twa/output/assetlinks.json <Agent_Swarm>/mobile/web/spa/.well-known/
```
Then rebuild + redeploy the `mxmobile` service on Turing.

## Deploy (on Turing)
The `mxmobile` service is defined in `turing_gateway/docker-compose.yml`:
```bash
cd /home/misterobots/Agent_Swarm/turing_gateway
docker compose build mxmobile && docker compose up -d mxmobile
```
Routing: external HTTPS `mxmobile.shivelymedia.com` behind Authentik, with
`/.well-known/` exempt so Android can verify the TWA. `*.shivelymedia.com`
already resolves via the Cloudflare wildcard.
