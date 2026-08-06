---
title: "Troubleshooting: GPU"
---

# GPU Troubleshooting

## GPU Not Detected

**Symptom**: `nvidia-smi` fails or shows no GPU.

**Fix**:

1. Install/update NVIDIA driver:
   ```bash
   sudo apt install nvidia-driver-550
   sudo reboot
   ```
2. Verify: `nvidia-smi`

---

## GPU Not Available in Docker

**Symptom**: `nvidia-smi` works on host but not in containers.

**Fix**:

```bash
# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Test: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`

---

## Thermal Throttling

**Symptom**: Performance degrades after sustained workloads.

**Diagnose**:

```bash
nvidia-smi -q -d TEMPERATURE
```

**Fix**:

- Improve case airflow
- Set fan curve to aggressive
- Add thermal pads/paste if needed
- Reduce sustained workload intensity

---

## Multi-GPU Selection

**Symptom**: Wrong GPU is being used.

**Fix**:

Set `CUDA_VISIBLE_DEVICES` in docker-compose:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0  # Or 1, 2, etc.
```

---

## VRAM OOM / Container Killed (Training vs. Inference)

**Symptom**: A container is OOM-killed when training and inference compete for VRAM.

**Diagnose**:

```bash
nvidia-smi
docker stats --no-stream
```

Training requires roughly 12.5GB. Before starting a training run, verify ComfyUI and Ollama have released VRAM:

```bash
# Force-unload all Ollama models
curl -X DELETE http://{{ lovelace_ip }}:{{ ollama_port }}/api/delete  # or restart ollama

# Stop ComfyUI
docker compose stop comfyui
```

A Redis-backed GPU mutex should normally prevent training and inference from running simultaneously. If Redis is unavailable, the mutex **fails open** (both can run) — see [GPU Mutex (Redis) Not Working](#gpu-mutex-redis-not-working) below. To force a release:

```bash
docker compose stop training-runtime comfyui
docker compose restart ollama
```

---

## GPU Mutex (Redis) Not Working

**Symptom**: Training and inference run simultaneously even though the mutex should serialize them.

**Cause**: The mutex fails open when it can't reach Redis.

**Diagnose**:

```bash
redis-cli -h {{ hopper_ip }} -p 6379 -a <REDIS_PASSWORD> PING
```

**Fix**: If the Redis port isn't exposed, add it to the data-plane `docker-compose.yml`:

```yaml
ports:
  - "6379:6379"
```

Then `docker compose up -d redis`. Note the compose file on the data-plane node may be root-owned — edits require `sudo`.

---

## nvidia-smi Not Available (WSL2)

**Symptom**: `nvidia-smi` fails inside WSL2 or containers, even though the Windows host has a working GPU.

**Fix**: Verify all three of the following:

1. NVIDIA driver installed on the Windows host (≥535.x for CUDA 12.x)
2. WSL2 CUDA support enabled (`/usr/lib/wsl/lib/` must exist inside WSL2)
3. Docker Desktop has GPU support enabled

Test:

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## Driver/CUDA Version Mismatch

**Symptom**: CUDA errors or library version conflicts.

**Check**:

```bash
nvidia-smi  # Shows driver and max CUDA version
nvcc --version  # Shows installed CUDA toolkit version
```

Ensure the Docker images use a compatible CUDA version.


