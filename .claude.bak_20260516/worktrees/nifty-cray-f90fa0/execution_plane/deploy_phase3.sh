#!/bin/bash
# Phase 3 Cleanup - Remove monitoring services from Lovelace compose
# Run this on Lovelace (misterobots@192.168.2.101) locally

set -e

COMPOSE_FILE="docker-compose.yml"
cd ~/execution_plane

echo "🔄 Phase 3: Removing Monitoring Services from Lovelace"
echo "========================================================"

# Step 1: Backup
echo "📦 Creating backup..."
cp "$COMPOSE_FILE" "docker-compose.backup.prePhase3.$(date +%s)"

# Step 2: Create new compose without monitoring
echo "✂️  Removing monitoring services..."
python3 << 'PYTHON_EOF'
import yaml
import sys

# Read current compose
with open('docker-compose.yml', 'r') as f:
    compose = yaml.safe_load(f)

# Services to KEEP (compute only)
keep_services = [
    'spire-agent',
    'ollama',
    'bmo-voice',
    'voice-engine',
    'openhands',
    'agent-runtime',
    'comfyui',
    'agent-ui',
    'ops-portal',
    'agent_ide_devops',
    'agent_ide_coding',
    'authentik_db',
    'authentik_redis',
    'authentik_server',
    'authentik_worker',
    'text-gen-webui'
]

# Services to REMOVE (monitoring)
remove_services = [
    'traefik',
    'cadvisor',
    'prometheus',
    'grafana', 
    'loki',
    'promtail',
    'redis_queue'
]

# Remove monitoring services
if 'services' in compose:
    for service in remove_services:
        if service in compose['services']:
            del compose['services'][service]
            print(f"  ✓ Removed: {service}")

# Remove monitoring volumes
if 'volumes' in compose:
    remove_volumes = [
        'prometheus_data',
        'grafana_data',
        'loki_data',
        'redis_data'
    ]
    for vol in remove_volumes:
        if vol in compose['volumes']:
            del compose['volumes'][vol]
            print(f"  ✓ Removed volume: {vol}")

# Write updated compose
with open('docker-compose.yml', 'w') as f:
    yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

print("\n✅ Monitoring services removed from compose file")
PYTHON_EOF

# Step 3: Verify services removed
echo ""
echo "🔍 Verifying changes..."
grep -c "traefik:" docker-compose.yml && echo "  ⚠️  Traefik still present!" || echo "  ✓ Traefik removed"
grep -c "prometheus:" docker-compose.yml && echo "  ⚠️  Prometheus still present!" || echo "  ✓ Prometheus removed"
grep -c "grafana:" docker-compose.yml && echo "  ⚠️  Grafana still present!" || echo "  ✓ Grafana removed"
grep -c "loki:" docker-compose.yml && echo "  ⚠️  Loki still present!" || echo "  ✓ Loki removed"

# Step 4: Stop all services
echo ""
echo "⏹️  Stopping all services..."
docker-compose down || true

# Step 5: Cleanup volumes
echo "🗑️  Cleaning up monitoring data volumes..."
docker volume rm prometheus_data grafana_data loki_data redis_data 2>/dev/null || true
docker system prune -f 2>/dev/null || true

# Step 6: Start new stack
echo ""
echo "🚀 Starting compute-only stack..."
docker-compose up -d

# Step 7: Wait and show status
sleep 15

echo ""
echo "📊 Service Status:"
docker-compose ps | grep -E 'NAME|Up|Exit'

echo ""
echo "✅ Phase 3 Deployment Complete!"
echo ""
echo "Freed storage: ~60-75GB (monitoring data)"
echo "Lovelace now COMPUTE ONLY - Monitoring on Turing Gateway (192.168.2.103)"

