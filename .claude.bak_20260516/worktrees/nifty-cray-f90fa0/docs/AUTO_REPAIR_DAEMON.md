# Auto-Repair Daemon

Automated health monitoring and repair system for the Agent Swarm infrastructure.

## Overview

The Auto-Repair Daemon continuously monitors critical services and automatically repairs common issues without manual intervention:

- **Authentik database corruption** - Automatically runs REINDEX when "unexpected zero page" errors are detected
- **Container failures** - Restarts crashed or unresponsive Docker containers
- **Database connection issues** - Detects and resolves PostgreSQL connection problems
- **Network connectivity issues** - Monitors and reports node reachability problems

## Quick Start

### On Windows (Lovelace)

```powershell
# Start the daemon
cd agents
.\launch_auto_repair.ps1

# Check status
.\launch_auto_repair.ps1 -Status

# View logs
.\launch_auto_repair.ps1 -Logs

# Stop the daemon
.\launch_auto_repair.ps1 -Stop
```

### On Linux (Turing)

```bash
# Deploy the daemon
cd scripts/deploy
bash deploy_auto_repair.sh

# Check status
sudo systemctl status auto_repair_daemon

# View logs
tail -f ~/Home_AI_Lab/logs/auto_repair.log

# Restart the daemon
sudo systemctl restart auto_repair_daemon

# Stop the daemon
sudo systemctl stop auto_repair_daemon
```

## Configuration

Copy `agents/auto_repair.env.example` to `agents/auto_repair.env` and customize:

```bash
# How often to check service health (seconds)
AUTO_REPAIR_CHECK_INTERVAL=300  # 5 minutes

# Minimum time between repair attempts (seconds)
AUTO_REPAIR_COOLDOWN=600  # 10 minutes

# Node IPs
TURING_IP=192.168.2.103
HOPPER_IP=192.168.2.102
LOVELACE_IP=192.168.2.101

# Authentik database credentials
AUTHENTIK_DB_USER=misterobots
AUTHENTIK_DB_PASSWORD=your_password_here
```

## Monitored Services

### Authentik (Turing)
- **Health Check**: HTTP endpoint `http://192.168.2.103:9000/-/health/live/`
- **Auto-Repair Actions**:
  - Detect database corruption in logs
  - Run `REINDEX DATABASE authentik`
  - Restart container after repair

### PostgreSQL (Hopper)
- **Health Check**: TCP port 5432
- **Auto-Repair Actions**:
  - Restart container if port is unresponsive

### Redis (Hopper)
- **Health Check**: TCP port 6379
- **Auto-Repair Actions**:
  - Restart container if port is unresponsive

### Langfuse (Hopper)
- **Health Check**: HTTP endpoint `http://192.168.2.102:3000/api/public/health`
- **Auto-Repair Actions**:
  - Restart container if endpoint returns 500+ or times out

## How It Works

### Health Check Cycle

1. **Check Service Health** - Every 5 minutes (configurable), the daemon checks all monitored services
2. **Detect Issues** - If a service is unhealthy, analyze logs and error messages
3. **Attempt Repair** - If repair is needed and cooldown has passed, execute repair action
4. **Verify Success** - Log the result and update repair history
5. **Alert on Failures** - After 3 consecutive failures, log a critical alert

### Repair Cooldown

To prevent repair loops, the daemon enforces a cooldown period (default 10 minutes) between repair attempts for the same service. This ensures issues are given time to stabilize after repair.

### Consecutive Failure Tracking

The daemon tracks consecutive failures for each service:
- ✓ 0 failures = Service healthy
- ⚠️ 1-2 failures = Attempting repairs
- 🚨 3+ failures = Critical alert logged (manual intervention needed)

## Common Issues Fixed

### 1. Authentik Database Corruption

**Symptoms:**
- "Server is starting up..." message persists
- Logs show: `index "authentik_*" contains unexpected zero page at block 0`
- Connection errors when accessing auth.shivelymedia.com

**Auto-Repair:**
```bash
# Daemon automatically runs:
docker exec authentik-postgres psql -U misterobots -d authentik -c 'REINDEX DATABASE authentik;'
docker restart authentik
```

**Manual Fix (if daemon fails):**
```bash
ssh misterobots@192.168.2.103
docker exec -e PGPASSWORD=your_password authentik-postgres psql -U misterobots -d authentik -c 'REINDEX DATABASE authentik;'
docker restart authentik
```

### 2. Container Crashes

**Symptoms:**
- Service unreachable
- Docker container shows "Exited" status
- Connection timeouts

**Auto-Repair:**
```bash
# Daemon automatically runs:
docker restart <container_name>
```

### 3. Database Connection Pool Exhaustion

