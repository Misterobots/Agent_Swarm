#!/bin/bash
set -e

COMPOSE="/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml"

# Check if bypass routers already exist
if grep -q 'hive-api-bypass' "$COMPOSE"; then
  echo "Bypass routers already exist. Skipping."
  exit 0
fi

# Add bypass router labels BEFORE the external HTTPS route comment line
# These have priority 25 (higher than 20) so they match first
# They skip the authentik@docker middleware for RSC and API requests

# Find the line with the external HTTPS route comment
ANCHOR='# External HTTPS route: hive.shivelymedia.com (behind Authentik)'

# Insert bypass routers before the main external route
sed -i "/$ANCHOR/i\\
      # --- Authentik Bypass for SPA/RSC requests (priority 25 > 20) ---\\
      # API backend: proxied to agent_runtime, has its own auth\\
      - \"traefik.http.routers.hive-api-bypass.rule=Host(\\\`hive.shivelymedia.com\\\`) \\&\\& PathPrefix(\\\`/api/backend/\\\`)\"\\
      - \"traefik.http.routers.hive-api-bypass.entrypoints=websecure\"\\
      - \"traefik.http.routers.hive-api-bypass.priority=25\"\\
      - \"traefik.http.routers.hive-api-bypass.tls=true\"\\
      - \"traefik.http.routers.hive-api-bypass.tls.certresolver=cfdns\"\\
      - \"traefik.http.routers.hive-api-bypass.service=hive-ext\"\\
      - \"traefik.http.routers.hive-api-bypass.middlewares=globalHeaders@file,secureHeaders@file\"\\
      # Next.js RSC requests: client-side navigation on already-authenticated pages\\
      - \"traefik.http.routers.hive-rsc-bypass.rule=Host(\\\`hive.shivelymedia.com\\\`) \\&\\& QueryRegexp(\\\`_rsc\\\`, \\\`.+\\\`)\"\\
      - \"traefik.http.routers.hive-rsc-bypass.entrypoints=websecure\"\\
      - \"traefik.http.routers.hive-rsc-bypass.priority=25\"\\
      - \"traefik.http.routers.hive-rsc-bypass.tls=true\"\\
      - \"traefik.http.routers.hive-rsc-bypass.tls.certresolver=cfdns\"\\
      - \"traefik.http.routers.hive-rsc-bypass.service=hive-ext\"\\
      - \"traefik.http.routers.hive-rsc-bypass.middlewares=globalHeaders@file,secureHeaders@file\"" "$COMPOSE"

echo "Bypass routers added."
echo ""
echo "Verifying:"
grep -n 'hive-api-bypass\|hive-rsc-bypass' "$COMPOSE"

