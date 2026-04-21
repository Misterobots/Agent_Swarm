#!/bin/bash
# SPIRE Turing Workload Registration Script
# Run this on the control plane (Hopper) after Turing SPIRE agent is running

set -e

SPIRE_SERVER="spire-server"
TRUST_DOMAIN="home-ai-lab"

echo "=== SPIRE Turing Workload Registration ==="
echo "Trust Domain: $TRUST_DOMAIN"
echo ""

# Wait for SPIRE Server to be healthy
echo "Waiting for SPIRE Server..."
until docker exec $SPIRE_SERVER /opt/spire/bin/spire-server healthcheck 2>/dev/null; do
    sleep 2
done
echo "SPIRE Server is healthy!"
echo ""

# Step 1: Generate a join token for the Turing SPIRE Agent
echo "Generating join token for Turing SPIRE Agent..."
TOKEN_OUTPUT=$(docker exec $SPIRE_SERVER /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://$TRUST_DOMAIN/spire-agent-Turing \
    -ttl 3600)
echo "$TOKEN_OUTPUT"
echo ""
echo "ACTION REQUIRED: Add the token above to turing_gateway/.env as SPIRE_TURING_JOIN_TOKEN=<token>"
echo ""

# Step 2: Register Turing Ollama workload
echo "Registering Turing ollama workload..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/inference/ollama-Turing \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent-Turing \
    -selector docker:label:com.docker.compose.service:ollama \
    -ttl 3600 || echo "Entry may already exist"

echo ""
echo "=== Turing Registration Complete ==="
echo ""

# List all registered entries
echo "All registered workloads:"
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry show

echo ""
echo "All attested agents:"
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server agent list

