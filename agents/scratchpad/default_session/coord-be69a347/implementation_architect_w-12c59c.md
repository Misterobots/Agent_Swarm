# architect — coordinate: Plan and build a simple health check script

```json
{
  "name": "write_file",
  "arguments": {
    "path": "/workspace/health_check.sh",
    "content": "#!/bin/bash\n\n# Check if a service is running\ncheck_service() {\n  local service_name=$1\n  if systemctl is-active --quiet $service_name; then\n    echo \"$service_name is running\"\n  else\n    echo \"$service_name is not running\"\n  fi\n}\n\n# Check CPU usage\ncheck_cpu_usage() {\n  local threshold=80\n  local cpu_usage=$(top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\([0-9.]*\)%* id.*/\\1/\" | awk '{print 100 - $1\"%\"}')\n  if (( $(echo \"$cpu_usage > $threshold" | bc -l) )); then\n    echo \"High CPU usage: $cpu_usage\"\n  else\n    echo \"CPU usage is normal: $cpu_usage\"\n  fi\n}\n\n# Check memory usage\ncheck_memory_usage() {\n  local threshold=80\n  local mem_usage=$(free | awk '/Mem/{printf(\"%.2f\"), $3/$2*100}')\n  if (( $(echo \"$mem_usage > $threshold" | bc -l) )); then\n    echo \"High memory usage: $mem_usage%\"\n  else\n    echo \"Memory usage is normal: $mem_usage%\"\n  fi\n}\n\n# Check disk usage\ncheck_disk_usage() {\n  local threshold=80\n  local disk_usage=$(df / | awk 'NR==2{print $5}' | sed 's/%//g')\n  if (( $(echo \"$disk_usage > $threshold" | bc -l) )); then\n    echo \"High disk usage: $disk_usage%\"\n  else\n    echo \"Disk usage is normal: $disk_usage%\"\n  fi\n}\n\n# Main script execution\ncheck_service postgresql\ncheck_service runtime-service\ncheck_cpu_usage\ncheck_memory_usage\ncheck_disk_usage"
  }
}
```