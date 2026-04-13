#!/bin/bash
set -e

COMPOSE="/home/misterobots/Home_AI_Lab/r730_gateway/docker-compose.yml"
UI_DIR="/home/misterobots/Home_AI_Lab/ui"
PATCH_DIR="$UI_DIR/patched-next"

mkdir -p "$PATCH_DIR"

# Extract files that contain the rewrite URL from the image
echo "Extracting Next.js manifest files from image..."
docker create --name hive_extract home-ai-lab/hive-ui:latest >/dev/null 2>&1 || true
docker cp hive_extract:/app/.next/routes-manifest.json "$PATCH_DIR/routes-manifest.json"
docker cp hive_extract:/app/.next/required-server-files.json "$PATCH_DIR/required-server-files.json"
docker rm hive_extract >/dev/null 2>&1

# Patch all files
echo "Patching rewrite URLs..."
sed -i 's|http://localhost:8000|http://execution-node:8008|g' "$UI_DIR/server.patched.js"
sed -i 's|http://localhost:8000|http://execution-node:8008|g' "$PATCH_DIR/routes-manifest.json"
sed -i 's|http://localhost:8000|http://execution-node:8008|g' "$PATCH_DIR/required-server-files.json"

# Verify patches
for f in "$UI_DIR/server.patched.js" "$PATCH_DIR/routes-manifest.json" "$PATCH_DIR/required-server-files.json"; do
  if grep -q 'localhost:8000' "$f"; then
    echo "ERROR: $f still contains localhost:8000"
    exit 1
  fi
  echo "OK: $(basename $f) patched"
done

# Add volume mounts for the manifest files if not already present
if ! grep -q 'routes-manifest.json' "$COMPOSE"; then
  sed -i '/server\.patched\.js:\/app\/server\.js:ro/a\      - ../ui/patched-next/routes-manifest.json:/app/.next/routes-manifest.json:ro\n      - ../ui/patched-next/required-server-files.json:/app/.next/required-server-files.json:ro' "$COMPOSE"
  echo "Added volume mounts for manifest files"
else
  echo "Manifest volume mounts already exist"
fi

echo ""
echo "Verifying volumes:"
grep -A8 'volumes:' "$COMPOSE" | grep -A8 'docs'
