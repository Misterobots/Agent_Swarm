---
title: "Troubleshooting: Network"
---

# Network Troubleshooting

## Traefik Not Routing

**Symptom**: Requests to `{{ turing_ip }}` return 404 or timeout.

**Diagnose**:

```bash
# Check Traefik dashboard
curl http://{{ turing_ip }}:8080/api/overview

# Check active routers
curl http://{{ turing_ip }}:8080/api/http/routers | python -m json.tool
```

**Fix**:

1. Verify Docker labels on the target service
2. Check that the service is on the correct Docker network
3. Restart Traefik: `docker compose restart traefik`

---

## Service Unreachable Between Nodes

**Symptom**: One node can't reach a service on another node.

**Diagnose**:

```bash
# Basic connectivity
ping {{ lovelace_ip }}

# Port check
curl -v http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags
```

**Fix**:

1. Check firewall rules: `sudo ufw status` or `sudo iptables -L`
2. Verify both nodes are on the same subnet
3. Check Docker network configuration

---

## DNS Resolution Failures

**Symptom**: Services can't resolve hostnames.

**Fix**:

- Use IP addresses instead of hostnames in `network.env`
- Check Docker's DNS: `docker exec <container> cat /etc/resolv.conf`
- Add static entries if needed: `extra_hosts` in docker-compose

---

## Tailscale VPN Issues

**Symptom**: Remote access via Tailscale doesn't work.

**Fix**:

1. Check Tailscale status: `tailscale status`
2. Verify the node is online in Tailscale admin
3. Check that services listen on `0.0.0.0` (not `127.0.0.1`)
4. Verify Tailscale IP routing

---

## Port Conflicts

**Symptom**: Container fails to start with "port already in use".

**Diagnose**:

```bash
sudo ss -tlnp | grep <port>
```

**Fix**:

- Stop the conflicting process
- Or remap the port in docker-compose.yml
- See [Port Map](../admin-guide/port-map.md) for all used ports


