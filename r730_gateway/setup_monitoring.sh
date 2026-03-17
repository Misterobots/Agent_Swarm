#!/bin/bash
# Setup script for R730 Monitoring Stack
# Run this on R730: bash setup_monitoring.sh

set -e

echo "🚀 Setting up R730 Monitoring Stack..."

WORK_DIR="$HOME/r730_gateway"
cd "$WORK_DIR"

# Create config directories
echo "📁 Creating config directories..."
mkdir -p config/prometheus
mkdir -p config/loki
mkdir -p config/promtail
mkdir -p provisioning/dashboards
mkdir -p provisioning/datasources

# Create Prometheus config if missing
if [ ! -f "config/prometheus/prometheus.yml" ]; then
  echo "📝 Creating prometheus.yml..."
  cat > config/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor-r730:8080']

  - job_name: 'docker'
    static_configs:
      - targets: ['unix:///var/run/docker.sock']
    relabel_configs:
      - source_labels: [__scheme__]
        target_label: __scheme__
        replacement: 'http'
      - source_labels: [__address__]
        target_label: __address__
        replacement: 'localhost:9323'
EOF
fi

# Create Loki config if missing
if [ ! -f "config/loki/loki.yml" ]; then
  echo "📝 Creating loki.yml..."
  cat > config/loki/loki.yml << 'EOF'
auth_enabled: false

ingester:
  chunk_idle_period: 3m
  chunk_retain_period: 1m
  max_chunk_age: 1h
  chunk_encoding: snappy
  chunk_target_size: 1048576
  enforce_rate_limited_streams: false
  max_streams_per_user: 10000
  rate_limit_streams_per_second: 10

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 8
  ingestion_burst_size_mb: 16

schema_config:
  configs:
  - from: 2020-10-24
    store: boltdb-shipper
    object_store: filesystem
    schema: v11
    index:
      prefix: index_
      period: 24h

server:
  http_listen_port: 3100
  log_level: info

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  enabled: false

rulerEnabled: false
EOF
fi

# Create Promtail config if missing
if [ ! -f "config/promtail/promtail.yml" ]; then
  echo "📝 Creating promtail.yml..."
  cat > config/promtail/promtail.yml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki-r730:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        target_label: 'container'
      - source_labels: ['__meta_docker_container_image_name']
        target_label: 'image'

  - job_name: syslog
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*log
EOF
fi

# Create Grafana datasources config
if [ ! -f "provisioning/datasources/prometheus.yml" ]; then
  echo "📝 Creating Grafana Prometheus datasource..."
  cat > provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    orgId: 1
    url: http://prometheus-r730:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 15s
EOF
fi

if [ ! -f "provisioning/datasources/loki.yml" ]; then
  echo "📝 Creating Grafana Loki datasource..."
  cat > provisioning/datasources/loki.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    orgId: 1
    url: http://loki-r730:3100
    jsonData:
      maxLines: 1000
EOF
fi

# Fix permissions
echo "🔐 Setting permissions..."
chmod -R 755 config
chmod -R 755 provisioning
sudo chown -R 65534:65534 config/prometheus  # Prometheus user

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Verify config files:"
echo "   ls -la config/"
echo ""
echo "2. Deploy monitoring stack:"
echo "   docker compose -f docker-compose-monitoring-fixed.yml up -d"
echo ""
echo "3. Check services:"
echo "   docker compose -f docker-compose-monitoring-fixed.yml ps"
echo ""
