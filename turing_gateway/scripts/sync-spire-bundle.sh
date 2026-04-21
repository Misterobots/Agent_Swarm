#!/usr/bin/env bash
# sync-spire-bundle.sh — Pull fresh SPIRE trust bundle from control plane
# Runs as cron job to prevent CA rotation drift breaking agent attestation
set -euo pipefail

CONTROL_HOST="misterobots@192.168.2.102"
SSH_KEY="/home/misterobots/.ssh/id_rsa_sync"
BUNDLE_PATH="/home/misterobots/Home_AI_Lab/turing_gateway/config/spire/certs/spire-server-bundle.crt"
LOG_TAG="spire-bundle-sync"

log() { logger -t "$LOG_TAG" "$*"; echo "$(date -Is) $*"; }

# 1. Fetch current bundle from SPIRE server via SSH
NEW_BUNDLE=$(ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes "$CONTROL_HOST" \
  "docker exec spire-server /opt/spire/bin/spire-server bundle show -format pem" 2>/dev/null)

if [ -z "$NEW_BUNDLE" ]; then
  log "ERROR: Failed to fetch bundle from control plane"
  exit 1
fi

# 2. Validate it contains at least one PEM certificate
if ! echo "$NEW_BUNDLE" | openssl x509 -noout >/dev/null 2>&1; then
  log "ERROR: Fetched bundle is not valid PEM"
  exit 1
fi

# 3. Compare with current bundle (skip write if identical)
CURRENT_HASH=""
if [ -f "$BUNDLE_PATH" ]; then
  CURRENT_HASH=$(sha256sum "$BUNDLE_PATH" | awk '{print $1}')
fi
NEW_HASH=$(echo "$NEW_BUNDLE" | sha256sum | awk '{print $1}')

if [ "$CURRENT_HASH" = "$NEW_HASH" ]; then
  log "OK: Bundle unchanged (hash=${NEW_HASH:0:12}...)"
  exit 0
fi

# 4. Atomic write: write to temp, then move
TMPFILE=$(mktemp "${BUNDLE_PATH}.XXXXXX")
echo "$NEW_BUNDLE" > "$TMPFILE"
chmod 644 "$TMPFILE"
mv "$TMPFILE" "$BUNDLE_PATH"

log "UPDATED: Bundle refreshed (old=${CURRENT_HASH:0:12} new=${NEW_HASH:0:12})"

# 5. Verify TLS handshake with new bundle
if ! openssl s_client -connect 192.168.2.102:8081 -CAfile "$BUNDLE_PATH" </dev/null 2>/dev/null | grep -q 'Verify return code: 0'; then
  log "WARNING: TLS verification failed after bundle update — agent may need manual review"
  exit 1
fi

log "VERIFIED: TLS handshake to SPIRE server passes with new bundle"

