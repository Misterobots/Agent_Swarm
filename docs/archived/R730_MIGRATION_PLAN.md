# R730 Storage & Monitoring Offload Plan

**Status**: Planning Phase  
**Target**: Migrate diagnostic/monitoring stack from Justin-PC (execution_plane) to R730  
**Expected Storage Savings**: ~50-70GB initially, +5GB/month (metrics retention)  
**CPU Impact**: -15-20% load on Justin-PC, +5-8% on R730

---

## 🎯 Strategy Overview

**Cleanest architecture**: Create a **Gateway/Ops layer on R730** with centralized routing and monitoring, leaving **Justin-PC as a pure compute/inference node**.

| Component | Current Location | Target | Rationale |
|-----------|------------------|--------|-----------|
| **Traefik (Reverse Proxy)** | Justin-PC | R730 | Central routing layer; unified API gateway for all services |
| **Prometheus** | Justin-PC | R730 | Metrics storage is I/O heavy; R730 has spare disk |
| **Grafana** | Justin-PC | R730 | Read-only dashboard UI; low resource cost |
| **Loki** | Justin-PC | R730 | Log aggregation storage; 30-40GB/quarter |
| **Promtail** | Justin-PC | R730 | Log shipper agent; minimal CPU |
| **cAdvisor** | Justin-PC | R730 | Container monitoring; lightweight |
| **Redis (Queue)** | Justin-PC | R730 | Queue persistence; can move with monitoring |

**R730 becomes Gateway/Ops Hub**:
- Traefik (reverse proxy entry point)
- Prometheus & Grafana (metrics + dashboards)
- Loki & Promtail (log aggregation)
- cAdvisor (container monitoring)
- Redis Queue (task persistence)
- Open-WebUI (primary chat gateway)
- Ollama inference (secondary solver)

**Justin-PC becomes Compute/Inference Node** (GPU-dedicated):
- Ollama (primary heavy inference)
- ComfyUI (generative art workloads)
- BMO Voice (Home Assistant voice agent with RVC)
- Voice Engine (TTS generation)
- OpenHands (sandboxed development)
- Agent Runtime (core FastAPI engine)

**Stay on Control Node** (Identity/Observability):
- SPIRE Server (zero-trust identity)
- Langfuse (LLM trace collection)
- PostgreSQL (identity database)
- ClickHouse (telemetry warehouse)
- MinIO (blob storage)

---

## 📊 Capacity Analysis

### Current Storage Utilization (Justin-PC)

```
Prometheus data:     ~15-20 GB  (1-month retention)
Grafana configs:     ~500 MB
Loki data:          ~25-35 GB  (30-day retention)
Promtail configs:    ~50 MB
Redis queue:         ~2-5 GB   (persistent)
Docker volumes:      ~5-10 GB
─────────────────────────────────
ESTIMATED TOTAL:     ~50-75 GB
```

### R730 Available Resources

```
Dell R730 @ 192.168.2.103:
- CPU: 24 cores (Intel Xeon E5-2680 v3) - currently ~5-10% used
- RAM: 384GB - currently ~50GB used (Ollama + Open-WebUI)
- Storage: 2x 480GB SSD (RAID 1) = ~450GB usable
  → Current usage: ~80-100GB (Ollama models)
  → Available for monitoring: ~150-200GB
- GPU: Nvidia RTX 3070 Ti (8GB VRAM) - not needed for monitoring
```

### Justin-PC Impact Post-Migration

```
Before:  80-100GB used on 500GB drive (~16% utilization)
After:   25-35GB used on 500GB drive (~5-7% utilization)
CPU Load: 25-30% → 10-15% (especially during log ingestion peaks)
Memory: 32GB (50-60% used) → 32GB (35-45% used)
```

---

## 🏗️ Migration Steps

### Phase 1: Prepare R730 (1-2 hours)

**1.1 Verify R730 Connectivity & Networking**
```bash
# From Justin-PC, verify R730 is reachable
ping 192.168.2.103
ssh ubuntu@192.168.2.103  # Test SSH access

# Check R730 disk space
df -h /  # Should show ~150GB+ free
```

**1.2 Extend R730 Docker Compose**
- Update `r730_gateway/docker-compose.yml` to include monitoring stack
- Add shared volumes for metrics storage → `/data/monitoring` on R730

