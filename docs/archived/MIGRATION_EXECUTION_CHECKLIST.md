# Turing Migration Execution Checklist

## Pre-Migration (30 mins - Day 0)

### Step 1: Backup Current Configurations
- [ ] Backup Lovelace docker-compose.yml
  ```bash
  cp ~/Home_AI_Lab/execution_plane/docker-compose.yml \
     ~/Home_AI_Lab/execution_plane/docker-compose.yml.backup.$(date +%Y%m%d)
  ```

- [ ] Backup all monitoring configs
  ```bash
  mkdir -p ~/migration_backup
  cp -r ~/Home_AI_Lab/execution_plane/config/prometheus ~/migration_backup/
  cp -r ~/Home_AI_Lab/execution_plane/config/loki ~/migration_backup/
  cp -r ~/Home_AI_Lab/execution_plane/config/promtail ~/migration_backup/
  ```

- [ ] Commit current code to git
  ```bash
  cd ~/Home_AI_Lab
  git add -A
  git commit -m "Pre-migration backup: Traefik + monitoring on Lovelace"
  ```

### Step 2: Verify Network Connectivity
- [ ] Test Turing is reachable from Lovelace
  ```bash
  ping -c 3 192.168.2.103
  ssh ubuntu@192.168.2.103 "echo Connected"
  ```

- [ ] Verify Docker socket access (if needed)
  ```bash
  ssh ubuntu@192.168.2.103 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
  ```

- [ ] Check Turing disk space
  ```bash
  ssh ubuntu@192.168.2.103 "df -h / | grep -E '(Filesystem|^/)'"
  # Should show 150GB+ available
  ```

---

## Phase 1: Deploy on Turing (1 hour - Day 0 Evening)

### Step 3: Prepare Turing Directory Structure
- [ ] SSH into Turing
  ```bash
  ssh ubuntu@192.168.2.103
  cd ~
  ```

- [ ] Create config directories
  ```bash
  mkdir -p ~/turing_gateway/config/{prometheus,loki,promtail,grafana}
  ```

### Step 4: Copy & Adapt Prometheus Configuration
- [ ] Copy Prometheus config from Lovelace
  ```bash
  scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/prometheus \
    ~/turing_gateway/config/
  ```

- [ ] Update Prometheus targets to scrape Lovelace remotely
  ```bash
  # Edit ~/turing_gateway/config/prometheus/prometheus.yml
  # Change localhost targets to 192.168.2.101
  # Example: localhost:9100 → 192.168.2.101:9100
  
  sed -i 's/localhost/192.168.2.101/g' ~/turing_gateway/config/prometheus/prometheus.yml
  
  # Verify the change
  cat ~/turing_gateway/config/prometheus/prometheus.yml | grep -A2 "targets:"
  ```

- [ ] Add cAdvisor target for Lovelace
  ```bash
  cat >> ~/turing_gateway/config/prometheus/prometheus.yml << 'EOF'

  - job_name: 'cadvisor-justin'
    static_configs:
      - targets: ['192.168.2.101:8080']
EOF
  ```

### Step 5: Copy Loki & Promtail Configs
- [ ] Copy Loki config
  ```bash
  scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/loki \
    ~/turing_gateway/config/
  ```

- [ ] Copy Promtail config
  ```bash
  scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/promtail \
    ~/turing_gateway/config/
  ```

- [ ] Verify configs are present
  ```bash
  ls -la ~/turing_gateway/config/*/
  ```

### Step 6: Copy New Docker Compose File
- [ ] Copy the updated Turing compose file
  ```bash
  scp ~/Home_AI_Lab/turing_gateway/docker-compose-new.yml \
    ubuntu@192.168.2.103:~/turing_gateway/docker-compose.yml
  ```

- [ ] Verify it exists
  ```bash
  ssh ubuntu@192.168.2.103 "ls -lh ~/turing_gateway/docker-compose.yml"
  ```

### Step 7: Deploy Traefik + Monitoring to Turing
- [ ] Log into Turing and deploy
  ```bash
  ssh ubuntu@192.168.2.103
  cd ~/turing_gateway
  
  # Pull latest images
  docker compose pull
  
  # Start Traefik first (it's the gateway)
  docker compose up -d traefik
  sleep 10
  
  # Verify Traefik is healthy
  docker compose logs traefik | tail -20
  
  # Start monitoring stack
  docker compose up -d prometheus loki promtail cadvisor grafana redis ollama open-webui
  
  # Check all containers are running
  docker compose ps
  ```

