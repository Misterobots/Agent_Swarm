#!/bin/bash
# Turing PHASE 1 SETUP - Run these commands on Turing (ubuntu@192.168.2.103)

set -e

echo "=== PHASE 1: Deploy Turing Gateway Stack ==="
echo ""

# Step 3: Create config directories
echo "[Step 3] Creating config directories on Turing..."
mkdir -p ~/turing_gateway/config/{prometheus,loki,promtail,grafana}
echo "✓ Directories created"
echo ""

# Step 4: Copy Prometheus config from Lovelace
echo "[Step 4] Copying Prometheus config from Lovelace..."
scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/prometheus ~/turing_gateway/config/
echo "✓ Prometheus config copied"
echo ""

# Step 4a: Update Prometheus targets to point to Lovelace
echo "[Step 4a] Updating Prometheus targets to scrape Lovelace..."
sed -i 's/localhost/192.168.2.101/g' ~/turing_gateway/config/prometheus/prometheus.yml
echo "✓ Prometheus targets updated to 192.168.2.101"
grep -A2 "targets:" ~/turing_gateway/config/prometheus/prometheus.yml | head -6
echo ""

# Step 4b: Add cAdvisor target for Lovelace
echo "[Step 4b] Adding cAdvisor target for Lovelace..."
cat >> ~/turing_gateway/config/prometheus/prometheus.yml << 'EOF'

  - job_name: 'cadvisor-justin'
    static_configs:
      - targets: ['192.168.2.101:8080']
EOF
echo "✓ cAdvisor target added"
echo ""

# Step 5: Copy Loki & Promtail configs
echo "[Step 5] Copying Loki and Promtail configs..."
scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/loki ~/turing_gateway/config/
scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/promtail ~/turing_gateway/config/
echo "✓ Loki and Promtail configs copied"
ls -la ~/turing_gateway/config/
echo ""

# Step 6: Copy new compose file
echo "[Step 6] Copying docker-compose file to Turing..."
# Note: This assumes the file already exists. If not, you'll need to copy it manually.
# scp ~/docker-compose-new.yml ubuntu@192.168.2.103:~/turing_gateway/docker-compose.yml
echo "✓ (Assuming docker-compose.yml already exists or will be provided)"
echo ""

# Step 7: Deploy to Turing
echo "[Step 7] Starting Docker Compose services on Turing..."
cd ~/turing_gateway

# Pull latest images
echo "  - Pulling Docker images..."
docker compose pull --quiet 2>/dev/null || echo "  (Images already available)"

# Start Traefik first
echo "  - Starting Traefik gateway..."
docker compose up -d traefik
sleep 10

# Verify Traefik is running
echo "  - Checking Traefik status..."
docker compose logs traefik | tail -5 || true

# Start monitoring stack
echo "  - Starting monitoring stack..."
docker compose up -d prometheus loki promtail cadvisor grafana redis ollama open-webui

# Wait for services to stabilize
sleep 15

# Final status
echo ""
echo "[Step 7] Deployment complete! Service status:"
docker compose ps

echo ""
echo "=== PHASE 1 COMPLETE ==="
echo ""
echo "Next steps:"
echo "1. Wait 2-3 minutes for all services to be healthy"
echo "2. Run Phase 2 validation commands"
echo "3. Monitor logs: docker compose logs -f --tail=50"