**1.3 Network Configuration**
- Prometheus on R730 scrapes metrics from Justin-PC by hostname
- Promtail ships logs to Loki (same R730 network)
- Grafana dashboard accessible from Tailscale

### Phase 2: Deploy Gateway Stack to R730 (45 mins)

**2.1 Add Traefik + Monitoring to R730 Compose**

File: `r730_gateway/docker-compose.yml`
```yaml
version: '3.8'

services:
  # REVERSE PROXY - Central routing layer for all services
  traefik:
    image: traefik:v3.0
    container_name: traefik-gateway
    hostname: traefik
    command:
      - "--api.dashboard=true"
      - "--api.insecure=true"  # Move to secure in production
      - "--providers.docker=true"
      - "--providers.docker.exposedByDefault=false"
      - "--providers.docker.network=ai_lab_net"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--log.level=INFO"
    ports:
      - "80:80"        # HTTP traffic (primary gateway)
      - "443:443"      # HTTPS
      - "8080:8080"    # Traefik Dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"
      - "justin-pc:192.168.2.101"      # Route to Justin-PC for compute services
      - "control-node:192.168.2.102"   # Route to Control Node if needed
    networks:
      - ai_lab_net
    restart: unless-stopped
    labels:
      - "com.example.description=Agentic Hive Central Gateway"

  # METRICS COLLECTION
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus-r730
    volumes:
      - ./config/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=90d'  # Keep 3 months of metrics
    networks:
      - ai_lab_net
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.prometheus.rule=PathPrefix(`/prometheus`)"
      - "traefik.http.routers.prometheus.entrypoints=web"
      - "traefik.http.services.prometheus.loadbalancer.server.port=9090"

  # LOG AGGREGATION
  loki:
    image: grafana/loki:latest
    container_name: loki-r730
    volumes:
      - ./config/loki:/etc/loki
      - loki_data:/tmp/loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/loki.yml
    networks:
      - ai_lab_net
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.loki.rule=PathPrefix(`/loki`)"
      - "traefik.http.routers.loki.entrypoints=web"
      - "traefik.http.services.loki.loadbalancer.server.port=3100"

  # LOG SHIPPING AGENT (scrapes container logs from Justin-PC via Docker API)
  promtail:
    image: grafana/promtail:latest
    container_name: promtail-r730
    volumes:
      - ./config/promtail:/etc/promtail
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
    command: -config.file=/etc/promtail/promtail.yml
    networks:
      - ai_lab_net
    restart: always
    # No exposed ports; ships logs internally to Loki

  # CONTAINER METRICS (scrapes cgroup stats)
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor-r730
    ports:
      - "8888:8080"  # Use 8888 to avoid conflict with Traefik dashboard
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    devices:
      - /dev/kmsg
    networks:
      - ai_lab_net
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.cadvisor.rule=PathPrefix(`/cadvisor`)"
      - "traefik.http.routers.cadvisor.entrypoints=web"
      - "traefik.http.services.cadvisor.loadbalancer.server.port=8080"

  # ANALYTICS DASHBOARD
  grafana:
    image: grafana/grafana:latest
    container_name: grafana-r730
    ports:
      - "3001:3000"  # Port 3001 to avoid conflict with Langfuse @ 3000
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_SECURITY_SECRET_KEY=hive_secret_key_for_persistence
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./provisioning:/etc/grafana/provisioning
    networks:
      - ai_lab_net
    depends_on:
      - prometheus
      - loki
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=PathPrefix(`/grafana`)"
      - "traefik.http.routers.grafana.entrypoints=web"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"

  # PERSISTENT QUEUE
  redis:
    image: redis:7.2-alpine
    container_name: redis-r730
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - ai_lab_net
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.redis.rule=PathPrefix(`/redis`)"
      - "traefik.http.routers.redis.entrypoints=web"
      - "traefik.http.services.redis.loadbalancer.server.port=6379"

networks:
  ai_lab_net:
    driver: bridge
    name: ai_lab_net

volumes:
  prometheus_data:
  loki_data:
  grafana_data:
  redis_data:
```

