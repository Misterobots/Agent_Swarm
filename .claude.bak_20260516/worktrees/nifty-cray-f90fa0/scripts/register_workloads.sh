#!/bin/bash
# SPIRE Workload Registration Script
# Run this after SPIRE Server is running to register all agent workloads

set -e

SPIRE_SERVER="spire-server"
TRUST_DOMAIN="home-ai-lab"

echo "=== SPIRE Workload Registration ==="
echo "Trust Domain: $TRUST_DOMAIN"
echo ""

# Wait for SPIRE Server to be healthy
echo "Waiting for SPIRE Server..."
until docker exec $SPIRE_SERVER /opt/spire/bin/spire-server healthcheck 2>/dev/null; do
    sleep 2
done
echo "SPIRE Server is healthy!"
echo ""

# Generate a join token for the SPIRE Agent
echo "Generating join token for SPIRE Agent..."
JOIN_TOKEN=$(docker exec $SPIRE_SERVER /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://$TRUST_DOMAIN/spire-agent \
    -ttl 3600 | grep -oP 'Token:\s+\K\S+')
echo "Join Token: $JOIN_TOKEN"
echo ""

# Save token for agent bootstrap
# echo "$JOIN_TOKEN" > execution_plane/config/spire/.join_token
echo "Token generated successfully."
echo "ACTION REQUIRED: Copy the token above and use it to start the SPIRE Agent on the Execution Plane."

echo ""

# Register Agent Runtime workload
echo "Registering agent-runtime workload..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/agent/runtime \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent \
    -selector docker:label:com.docker.compose.service:agent-runtime \
    -ttl 3600 || echo "Entry may already exist"

# Register Agent UI workload
echo "Registering agent-ui workload..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/agent/ui \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent \
    -selector docker:label:com.docker.compose.service:agent-ui \
    -ttl 3600 || echo "Entry may already exist"

# Register Router Agent (runs in agent-runtime)
echo "Registering router workload..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/agent/router \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent \
    -selector docker:label:spiffe.io/spiffe-id:spiffe://home-ai-lab/agent/runtime \
    -ttl 3600 || echo "Entry may already exist"

# Register Ephemeral Task workloads (wildcard pattern)
echo "Registering ephemeral task pattern..."
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://$TRUST_DOMAIN/task/ephemeral \
    -parentID spiffe://$TRUST_DOMAIN/spire-agent \
    -selector docker:env:TASK_TYPE:ephemeral \
    -ttl 300 || echo "Entry may already exist"  # 5-minute TTL for tasks

echo ""
echo "=== Registration Complete ==="
echo ""

# List all registered entries
echo "Registered workloads:"
docker exec $SPIRE_SERVER /opt/spire/bin/spire-server entry show

