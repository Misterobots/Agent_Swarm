# Phase 1 - RECOVERY: Fix Monitoring Stack Deployment

## Problems Encountered

1. ✗ **Loki permission denied**: `mkdir /tmp/loki/rules: permission denied`
   - Root cause: Loki trying to write to /tmp/loki but running as non-root user
   - Fix: Run container as root (user: "0:0") and use proper volume mount

2. ✗ **Promtail config missing**: `/etc/promtail/promtail.yml does not exist`
   - Root cause: Config files not provisioned on Turing
   - Fix: Run setup script to create all config files

3. ⚠️ **Version attribute warning**: Docker Compose version is obsolete
   - Fix: Removed from new compose file

4. ⚠️ **Prometheus & Grafana not starting**: Not visible in docker ps
   - Root cause: Config files missing, chain dependencies failed
   - Fix: Create configs first, then deploy

## Recovery Steps

### Step 1: Copy Setup Files to Turing

Run from Lovelace (where you are now):

```powershell
# Copy the fixed compose file
scp C:\Users\panca\Documents\GitHub\Home_AI_Lab\turing_gateway\docker-compose-monitoring-fixed.yml `
    ubuntu@192.168.2.103:~/turing_gateway/docker-compose-monitoring-fixed.yml

# Copy the setup script
scp C:\Users\panca\Documents\GitHub\Home_AI_Lab\turing_gateway\setup_monitoring.sh `
    ubuntu@192.168.2.103:~/turing_gateway/setup_monitoring.sh
```

### Step 2: Stop Old Stack on Turing

```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway

# Stop old problematic containers
docker compose -f docker-compose-monitoring.yml down || true
docker compose -f docker-compose-monitoring-stack.yml down || true

# Remove old containers to clean slate
docker rm -f prometheus-turing grafana-turing loki-turing promtail-turing || true
docker rm -f redis-monitoring-turing || true

# Optional: Clean volume data if you want fresh start
# docker volume rm turing_gateway_prometheus_data turing_gateway_loki_data turing_gateway_grafana_data turing_gateway_redis_data

echo "✅ Old stack stopped"
EOF
```

### Step 3: Run Setup Script

```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway
chmod +x setup_monitoring.sh
bash setup_monitoring.sh
EOF
```

This will create:
- `config/prometheus/prometheus.yml`
- `config/loki/loki.yml`
- `config/promtail/promtail.yml`
- `provisioning/datasources/prometheus.yml`
- `provisioning/datasources/loki.yml`

### Step 4: Deploy New Fixed Stack

```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway

# Pull latest images
docker compose -f docker-compose-monitoring-fixed.yml pull

# Deploy
docker compose -f docker-compose-monitoring-fixed.yml up -d

# Wait 10 seconds for containers to settle
sleep 10

# Check status
docker compose -f docker-compose-monitoring-fixed.yml ps

# View detailed logs
docker compose -f docker-compose-monitoring-fixed.yml logs --tail=50
EOF
```

### Step 5: Verify All Services Running

```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway

# All containers should show "Up" status
docker compose -f docker-compose-monitoring-fixed.yml ps

# Expected output:
# NAME                      IMAGE                       STATUS
# prometheus-turing           prom/prometheus:latest      Up
# loki-turing                 grafana/loki:latest         Up (healthy)
# promtail-turing             grafana/promtail:latest     Up
# cadvisor-turing             gcr.io/cadvisor...          Up (healthy)
# grafana-turing              grafana/grafana:latest      Up
# redis-monitoring-turing     redis:7.2-alpine            Up

# Check for errors in logs
docker compose -f docker-compose-monitoring-fixed.yml logs --tail=20 | grep -i error
EOF
```

### Step 6: Validate Services Are Responding

```bash
# From Lovelace, verify endpoints
curl -s http://192.168.2.103:9090/-/healthy  # Prometheus
curl -s http://192.168.2.103:3100/ready      # Loki  
curl -s http://192.168.2.103:9080            # Promtail
curl -s http://192.168.2.103:8888/           # cAdvisor
curl -s http://192.168.2.103:3001/api/health # Grafana
```

## Quick Reference: Access Points

| Service         | Port | URL                      | Status Check |
|-----------------|------|--------------------------|--------------|
| Prometheus      | 9090 | http://192.168.2.103:9090| /-/healthy   |
| Grafana         | 3001 | http://192.168.2.103:3001| /api/health  |
| Loki            | 3100 | http://192.168.2.103:3100| /ready       |
| cAdvisor        | 8888 | http://192.168.2.103:8888| /            |
| Promtail        | 9080 | http://192.168.2.103:9080| /targets     |

## If Issues Persist

### Check specific container logs:
```bash
ssh ubuntu@192.168.2.103 << 'EOF'
docker logs prometheus-turing --tail=20
docker logs loki-turing --tail=20
docker logs promtail-turing --tail=20
docker logs grafana-turing --tail=20
EOF
```

### Restart single service:
```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway
docker compose -f docker-compose-monitoring-fixed.yml restart loki-turing
docker logs loki-turing --tail=20
EOF
```

### Reset volumes (DESTRUCTIVE - loses data):
```bash
ssh ubuntu@192.168.2.103 << 'EOF'
cd ~/turing_gateway
docker compose -f docker-compose-monitoring-fixed.yml down -v
docker compose -f docker-compose-monitoring-fixed.yml up -d
EOF
```

## Next: Phase 2 Tasks (After successful deployment)

Once all services are running:
1. ✅ Access Grafana at http://192.168.2.103:3001 (admin/admin)
2. ✅ Add Prometheus datasource  
3. ✅ Add Loki datasource
4. ✅ Create dashboards for Lovelace and Turing
5. ✅ Configure log scraping from both nodes