**2.2 Copy & Adapt Configs from Justin-PC to R730**
```bash
# SSH into R730
ssh ubuntu@192.168.2.103

# Copy monitoring configs from Justin-PC
scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/prometheus \
  ~/r730_gateway/config/

scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/loki \
  ~/r730_gateway/config/

scp -r ubuntu@192.168.2.101:~/Home_AI_Lab/execution_plane/config/promtail \
  ~/r730_gateway/config/

# Update Prometheus targets to scrape Justin-PC containers remotely
cat ~/r730_gateway/config/prometheus/prometheus.yml | sed 's|localhost:9100|192.168.2.101:9100|g' \
  > ~/r730_gateway/config/prometheus/prometheus.yml.new && \
  mv ~/r730_gateway/config/prometheus/prometheus.yml.new ~/r730_gateway/config/prometheus/prometheus.yml

# Add cAdvisor target for Justin-PC
echo """
  - job_name: 'cadvisor-justin'
    static_configs:
      - targets: ['192.168.2.101:8080']
""" >> ~/r730_gateway/config/prometheus/prometheus.yml
```

**2.3 Deploy to R730**
```bash
cd ~/r730_gateway
docker compose up -d traefik prometheus loki promtail cadvisor grafana redis
docker compose logs -f traefik  # Verify startup
```

**2.4 Configure Grafana Datasources**
```bash
# Access Grafana @ http://192.168.2.103:3001 (admin/admin)
# Create Prometheus datasource:
#   Name: Prometheus
#   URL: http://prometheus-r730:9090
#   Access: Server
#
# Create Loki datasource:
#   Name: Loki
#   URL: http://loki-r730:3100
#   Access: Server
```

### Phase 3: Validate Gateway & Metrics (30 mins)

**3.1 Test Traefik Routing to Justin-PC**
```bash
# From any machine on network:
curl -v http://192.168.2.103:80/

# Should resolve through Traefik on R730 to Justin-PC services
# Check Traefik dashboard
curl http://192.168.2.103:8080/dashboard/

# Verify Docker network dns
docker exec traefik-gateway ping justin-pc  # Should resolve to 192.168.2.101
```

**3.2 Verify Prometheus Scraping**
```bash
# Check Prometheus targets
curl http://192.168.2.103:9090/api/v1/targets | jq '.data.activeTargets[] | .labels'

# Should show targets from:
#   - Prometheus itself (localhost:9090)
#   - cAdvisor (localhost:8888)
#   - Justin-PC cAdvisor (192.168.2.101:8080)
#   - Justin-PC Ollama (192.168.2.101:11434)
```

**3.3 Check Log Flow**
```bash
# Open browser to Grafana dashboard
# http://192.168.2.103:3001 (admin/admin)

# Verify Loki datasource is active
# Run sample query: {job="docker"}

# Should show logs from containers on both R730 and Justin-PC
```

**3.4 Test Cross-Node Traffic**
```bash
# Verify Traefik can route to Justin-PC
curl -H "Host: justin-pc" http://192.168.2.103/

# Should reach Justin-PC services (ComfyUI, Ollama, Agent Runtime, etc.)
```

### Phase 4: Decommission Justin-PC Monitoring (20 mins, staggered)

**⚠️ CRITICAL: Traefik must migrate FIRST**

The Agent Runtime container on Justin-PC likely has Traefik labels for routing. We need to:
1. Start R730 Traefik with Justin-PC remote targets configured
2. Test all routes work through R730 Traefik
3. **Then** remove Justin-PC Traefik

**4.1 Update Agent Runtime Labels for R730 Traefik**

Before removing Justin-PC Traefik, update routing labels to be discovered by R730 Traefik:

File: `execution_plane/docker-compose.yml` (Agent Runtime service)
```yaml
  agent-runtime:
    # ... existing config ...
    labels:
      # These labels will now be discovered by R730 Traefik via Docker API
      - "traefik.enable=true"
      - "traefik.http.routers.agent-runtime.rule=PathPrefix(`/swarm`)"
      - "traefik.http.routers.agent-runtime.entrypoints=web"
      - "traefik.http.services.agent-runtime.loadbalancer.server.port=8000"
```

**4.2 Remove Traefik from Justin-PC**

File: `execution_plane/docker-compose.yml` - Delete entire `traefik` service block:
```yaml
# DELETE THIS:
  traefik:
    image: traefik:v3.0
    container_name: traefik
    # ... all config ...
```