**Symptoms:**
- "Too many connections" errors
- Slow query responses
- Connection timeouts

**Auto-Repair:**
```bash
# Daemon automatically restarts affected services to reset connection pools
docker restart postgres
docker restart langfuse
```

## Logs

### Log Files

- **Main log**: `logs/auto_repair.log`
- **Error log** (Linux only): `logs/auto_repair_error.log`

### Log Format

```
2026-04-28 12:00:00 [INFO] AutoRepair: Starting health check cycle...
2026-04-28 12:00:01 [INFO] AutoRepair: Authentik on Turing: ✓ Healthy
2026-04-28 12:00:02 [WARNING] AutoRepair: PostgreSQL issue detected: Port 5432 not responding
2026-04-28 12:00:03 [INFO] AutoRepair: Attempting auto-repair for PostgreSQL...
2026-04-28 12:00:08 [INFO] AutoRepair: ✓ Repair successful: Container restarted
```

### Viewing Logs

```bash
# Last 50 lines
tail -n 50 logs/auto_repair.log

# Follow in real-time
tail -f logs/auto_repair.log

# Search for repairs
grep "Repair successful" logs/auto_repair.log

# Search for failures
grep "Repair failed" logs/auto_repair.log
```

## Troubleshooting

### Daemon Won't Start

**Check Python dependencies:**
```bash
pip install requests
```

**Check permissions:**
```bash
# Ensure script is executable
chmod +x agents/auto_repair_daemon.py
```

**Check environment variables:**
```bash
# Ensure AUTHENTIK_DB_PASSWORD is set
echo $AUTHENTIK_DB_PASSWORD
```

### Repairs Are Not Working

**Check cooldown period:**
- Repairs are rate-limited to prevent loops
- Wait 10 minutes between attempts
- Check logs for "Skipping repair (cooldown: Xs remaining)"

**Check SSH connectivity:**
```bash
# Test SSH to remote nodes
ssh -o BatchMode=yes misterobots@192.168.2.103 echo "OK"
```

**Check Docker permissions:**
```bash
# Ensure user can access Docker socket
ssh misterobots@192.168.2.103 docker ps
```

### False Positive Alerts

**Adjust health check timeout:**
- Increase timeout for slow networks
- Edit `check_tcp_port` and `check_http_endpoint` timeout parameters

**Adjust check interval:**
- Increase `AUTO_REPAIR_CHECK_INTERVAL` for less frequent checks
- Reduce noise from transient issues

## Integration

### With Monitoring Dashboard

The auto-repair daemon integrates with `agents/ops_dashboard.py`:

```python
# Dashboard shows repair history
from auto_repair_daemon import AutoRepairDaemon

daemon = AutoRepairDaemon()
recent_repairs = daemon.repair_history[-10:]
```

### With Alerting (Future)

Planned integration with notification services:
- Discord webhooks for critical failures
- Email alerts for consecutive failures
- Slack integration for repair summaries

## Maintenance

### Update the Daemon

```bash
# Pull latest changes
git pull

# Redeploy (Linux)
cd scripts/deploy
bash deploy_auto_repair.sh

# Restart (Windows)
cd agents
.\launch_auto_repair.ps1 -Stop
.\launch_auto_repair.ps1
```

### View Repair History

```bash
# Show repair summary
grep "Repair Summary" logs/auto_repair.log

# Count repairs by service
grep "Repair successful" logs/auto_repair.log | awk '{print $8}' | sort | uniq -c
```

### Clean Old Logs

```bash
# Rotate logs (manual)
mv logs/auto_repair.log logs/auto_repair.log.$(date +%Y%m%d)
touch logs/auto_repair.log
```

## Security

### Credentials

The daemon requires database credentials to perform repairs:
- Store in `.env` file with restricted permissions: `chmod 600 .env`
- Never commit credentials to version control
- Rotate passwords periodically

### SSH Access

The daemon uses SSH to access remote nodes:
- Ensure SSH key authentication is configured
- Use `BatchMode=yes` to prevent interactive prompts
- Restrict SSH user permissions to necessary Docker commands only

## Performance

### Resource Usage

- **CPU**: < 1% average (mostly idle)
- **Memory**: ~50-100 MB
- **Network**: Minimal (health checks only)
- **Disk**: Logs grow ~1-5 MB/day

### Scaling

For large deployments:
- Run daemon on each node separately
- Use distributed health checks
- Implement leader election for coordinated repairs

## Support

For issues or questions:
1. Check logs: `logs/auto_repair.log`
2. Review repair history
3. Check service status manually
4. Consult main Agent Swarm documentation

## License

Part of the Agent Swarm project. See main LICENSE file.