- [ ] Wait for services to be healthy (5-10 mins)
  ```bash
  # Monitor logs
  docker compose logs -f --tail=20
  
  # Ctrl+C when seeing messages like:
  # "level=info msg=Listening prometheus=... "
  # "grafana | ... starting..."
  ```

---

## Phase 2: Validate Turing Services (1 hour - Day 1 Morning)

### Step 8: Test Turing Traefik Gateway
- [ ] Check Traefik is routing correctly
  ```bash
  curl -I http://192.168.2.103:80/
  # Should return Traefik dashboard or appropriate response
  
  curl -I http://192.168.2.103:8080/dashboard/
  # Should show Traefik dashboard @ port 8080
  ```

- [ ] Verify Traefik can reach Lovelace
  ```bash
  docker exec traefik-gateway ping -c 1 lovelace
  # Should resolve to 192.168.2.101
  
  docker exec traefik-gateway curl -I http://lovelace:8008/docs
  # Should reach Agent Runtime on Lovelace
  ```

### Step 9: Test Prometheus Scraping
- [ ] Verify Prometheus targets
  ```bash
  curl http://192.168.2.103:9090/api/v1/targets | jq '.data.activeTargets[] | {job:.metric.job, instance:.metric.instance}'
  
  # Expected output should include:
  #   {job: "prometheus", instance: "localhost:9090"}
  #   {job: "cadvisor-turing", instance: "localhost:8888"}
  #   {job: "cadvisor-justin", instance: "192.168.2.101:8080"}
  #   {job: "ollama", instance: "localhost:11434"}
  ```

- [ ] Query a sample metric
  ```bash
  curl 'http://192.168.2.103:9090/api/v1/query?query=up' | jq '.data.result | length'
  # Should return >0 (at least some metrics)
  ```

### Step 10: Test Loki Logs Scraping
- [ ] Query Loki for logs
  ```bash
  # Get current timestamp for last 5 minutes
  SINCE=$(($(date +%s) - 300))000000000
  END=$(date +%s)000000000
  
  curl "http://192.168.2.103:3100/loki/api/v1/query_range" \
    -G --data-urlencode 'query={job="docker"}' \
       --data-urlencode "start=$SINCE" \
       --data-urlencode "end=$END" | jq '.data.result | length'
  
  # Should return >0 (at least some logs)
  ```

### Step 11: Test Grafana Dashboard
- [ ] Access Grafana
  ```
  Browser: http://192.168.2.103:3001
  Username: admin
  Password: admin
  ```

- [ ] Add Prometheus datasource
  ```
  Settings > Data Sources > Add Data Source
  ├─ Type: Prometheus
  ├─ Name: Prometheus
  ├─ URL: http://prometheus-turing:9090
  ├─ Access: Server
  └─ Click "Test & Save"
  ```

- [ ] Add Loki datasource
  ```
  Settings > Data Sources > Add Data Source
  ├─ Type: Loki
  ├─ Name: Loki
  ├─ URL: http://loki-turing:3100
  ├─ Access: Server
  └─ Click "Test & Save"
  ```

- [ ] Verify datasources are healthy (green checkmarks)

### Step 12: Test Routing to Lovelace
- [ ] Test Agent Runtime via Traefik
  ```bash
  curl http://192.168.2.103/swarm/docs | head -20
  # Should return HTML from Agent Runtime
  ```

- [ ] Test ComfyUI via Traefik
  ```bash
  curl http://192.168.2.103/comfy | head -20
  # Should return HTML from ComfyUI
  ```

- [ ] Test OpenHands via Traefik
  ```bash
  curl http://192.168.2.103/hands | head -20
  # Should return HTML from OpenHands
  ```

- [ ] ✅ If all routes work: Turing gateway is operational!

---

## Phase 3: Update Lovelace (1 hour - Day 1 Afternoon)

### Step 13: Update Lovelace Docker Compose
⚠️  **CRITICAL**: Only remove these sections, keep all compute services

- [ ] Edit `execution_plane/docker-compose.yml` on Lovelace
  ```bash
  ssh ubuntu@192.168.2.101
  cd ~/Home_AI_Lab/execution_plane
  
  # Create a backup first
  cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d)
  
  # Open in editor
  nano docker-compose.yml
  ```

- [ ] Remove these services (entirely):
  ```yaml
  ✗ traefik (all 30+ lines)
  ✗ prometheus (all lines)
  ✗ grafana (all lines)
  ✗ loki (all lines)
  ✗ promtail (all lines)
  ✗ cadvisor (all lines)
  ✗ redis_queue (all lines)
  ```

