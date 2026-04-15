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

## Driver/CUDA Version Mismatch

**Symptom**: CUDA errors or library version conflicts.

**Check**:

```bash
nvidia-smi  # Shows driver and max CUDA version
nvcc --version  # Shows installed CUDA toolkit version
```

Ensure the Docker images use a compatible CUDA version.