**4.3 Remove Monitoring Services from Justin-PC**

File: `execution_plane/docker-compose.yml` - Delete these service blocks:
```yaml
# DELETE:
  prometheus: ...
  grafana: ...
  loki: ...
  promtail: ...
  cadvisor: ...
  redis_queue: ...
```

**4.4 Remove Monitoring Volumes**

File: `execution_plane/docker-compose.yml` - Delete volume definitions:
```yaml
# DELETE from volumes: section:
  prometheus_data:
  grafana_data:
  loki_data:
  redis_data:
```

**4.5 Reload Justin-PC Stack**
```bash
ssh ubuntu@192.168.2.101
cd ~/Home_AI_Lab/execution_plane

# Stop all containers
docker-compose down -v  # -v removes volumes

# Verify deletions committed
git diff docker-compose.yml | head -50  # Review changes

# Restart with new config
docker-compose up -d

# Verify services
docker-compose ps
# Should show: spire-agent, ollama, bmo-voice, voice-engine, openhands, agent-runtime, comfyui
```

**4.6 Validate Justin-PC Is Still Reachable**
```bash
# From Justin-PC, test R730 can route to it
curl -v http://192.168.2.103/swarm/docs

# From R730, verify Docker API can still reach Justin-PC containers
docker exec traefik-gateway curl http://host.docker.internal:8080/metrics | head -5
```

### Phase 5: Update Architecture Documentation

**5.1 Update CONNECTION_REFERENCE.md**

Primary entry point changes from Justin-PC to R730:

```markdown
## 🖥️ User Interfaces (Web UIs)

| Interface                | URL                         | Hosted On    | Purpose                                                    |
| :----------------------- | :-------------------------- | :----------- | :--------------------------------------------------------- |
| **Traefik Gateway** ⭐   | `http://192.168.2.103:80`   | Dell R730    | Central reverse proxy for ALL services (new primary entry) |
| **Open-WebUI Gateway**   | `http://192.168.2.103:3000` | Dell R730    | Primary chat interface to interact with the Swarm.         |
| **Langfuse Dashboard**   | `http://192.168.2.102:3000` | Control-Node | Live tracking of LLM traces, MarsRL Process Rewards.       |
| **Grafana Portal** ⭐    | `http://192.168.2.103:3001` | Dell R730    | Ops dashboards, metrics, logs (moved from Justin-PC)       |
| **Prometheus Metrics**   | `http://192.168.2.103:9090` | Dell R730    | Time-series metrics database (moved from Justin-PC)        |
| **Loki Logs API**        | `http://192.168.2.103:3100` | Dell R730    | Log aggregation backend (moved from Justin-PC)             |
| **Traefik Dashboard**    | `http://192.168.2.103:8080` | Dell R730    | Live routing and load balancer metrics                     |
| **cAdvisor Metrics**     | `http://192.168.2.103:8888` | Dell R730    | Container resource monitoring                              |
| **OpenHands Sandbox**    | `http://192.168.2.103/hands` via Traefik | Dell R730    | Docker-in-Docker sandbox (routed from Justin-PC)           |
| **ComfyUI**              | `http://192.168.2.103/comfy` via Traefik | Dell R730    | Image/3D generation (routed from Justin-PC)                |
```

**5.2 Network Topology Update**

```markdown
## 🌐 Architecture After Migration

### Gateway Layer (R730)
```
R730 Traefik (port 80)
  ├─ Direct: Prometheus, Grafana, Loki, cAdvisor, Redis
  └─ Routed: Agent Runtime, ComfyUI, OpenHands, Ollama, BMO Voice (all on Justin-PC)

Control Plane (Dell Wyse)
  ├─ SPIRE Server (zero-trust identity)
  ├─ Langfuse (LLM observability)
  └─ PostgreSQL, ClickHouse, MinIO
```

### Compute Layer (Justin-PC)
```
Justin-PC (no reverse proxy)
  ├─ Ollama (primary inference - RTX 5060 Ti)
  ├─ ComfyUI (generative workloads)
  ├─ BMO Voice (Home Assistant agent)
  ├─ Voice Engine (TTS)
  ├─ OpenHands (sandboxed dev)
  └─ Agent Runtime (FastAPI engine)
```

