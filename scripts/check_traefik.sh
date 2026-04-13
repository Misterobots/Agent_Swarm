#!/bin/bash
# Get Traefik container labels related to traefik routing
docker inspect traefik --format '{{json .Config.Labels}}' | python3 -c "
import sys, json
labels = json.load(sys.stdin)
for k, v in sorted(labels.items()):
    if 'traefik' in k.lower():
        print(f'{k}: {v}')
"
echo "---"
# Try multiple ways to access Traefik API
echo "Trying internal API on port 8080..."
docker exec traefik wget -qO- http://127.0.0.1:8080/api/overview 2>&1 | head -c 500
echo ""
echo "---"
echo "Trying Traefik API entrypoint..."
# Check if there's an @internal API router
docker exec traefik wget -qO- http://127.0.0.1:8080/api/rawdata 2>&1 | head -c 200
echo ""
echo "---"
# Check insecure API on the internal entrypoint with the right path
docker exec traefik wget -qO- http://127.0.0.1:8080/dashboard/ 2>&1 | head -c 200
