#!/bin/bash
# SPIRE R730 Workload Registration Script
# Run this on the control plane (Wyse 5070) after R730 SPIRE agent is running

set -e

SPIRE_SERVER="spire-server"
TRUST_DOMAIN="home-ai-lab"

echo "=== SPIRE R730 Workload Registration ==="
echo "Trust Domain: $TRUST_DOMAIN"
echo ""

# Wait for SPIRE Server to be healthy
echo "Waiting for SPIRE Server..."
until docker exec $SPIRE_SERVER /opt/spire/bin/spire-server healthcheck 2>/dev/null; do
    sleep 2
done
echo "SPIRE Server is healthy!"
echo ""

# Step 1: Generate a join token for the R730 SPIRE Agent
echo "Generating join token for R730 SPIRE Agent..."
TOKEN_OUTPUT=$(docker exec $SPIRE_SERVER /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://$TRUST_DOMAIN/spire-agent-r730 \
    -ttl 3600)
echo "$TOKEN_OUTPUT"
echo ""
echo "ACTION REQUIRED: Add the token above to r730_gateway/.env as SPIRE_R730_JOIN_TOKEN=<token>"
echo ""

# Step 2: Register R730 Ollama workload
echo "Registering R730 ollama workload..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/inference/ollama-r730 \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent-r730 \
    -selector docker:label:com.docker.compose.service:ollama \
    -ttl 3600 || echo "Entry may already exist"

echo ""
echo "=== R730 Registration Complete ==="
echo ""

# List all registered entries
echo "All registered workloads:"
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry show

echo ""
echo "All attested agents:"
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server agent list
