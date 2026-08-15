# Persistent launcher for the auto-repair daemon.
# Invoked by the AutoRepairDaemon Startup-folder entry at logon. Sets the queue Redis
# (redis-turing @ 192.168.2.103 — where maintenance_router pushes the
# maintenance:system_alert queue; the daemon's default 'redis-turing' hostname
# does not resolve from Lovelace) then hands off to the existing launcher, which
# guards against double-starts via the PID file.
$env:REDIS_HOST = '192.168.2.103'
$env:REDIS_PORT = '6379'
$env:AUTO_REPAIR_REDIS_SUBSCRIBER = 'true'
& (Join-Path $PSScriptRoot 'launch_auto_repair.ps1')