**Benefits of this architecture:**
- ✅ Single entry point (R730:80) for all UIs
- ✅ Compute node (Justin-PC) has no external routing overhead
- ✅ Storage/metrics isolated from GPU workloads
- ✅ Easy to scale: add more compute nodes behind Traefik
```

### Phase 6: Full System Validation (45 mins)

**6.1 Traefik Routing Verification**

```bash
# Test each route through R730 Traefik
echo "Testing routes through R730 Traefik..."

# Test metrics services (local to R730)
curl -I http://192.168.2.103/prometheus  # Should 200
curl -I http://192.168.2.103/grafana      # Should redirect or 200
curl -I http://192.168.2.103/cadvisor     # Should 200

# Test compute services (routed to Justin-PC)
curl -I http://192.168.2.103/swarm/docs   # Agent Runtime Swagger
curl -I http://192.168.2.103/comfy        # ComfyUI
curl -I http://192.168.2.103/hands        # OpenHands

# Should all succeed with 200/302 (redirects ok)
```

**6.2 Metrics Collection Verification**

```bash
# Verify Prometheus is scraping from Justin-PC
curl http://192.168.2.103:9090/api/v1/query?query=up | jq '.data.result[] | {job:.metric.job, instance:.metric.instance}'

# Expected output should include:
#  - prometheus (local)
#  - ollama (192.168.2.101)
#  - cadvisor (192.168.2.101)
#  - agent-runtime (192.168.2.101)
```

**6.3 Log Flow Verification**

```bash
# Query Loki for recent logs (past 5 minutes)
SINCE=$(($(date +%s) - 300))000000000  # 5 min ago in nanoseconds
curl "http://192.168.2.103:3100/loki/api/v1/query_range" \
  -G --data-urlencode 'query={job="docker"}' \
     --data-urlencode "start=$SINCE" \
     --data-urlencode "end=$(date +%s)000000000" | jq '.data.result | length'

# Should return >0 (at least some logs)
```

**6.4 Grafana Dashboard Verification**

```bash
# Access Grafana @ http://192.168.2.103:3001 (admin/admin)
# Verify:
#  1. Prometheus datasource is healthy (Settings > Data Sources > Prometheus > Test)
#  2. Loki datasource is healthy (Settings > Data Sources > Loki > Test)
#  3. Dashboards show metrics from both R730 and Justin-PC
#  4. Logs appear in Explore > Loki
```

**6.5 Justin-PC Isolation Verification**

```bash
# Verify Justin-PC containers are NOT running Traefik/Monitoring
ssh ubuntu@192.168.2.101 "cd ~/Home_AI_Lab/execution_plane && docker-compose ps"

# Expected OUTPUT (should NOT show traefik, prometheus, grafana, loki, promtail, cadvisor, redis_queue):
# NAME                      STATUS              PORTS
# spire-agent               Up                  ...
# ollama_gpu                Up                  192.168.2.101:11434->11434/tcp
# bmo_voice_gpu             Up                  192.168.2.101:8100->8000/tcp
# voice_engine_gpu          Up                  ...
# openhands_sandbox         Up                  192.168.2.101:3000->3000/tcp
# comfyui_gpu               Up                  192.168.2.101:8188->8188/tcp
# agent_runtime             Up                  192.168.2.101:8008->8000/tcp
```

**6.6 Storage Verification**

```bash
# Check Justin-PC free space (should be ~50-75GB more)
ssh ubuntu@192.168.2.101 "df -h / | grep -E '(Filesystem|^/)'

# Expected: should show ~70-80% free (up from ~85% used before)
```

**6.7 Load Testing (Optional)**

```bash
# Simulate user requests to verify routing stability
for i in {1..10}; do
  echo "Request $i..."
  curl -s http://192.168.2.103/swarm/v1/models | jq '.data[0].id'
  sleep 2
done

# All should succeed without Traefik errors
```

---

## 📈 Storage Impact Timeline

```
Week 1:  Justin-PC gains ~50GB free space
         R730 used: 120GB → 180GB
         
Week 2:  Prometheus grows ~1.5GB/week  
         Loki grows ~3GB/week
         
Month 1: Total monitoring storage: ~35-40GB on R730
         Justin-PC stress: 60% reduction in I/O
         
