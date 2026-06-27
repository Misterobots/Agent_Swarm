# Memex Remote Control — Android APK (TWA)

A sideloadable Android app that remote-controls your Memex agent. It's a **Trusted
Web Activity (TWA)**: a thin native shell that opens the existing PWA
(`https://memex.shivelymedia.com`) full-screen, reusing Authentik SSO. No separate
mobile codebase — the app is always in sync with the deployed web UI.

```
phone APK ──► memex.shivelymedia.com (PWA, behind Authentik)
                     └─► agent_runtime  /v1/chat/completions (SSE)
```

## Prerequisites
- Docker (the build toolchain — JDK 17, Android SDK, Bubblewrap — is fully containerized).
- Ability to host a file at `https://memex.shivelymedia.com/.well-known/assetlinks.json`
  (needed for full-screen, no-URL-bar mode).

## Build

```bash
cd mobile/twa
docker build -t memex-twa-builder .

# keystore/ and output/ persist on the host (stable signing key + artifacts)
docker run --rm \
  -v "$(pwd)/output:/twa/output" \
  -v "$(pwd)/keystore:/twa/keystore" \
  memex-twa-builder
```

Outputs to `mobile/twa/output/`:
- `memex.apk` — the signed, sideloadable APK
- `assetlinks.json` — Digital Asset Links file (contains the signing cert fingerprint)

The signing key lives in `mobile/twa/keystore/memex.keystore` and is **gitignored**.
Keep it safe: re-signing with a different key changes the fingerprint and breaks the
asset-link verification (and Android won't update an APK signed with a different key).

## Deploy (two steps)

1. **Host the asset-links file** so Android trusts the app for the domain (enables
   full-screen). Serve `output/assetlinks.json` at:

   ```
   https://memex.shivelymedia.com/.well-known/assetlinks.json
   ```

   It must be reachable **without** Authentik (allowlist `/.well-known/assetlinks.json`
   in Traefik / the Authentik forward-auth, like the PWA static-asset bypasses).
   Verify: `curl https://memex.shivelymedia.com/.well-known/assetlinks.json` returns the JSON.

2. **Sideload the APK**: copy `output/memex.apk` to the phone and install (enable
   "Install unknown apps" for your file manager/browser). First launch will sign in
   via Authentik in a Chrome Custom Tab; the session is then reused.

> If asset-links verification hasn't propagated yet, the app still works but shows a
> thin URL bar at the top. Once `assetlinks.json` is live and matches the fingerprint,
> it goes full-screen.

## Updating
Bump `appVersionName` / `appVersionCode` in `twa-manifest.json`, rebuild with the
**same** keystore, and reinstall. Because it's a TWA, day-to-day UI changes ship by
deploying the web app — no APK rebuild needed.

## Config
- `twa-manifest.json` — package id (`com.shivelymedia.memex`), host, colors, start URL
  (`/chat`), icon sources. Icons are fetched from a local server at build time (the live
  ones are behind Authentik), baked from `assets/icon-512.png` + `assets/icon-maskable-512.png`.
- Regenerate icons from source: `ui/public/icons/icon-src-*.svg`.
