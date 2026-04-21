---
title: "Troubleshooting: Docker"
---

# Docker Troubleshooting

## Container Won't Start

**Symptom**: Container exits immediately after starting.

**Diagnose**:

```bash
docker logs <container-name> --tail 50
```

{% raw %}
```bash
docker inspect <container-name> --format='{{.State.ExitCode}}'
```
{% endraw %}

**Common causes**:

- Missing environment variables
- Port already in use
- Volume mount permission issues
- Image not built

---

## Disk Space Full

**Symptom**: Containers fail to start or operations fail with I/O errors.

**Diagnose**:

```bash
df -h
docker system df
```

**Fix**:

```bash
# Remove unused images, containers, volumes
docker system prune -a --volumes

# Remove old build caches
docker builder prune
```

!!! warning
    `docker system prune --volumes` removes unused volumes. Make sure your data is backed up first.

---

## Network Connectivity Between Containers

**Symptom**: One container can't reach another.

**Diagnose**:

```bash
# Check networks
docker network ls
docker network inspect <network-name>

# Test from inside a container
docker exec <container> ping <other-container>
```

**Fix**:

- Ensure both containers are on the same Docker network
- Check Docker Compose `networks:` configuration
- Use service names (not container names) for inter-container DNS

---

## Permission Denied on Volumes

**Symptom**: Container logs show permission errors on mounted volumes.

**Fix**:

```bash
# Fix ownership
sudo chown -R 1000:1000 /path/to/volume

# Or use user mapping in docker-compose
user: "1000:1000"
```

---

## Docker Compose Version Issues

**Symptom**: `docker compose` commands fail with syntax errors.

**Fix**:

- Use `docker compose` (v2, built-in) not `docker-compose` (v1, standalone)
- Verify version: `docker compose version`
- Update Docker Engine for the latest Compose


