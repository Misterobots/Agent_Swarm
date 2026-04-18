#!/bin/bash
# Copy the Mission Control add-on scaffold to the Home Assistant local add-ons directory.

set -euo pipefail

TARGET_HOST="${TARGET_HOST:-192.168.2.100}"
TARGET_USER="${TARGET_USER:-misterobots}"
TARGET_DIR="${TARGET_DIR:-/addons/local/mission_control}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/services/home_assistant/addons/mission-control"

echo "=== Mission Control Add-on Deployment ==="
echo "Target: ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}"

if [[ ! -f "$SOURCE_DIR/config.yaml" ]]; then
  echo "ERROR: Missing add-on config at $SOURCE_DIR"
  exit 1
fi

echo "[1/4] Checking SSH reachability..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "${TARGET_USER}@${TARGET_HOST}" "echo ok" >/dev/null

echo "[2/4] Creating remote add-on directory..."
ssh "${TARGET_USER}@${TARGET_HOST}" "mkdir -p ${TARGET_DIR}"

echo "[3/4] Copying add-on scaffold..."
scp -r "$SOURCE_DIR"/* "${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/"

echo "[4/4] Asking Home Assistant to rescan local add-ons if CLI is available..."
ssh "${TARGET_USER}@${TARGET_HOST}" "if command -v ha >/dev/null 2>&1; then ha addons reload || true; fi"

echo
echo "Copy complete."
echo "Next steps in Home Assistant: Settings -> Add-ons -> Add-on Store -> Check for updates."
echo "Then open the local Mission Control add-on, set options, install, and start it."