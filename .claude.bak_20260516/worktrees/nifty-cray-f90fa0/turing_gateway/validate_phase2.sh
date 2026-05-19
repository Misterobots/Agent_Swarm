#!/bin/bash
# Phase 2 Validation Script - Run on Turing

echo "🔍 Phase 2: Validating Turing Monitoring Stack"
echo "=================================================="
echo ""

# 1. Check all containers are running
echo "1️⃣  Container Status:"
docker compose -f ~/turing_gateway/docker-compose-monitoring-fixed.yml ps
echo ""

# 2. Check Prometheus targets
echo "2️⃣  Prometheus Scrape Targets:"
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, endpoint: .discoveredLabels.endpoint, state: .health}' 2>/dev/null || echo "   (Prometheus not ready yet)"
echo ""

# 3. Check Loki is running
echo "3️⃣  Loki Status:"
curl -s http://localhost:3101/ready && echo "   ✅ Loki Ready" || echo "   ❌ Loki Not Ready"
echo ""

# 4. Check Promtail logs
echo "4️⃣  Promtail Status:"
docker logs promtail-Turing --tail=5 | grep -E "Starting|Connected|Error" || echo "   (Checking logs...)"
echo ""

# 5. Check cAdvisor metrics
echo "5️⃣  cAdvisor Metrics:"
curl -s http://localhost:8888/api/v1.3/machine | jq '.root_fs[0:1]' 2>/dev/null | head -10 || echo "   (cAdvisor collecting metrics...)"
echo ""

# 6. Check Grafana datasources
echo "6️⃣  Grafana Status:"
curl -s http://localhost:3002/api/health | jq '.database' 2>/dev/null || echo "   (Grafana starting up...)"
echo ""

# 7. Memory and CPU usage
echo "7️⃣  Stack Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep -E "prometheus|loki|grafana|cadvisor|promtail|redis" || echo "   (Stats not available yet)"
echo ""

echo "✅ Phase 2 Validation Complete!"