Q1:      Loki archives @ 60 days: ~24GB archived to external storage
```

---

## ⚠️ Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Traefik routing breaks during migration** | Run both Traefik instances in parallel (Justin-PC on :81, R730 on :80) for 1 hour; verify all routes work before shutting down old |
| **Network latency to Justin-PC services** | Traefik adds ~2-5ms per hop (negligible for home lab); routing happens at L4 (low overhead) |
| **R730 disk fills with logs** | Set retention: Prometheus 90 days, Loki 60 days; configure log rotation in Promtail |
| **Metrics loss during Traefik switchover** | Both Traefik instances collect metrics in parallel; Prometheus merge query once both are stable |
| **R730 Traefik fails → all UIs down** | Keep rollback plan; verify R730 stability for 48 hours before full commitment |
| **Justin-PC containers fail to register with R730 Traefik** | Verify Docker network connectivity; test `docker exec traefik-gateway ping justin-pc` |
| **Promtail loses logs during migration** | Loki has in-memory buffer (configurable); validate no log gaps in Grafana after cutover |

---

---

## 🚀 Quick Reference: Post-Migration Access

All services now accessible through **R730 Traefik Gateway** @ `http://192.168.2.103:80`

| Service | Direct URL <sup>*</sup> | Routed URL | Purpose |
|---------|------------------------|-----------|---------|
| **Grafana** | `http://192.168.2.103:3001` | `http://192.168.2.103/grafana` | Dashboards & analytics |
| **Prometheus** | `http://192.168.2.103:9090` | `http://192.168.2.103/prometheus` | Metrics DB & queries |
| **Loki** | `http://192.168.2.103:3100` | `http://192.168.2.103/loki` | Log aggregation API |
| **cAdvisor** | `http://192.168.2.103:8888` | `http://192.168.2.103/cadvisor` | Container metrics |
| **Agent Runtime** | - | `http://192.168.2.103/swarm` | FastAPI engine (Justin-PC) |
| **ComfyUI** | - | `http://192.168.2.103/comfy` | Generative (Justin-PC) |
| **OpenHands** | - | `http://192.168.2.103/hands` | Sandbox dev (Justin-PC) |
| **Traefik Dashboard** | `http://192.168.2.103:8080` | - | Gateway metrics |

<sup>*</sup> Direct URLs bypass Traefik routing if needed

---

## 📝 Optional: Further Optimizations

**Can also move (lower priority):**
1. **Open-WebUI UI server** (currently hosted on R730) - move to Control Node for centralization
2. **Ollama on R730** - can reduce to CPU-only inference mode if needed for storage
3. **Docker registry/artifact caching** - move to R730 to reduce Justin-PC disk churn

**Things NOT to move:**
- ComfyUI (GPU-bound on RTX 5060 Ti)
- Agent Runtime (primary inference gateway)
- Voice services (GPU-intensive)
- OpenHands (needs Docker-in-Docker close to compute)

---

## 🔄 Rollback Plan

If critical issues occur during migration:

```bash
# ROLLBACK SCENARIO: R730 Traefik is unstable

# 1. Restore Justin-PC Traefik (5 mins)
ssh ubuntu@192.168.2.101
cd ~/Home_AI_Lab/execution_plane
git checkout docker-compose.yml  # Restore original
docker-compose up -d traefik prometheus grafana loki promtail cadvisor redis_queue

# 2. Point clients back to Justin-PC
# Update all .env files and agent configs to use:
#   - Traefik: http://192.168.2.101:81
#   - Prometheus: http://192.168.2.101:9090
#   - Grafana: http://192.168.2.101:80

# 3. Stop R730 monitoring (to avoid confusion)
ssh ubuntu@192.168.2.103
cd ~/r730_gateway
docker-compose down traefik prometheus grafana loki promtail cadvisor redis

# 4. Verify Justin-PC monitoring is healthy
curl -v http://192.168.2.101:81/
docker-compose logs traefik | grep "error\|ERROR"
```

**Estimated rollback time**: 15-20 minutes (with validation)

---

**Timeline**: 3-4 hours total (including testing)  
**Downtime**: ~10 minutes (monitoring blind spot during cutover)  
**Early wins**: Immediate Justin-PC storage relief, reduced CPU contention with ComfyUI
