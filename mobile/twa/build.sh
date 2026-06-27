#!/usr/bin/env bash
# Builds the Memex TWA APK. Run inside the Docker image (see README).
#   - serves icons/manifest locally so Bubblewrap doesn't hit the Authentik-gated site
#   - reuses a persisted signing key (mount ./keystore) for a stable assetlinks fingerprint
#   - emits the signed APK + assetlinks.json to ./output
set -euo pipefail

PASS="${KEYSTORE_PASS:-memex-remote-control}"
PKG="com.shivelymedia.memex"
PORT=8088

mkdir -p /twa/serve /twa/keystore /twa/output

# ── Local asset server (Bubblewrap fetches iconUrl/webManifestUrl at build time) ──
cp /twa/assets/icon-512.png          /twa/serve/icon-512.png
cp /twa/assets/icon-maskable-512.png /twa/serve/icon-maskable-512.png
cat > /twa/serve/manifest.json <<JSON
{
  "name": "Memex",
  "short_name": "Memex",
  "start_url": "/chat",
  "scope": "/",
  "display": "standalone",
  "theme_color": "#0e1117",
  "background_color": "#0e1117",
  "icons": [
    { "src": "http://127.0.0.1:${PORT}/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "http://127.0.0.1:${PORT}/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
JSON

python3 -m http.server "$PORT" --directory /twa/serve >/tmp/serve.log 2>&1 &
SERVE_PID=$!
sleep 1

# ── Signing key (persisted via mounted ./keystore) ──
if [ ! -f /twa/keystore/memex.keystore ]; then
  echo ">> generating signing keystore"
  keytool -genkeypair -v \
    -keystore /twa/keystore/memex.keystore -alias memex \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$PASS" -keypass "$PASS" \
    -dname "CN=Memex Remote, O=ShivelyMedia, C=US"
fi

export BUBBLEWRAP_KEYSTORE_PASSWORD="$PASS"
export BUBBLEWRAP_KEY_PASSWORD="$PASS"

# ── Generate the Android project from twa-manifest.json, then build ──
echo ">> bubblewrap update (generate project)"
bubblewrap update --skipVersionUpgrade

echo ">> bubblewrap build"
bubblewrap build --skipPwaValidation

kill "$SERVE_PID" 2>/dev/null || true

# ── Collect artifacts ──
cp -f ./app-release-signed.apk /twa/output/memex.apk 2>/dev/null \
  || cp -f ./app-release-signed.apk /twa/output/ 2>/dev/null || true

FP=$(keytool -list -v -keystore /twa/keystore/memex.keystore -alias memex -storepass "$PASS" \
     | grep -i "SHA256:" | head -1 | sed 's/.*SHA256: *//' | tr -d ' ')
cat > /twa/output/assetlinks.json <<JSON
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "${PKG}",
      "sha256_cert_fingerprints": ["${FP}"]
    }
  }
]
JSON

echo ""
echo "================ BUILD COMPLETE ================"
echo "SHA-256 fingerprint: ${FP}"
echo "Artifacts in ./output:"
ls -la /twa/output/
echo "Host /twa/output/assetlinks.json at:"
echo "  https://memex.shivelymedia.com/.well-known/assetlinks.json"