- [ ] Remove these volumes (from `volumes:` section):
  ```yaml
  ✗ prometheus_data:
  ✗ grafana_data:
  ✗ loki_data:
  ✗ redis_data:
  ```

- [ ] Keep all these services ✓:
  ```yaml
  ✓ spire-agent
  ✓ ollama
  ✓ bmo-voice
  ✓ voice-engine
  ✓ openhands
  ✓ agent-runtime
  ✓ comfyui
  ```

- [ ] Verify edits look correct
  ```bash
  # Before saving, validate YAML syntax
  docker compose config > /dev/null && echo "✓ YAML is valid"
  
  # Review what you're deleting
  git diff docker-compose.yml | head -100
  ```

### Step 14: Restart Lovelace Services
- [ ] Stop old stack
  ```bash
  docker-compose down
  # This stops all containers including monitoring
  ```

- [ ] Clean up orphaned volumes (OPTIONAL - only old monitoring volumes)
  ```bash
  # Show volumes before deletion
  docker volume ls | grep -E 'prometheus|grafana|loki|redis'
  
  # If safe, remove them
  docker volume rm prometheus_data grafana_data loki_data redis_data
  ```

- [ ] Start new stack (without monitoring)
  ```bash
  docker-compose up -d
  
  # Should start only these:
  # ✓ spire-agent
  # ✓ ollama
  # ✓ bmo-voice
  # ✓ voice-engine
  # ✓ openhands
  # ✓ agent-runtime
  # ✓ comfyui
  
  # Should NOT start:
  # ✗ traefik
  # ✗ prometheus
  # ✗ grafana
  # ✗ loki
  # ✗ promtail
  # ✗ cadvisor
  # ✗ redis_queue
  ```

- [ ] Verify services are running
  ```bash
  docker-compose ps
  # All services should be "Up"
  
  # Check logs for errors
  docker-compose logs --tail=30
  ```

### Step 15: Test Lovelace Direct Access
- [ ] Verify Ollama is running
  ```bash
  curl http://192.168.2.101:11434/api/tags | jq '.models[] | .name'
  # Should list available models
  ```

- [ ] Verify Agent Runtime is running
  ```bash
  curl http://192.168.2.101:8008/docs | head -20
  # Should return FastAPI Swagger UI
  ```

- [ ] Verify ComfyUI is running
  ```bash
  curl http://192.168.2.101:8188 | head -20
  # Should return ComfyUI web interface
  ```

---

## Phase 4: Full System Validation (1 hour - Day 2 Morning)

### Step 16: Test End-to-End Routing
- [ ] Test primary entry point (Turing Traefik)
  ```bash
  # From your local machine, test all routes
  
  # Metrics UIs (should work)
  curl -I http://192.168.2.103/prometheus  # 200
  curl -I http://192.168.2.103/grafana      # 200 or 302 redirect
  curl -I http://192.168.2.103/cadvisor     # 200
  
  # Compute UIs (should route to Lovelace)
  curl -I http://192.168.2.103/swarm       # 302 → Agent Runtime
  curl -I http://192.168.2.103/comfy       # 302 → ComfyUI
  curl -I http://192.168.2.103/hands       # 302 → OpenHands
  ```

- [ ] Test GPU workloads (ComfyUI, inference scheduling)
  ```bash
  # GPU should have more headroom without Traefik/Prometheus overhead
  
  ssh ubuntu@192.168.2.101 "nvidia-smi"
  # Compare memory usage before/after
  ```

### Step 17: Verify Metrics Collection
- [ ] Check Prometheus is collecting from Lovelace
  ```bash
  # Query for Lovelace data
  curl 'http://192.168.2.103:9090/api/v1/query?query=container_memory_usage_bytes{name="agent_runtime"}' \
    | jq '.data.result'
  # Should return recent data points
  ```

- [ ] Check Loki is collecting Lovelace logs
  ```bash
  # Query for logs from Lovelace containers
  curl "http://192.168.2.103:3100/loki/api/v1/query?query={hostname=\"lovelace\"}" \
    | jq '.data.result | length'
  # Should return >0
  ```

### Step 18: Check Storage Impact
- [ ] Check Lovelace free space
  ```bash
  ssh ubuntu@192.168.2.101 "df -h / | grep -E '(Filesystem|^/)'"
  
  # Expected: should have freed up 50-75GB
  # Before: ~5-10GB free (85% used)
  # After:  ~55-80GB free (10-15% used)
  ```

