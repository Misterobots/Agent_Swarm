# architect|coder — Configure and set up monitoring agents on each node for CPU, memory, and disk usage.

```json
{
  "name": "write_file",
  "arguments": {
    "path": "/workspace/monitoring_setup.sh",
    "content": "#!/bin/bash\n\n# Install Prometheus, Grafana, Telegraf, InfluxDB, and Node Exporter on each node\n\ncurl -fsSL https://get.docker.com -o get-docker.sh\nsudo sh get-docker.sh\nsudo usermod -aG docker $USER\nnewgrp docker\n\ndocker run --name prometheus -d -p 9090:9090 prom/prometheus\n\ndocker run --name grafana -d -p 3000:3000 grafana/grafana\n\ndocker run --name telegraf -d -v /etc/telegraf:/etc/telegraf -v /var/run/docker.sock:/var/run/docker.sock telegraf/telegraf\n\ndocker run --name influxdb -d -p 8086:8086 influxdata/influxdb\n\ndocker run --name node-exporter -d -p 9100:9100 prom/node-exporter\n"
  }
}
```