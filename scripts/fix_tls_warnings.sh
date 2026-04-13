#!/bin/bash
# Fix TLS options on bypass routers to match hive-ext (securetls@file + domains)
COMPOSE="/home/misterobots/Home_AI_Lab/r730_gateway/docker-compose.yml"

# Add tls.options to hive-api-bypass (after certresolver line)
sed -i '/hive-api-bypass\.tls\.certresolver=cfdns/a\      - "traefik.http.routers.hive-api-bypass.tls.options=securetls@file"\n      - "traefik.http.routers.hive-api-bypass.tls.domains[0].main=shivelymedia.com"\n      - "traefik.http.routers.hive-api-bypass.tls.domains[0].sans=*.shivelymedia.com"' "$COMPOSE"

# Add tls.options to hive-rsc-bypass (after certresolver line)
sed -i '/hive-rsc-bypass\.tls\.certresolver=cfdns/a\      - "traefik.http.routers.hive-rsc-bypass.tls.options=securetls@file"\n      - "traefik.http.routers.hive-rsc-bypass.tls.domains[0].main=shivelymedia.com"\n      - "traefik.http.routers.hive-rsc-bypass.tls.domains[0].sans=*.shivelymedia.com"' "$COMPOSE"

echo "Verifying changes..."
grep -n 'bypass.*tls' "$COMPOSE"