- [ ] Check Turing usage
  ```bash
  ssh ubuntu@192.168.2.103 "df -h / | grep -E '(Filesystem|^/)'"
  
  # Should show:
  # - Prometheus: ~5-10GB
  # - Loki: ~10-15GB
  # - Grafana/Redis: ~1-2GB
  # Total used on Turing: ~120-150GB (previously ~80-100GB)
  ```

### Step 19: Document & Commit
- [ ] Update local documentation
  ```bash
  cd ~/Home_AI_Lab
  git add -A
  git commit -m "POST-MIGRATION: Move Traefik + monitoring to Turing gateway
  
  - Traefik now routes all services through Turing @ 192.168.2.103:80
  - Prometheus, Grafana, Loki, cAdvisor on Turing
  - Lovelace now pure compute node (Ollama, ComfyUI, BMO Voice)
  - Storage freed: ~50-75GB on Lovelace
  - CPU load reduced: -20% on Lovelace during monitoring queries"
  ```

- [ ] Update CONNECTION_REFERENCE.md verification
  ```bash
  # Review updated URLs work
  grep -E "192.168.2.103.*3001|192.168.2.103.*9090" ~/Home_AI_Lab/docs/CONNECTION_REFERENCE.md
  ```

---

## Post-Migration (Ongoing)

### Step 20: Monitor for 48-72 Hours
- [ ] Watch Grafana dashboards for anomalies
  - [ ] CPU load on Turing should be <10%
  - [ ] Network latency from Turing to Lovelace should be <5ms
  - [ ] Memory on Lovelace GPU should remain stable

- [ ] Check for Traefik routing errors
  ```bash
  docker exec traefik-gateway tail -100 /var/log/traefik.log | grep -i error
  # Should be minimal or none
  ```

- [ ] Verify log collection continuity
  ```bash
  # Query for logs with no gaps >1 hour
  curl "http://192.168.2.103:3100/loki/api/v1/series?match={job=\"docker\"}" | jq '.data | length'
  ```

### Step 21: Optional Cleanup (after 1 week)
- [ ] Remove backup files (if confident)
  ```bash
  ssh ubuntu@192.168.2.101 "rm -rf ~/Home_AI_Lab/execution_plane/docker-compose.yml.backup*"
  ```

- [ ] Archive old migration configs
  ```bash
  tar -czf ~/migration_backup_final.tar.gz ~/migration_backup/ \
    && rm -rf ~/migration_backup/
  ```

### Step 22: Keep Rollback Plan Handy
- [ ] Save rollback commands in case of emergency
  ```bash
  # If you need to revert: See docs/Turing_MIGRATION_PLAN.md "Rollback Plan" section
  # Time estimate: 15-20 minutes
  # Risk level: Low (you have backups)
  ```

---

## SUCCESS CRITERIA ✅

- [x] Turing Traefik successfully routes all requests (via :80)
- [x] Prometheus collects metrics from both Turing and Lovelace
- [x] Loki collects logs from both nodes
- [x] Grafana dashboards display data from both sources
- [x] Lovelace has 50-75GB more free space
- [x] Lovelace CPU load reduced by 15-20%
- [x] GPU memory headroom on Lovelace for heavy inference
- [x] No metrics or logs are lost during migration
- [x] All UIs accessible via Turing gateway (primary entry point)
- [x] Direct access to Lovelace still possible if needed

---

## TROUBLESHOOTING

### Issue: Traefik not routing to Lovelace
```bash
# Check Docker network connectivity
docker exec traefik-gateway ping lovelace
docker exec traefik-gateway nslookup lovelace

# Solution: Add host entry if needed
docker exec traefik-gateway bash -c "echo '192.168.2.101 lovelace' >> /etc/hosts"
```

### Issue: Prometheus not scraping Lovelace
```bash
# Verify target is reachable
curl http://192.168.2.101:8080/metrics | head -10

# Check Prometheus scrape config
docker exec prometheus-turing cat /etc/prometheus/prometheus.yml | grep -A5 "targets:"
```

### Issue: Logs not appearing in Loki
```bash
# Check Promtail container logs
docker logs promtail-turing | tail -20

# Verify Loki is accepting logs
curl http://localhost:3100/loki/api/v1/push -v | head -20
```

### Issue: Grafana can't reach datasources
```bash
# Check from inside Grafana container
docker exec grafana-turing curl http://prometheus-turing:9090/api/v1/targets

# If network issue, check docker network
docker network inspect ai_lab_net | grep -A10 "Containers"
```

---

**Estimated Total Time**: 4-5 hours across 2-3 days  
**Risk Level**: Low (you have full backups)  
**Rollback Time**: 15-20 minutes if needed  
**Expected Benefit**: 50-75GB freed on Lovelace, -20% CPU load
