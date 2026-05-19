#!/bin/bash
set -e

COMPOSE="/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml"
NETENV="/home/misterobots/Home_AI_Lab/network.env"

# 1. Populate network.env with Tailscale IP for execution node
echo "LOVELACE_IP=100.112.7.31" > "$NETENV"
echo "Updated $NETENV:"
cat "$NETENV"

# 2. Add command override to hive-ui service to patch the rewrite URL at startup
# Check if command override already exists
if grep -A2 'container_name: hive_ui' "$COMPOSE" | grep -q 'command:'; then
  echo "hive-ui command override already exists, skipping"
else
  # Insert command after 'container_name: hive_ui' line
  sed -i '/container_name: hive_ui/a\    command: ["sh", "-c", "sed -i '"'"'s|http://localhost:8000|http://execution-node:8008|g'"'"' /app/server.js && exec node /app/server.js"]' "$COMPOSE"
  echo "Added command override to hive-ui service"
fi

echo ""
echo "Verifying changes:"
grep -A5 'container_name: hive_ui' "$COMPOSE"

