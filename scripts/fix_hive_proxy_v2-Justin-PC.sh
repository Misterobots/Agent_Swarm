#!/bin/bash
set -e

COMPOSE="/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml"
UI_DIR="/home/misterobots/Home_AI_Lab/ui"

# 1. Extract server.js from the image
echo "Extracting server.js from image..."
docker create --name hive_extract home-ai-lab/hive-ui:latest >/dev/null 2>&1
docker cp hive_extract:/app/server.js "$UI_DIR/server.patched.js"
docker rm hive_extract >/dev/null 2>&1

# 2. Patch the rewrite URL
echo "Patching rewrite URL..."
sed -i 's|http://localhost:8000|http://execution-node:8008|g' "$UI_DIR/server.patched.js"

# Verify the patch
if grep -q 'execution-node:8008' "$UI_DIR/server.patched.js"; then
  echo "Patch applied successfully"
else
  echo "ERROR: Patch did not apply"
  exit 1
fi

# 3. Remove the command override we added earlier (it doesn't work due to permissions)
# and add a volume mount for the patched server.js instead
sed -i '/command: \["sh", "-c", "sed -i/d' "$COMPOSE"

# 4. Add volume mount for patched server.js if not already present
if grep -A20 'container_name: hive_ui' "$COMPOSE" | grep -q 'server.patched.js'; then
  echo "Volume mount already exists"
else
  # Add the volume mount to the existing volumes section
  sed -i '/^\s*- \.\.\/docs:\/app\/docs:ro$/a\      - ../ui/server.patched.js:/app/server.js:ro' "$COMPOSE"
  echo "Added volume mount for patched server.js"
fi

echo ""
echo "Verifying compose changes:"
grep -B2 -A8 'container_name: hive_ui' "$COMPOSE"
echo ""
echo "Verifying volumes section:"
grep -A5 'volumes:' "$COMPOSE" | head -10

