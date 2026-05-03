# Multi-GPU Load Balancing Setup

**Date**: May 3, 2026  
**Status**: ✅ DEPLOYED AND OPERATIONAL

## Overview
Implemented automatic GPU load balancing for image generation across 2× RTX 5060 Ti GPUs (16GB each) on Lovelace node. The system intelligently distributes image generation requests across both GPUs for 2× throughput.

## Architecture

### Hardware Configuration
- **Lovelace** (192.168.2.101): 2× RTX 5060 Ti (16GB VRAM each)
  - GPU 0: ComfyUI instance on port 8189
  - GPU 1: ComfyUI instance on port 8188 (primary)
- **Turing** (192.168.2.103): Agent runtime orchestration

### Software Stack
- **ComfyUI**: Docker containers with PyTorch 2.11.0+cu130 (Blackwell sm_120 support)
- **GPU Pool Manager**: Thread-safe load balancer in `agents/specialized/gpu_pool_manager.py`
- **Image Generator**: Integrated in `agents/specialized/image_gen.py`

## Components

### 1. GPU Pool Manager (`agents/specialized/gpu_pool_manager.py`)
Thread-safe GPU instance management:
- **Auto-discovery**: Detects GPU instances from `COMFYUI_HOST` and `COMFYUI_HOST_GPU1` env vars
- **Load balancing**: Least-recently-used (LRU) selection algorithm
- **Resource tracking**: Monitors availability, request count, last-used timestamp per GPU
- **Statistics**: `get_stats()` provides pool metrics for monitoring

Key Methods:
```python
gpu_pool = get_gpu_pool()                          # Get singleton pool
instance = gpu_pool.get_available_instance()       # Acquire GPU
gpu_pool.release_instance(instance)                # Release after generation
stats = gpu_pool.get_stats()                       # Get pool statistics
```

### 2. Image Generation Integration (`agents/specialized/image_gen.py`)
Modified `queue_prompt()` function:
- Acquires GPU instance before generation
- Uses instance-specific host URL instead of static `COMFYUI_HOST`
- Releases GPU on completion or error (all paths)
- Falls back to primary host if all GPUs busy

### 3. Docker Configuration

#### Lovelace (`execution_plane/docker-compose.yml`)
```yaml
services:
  comfyui:
    container_name: comfyui_gpu
    ports: ["8188:8188"]
    environment:
      - NVIDIA_VISIBLE_DEVICES=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]

  comfyui-gpu1:
    container_name: comfyui_gpu1
    ports: ["8189:8188"]
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
```

#### Turing (`turing_gateway/docker-compose.yml`)
```yaml
agent-runtime:
  environment:
    - COMFYUI_HOST=http://192.168.2.101:8188
    - COMFYUI_HOST_GPU1=http://192.168.2.101:8189
```

## Deployment

### Initial Setup (Completed)
```powershell
# 1. Update docker-compose.yml on Lovelace
# Added comfyui-gpu1 service with GPU 0 binding

# 2. Start second ComfyUI instance
cd C:\Users\panca\Documents\Github\Agent_Swarm\execution_plane
docker compose up -d comfyui-gpu1

# 3. Deploy GPU pool manager to Turing
scp agents/specialized/gpu_pool_manager.py misterobots@192.168.2.103:~/Home_AI_Lab/agents/specialized/
scp agents/specialized/image_gen.py misterobots@192.168.2.103:~/Home_AI_Lab/agents/specialized/

# 4. Configure environment variables on Turing
ssh misterobots@192.168.2.103
# Edit ~/Home_AI_Lab/turing_gateway/docker-compose.yml
# Add COMFYUI_HOST and COMFYUI_HOST_GPU1 under agent-runtime environment

# 5. Restart agent_runtime
cd ~/Home_AI_Lab/turing_gateway
docker compose restart agent-runtime
```

### Verification
```bash
# Check both ComfyUI instances
docker ps --filter "name=comfyui"

# Test connectivity from Turing
curl http://192.168.2.101:8188/system_stats  # GPU1
curl http://192.168.2.101:8189/system_stats  # GPU0

# Monitor GPU utilization
nvidia-smi --loop=1
```

## Usage

### Automatic Load Balancing
The system automatically distributes requests:
1. User requests image generation via chat
2. Art Director processes request → church.py IMAGE intent
3. church.py calls `image_gen.queue_prompt()`
4. GPU pool manager selects available GPU (LRU)
5. Image generates on assigned GPU
6. GPU released back to pool after completion

### Monitoring
Check GPU pool statistics in agent logs:
```bash
docker logs agent_runtime | grep -i "gpu\|pool"
```

Expected log messages:
- `Using GPU0-Secondary at http://192.168.2.101:8189`
- `Using GPU1-Primary at http://192.168.2.101:8188`
- `All GPUs busy - using primary instance (may queue)`

### Testing Parallel Generation
Request multiple images simultaneously in chat to observe parallel processing:
```
User: "generate a cyberpunk city"
User: "generate a forest landscape"
```

Check `nvidia-smi` during generation to verify both GPUs active.

## Performance Expectations

### Throughput
- **Single GPU**: ~1 image per 20-40 seconds (FLUX model)
- **Dual GPU**: ~2 images per 20-40 seconds (2× throughput)
- **Batching**: 4+ simultaneous requests queue and process in parallel

### VRAM Usage
- **SD XL Turbo**: ~8GB VRAM per GPU
- **FLUX Schnell**: ~12-14GB VRAM per GPU
- **FLUX Dev**: ~14-16GB VRAM per GPU
- Each RTX 5060 Ti has 16GB, sufficient for FLUX models

## Troubleshooting

### GPU Pool Not Initializing
**Symptom**: No GPU messages in logs  
**Cause**: Lazy initialization - pool creates on first image request  
**Solution**: Normal behavior, pool initializes when needed

### All GPUs Busy
**Symptom**: "All GPUs busy - using primary instance"  
**Cause**: Both GPUs processing images simultaneously  
**Solution**: Request queues on primary, normal operation

### Model Not Found
**Symptom**: "Error: No checkpoint matches profile"  
**Cause**: Model not downloaded in ComfyUI  
**Solution**: Download FLUX Schnell or Dev to `C:\Users\panca\Documents\ComfyUI_app\models\checkpoints\`

### GPU Not Responding
**Symptom**: Timeout errors from specific GPU  
**Check**: `docker logs comfyui_gpu` or `docker logs comfyui_gpu1`  
**Solution**: Restart specific container: `docker restart comfyui_gpu1`

## Future Enhancements

### Potential Improvements
1. **Dynamic quality scaling**: Route high-quality to less-busy GPU
2. **Model-aware routing**: Assign based on model VRAM requirements
3. **Priority queuing**: VIP users get faster GPU assignment
4. **Cross-node GPU pool**: Include Turing RTX 3070 Ti for 3-GPU pool
5. **Auto-scaling**: Spin up/down GPU instances based on load

### Adding Third GPU (Turing RTX 3070 Ti)
```yaml
# On Turing, add to docker-compose.yml:
comfyui-turing:
  image: comfyui:cuda
  ports: ["8190:8188"]
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]

# On Turing agent-runtime environment:
- COMFYUI_HOST_GPU2=http://localhost:8190

# GPU pool manager auto-discovers all COMFYUI_HOST_GPU* variables
```

## Status

### ✅ Completed
- [x] Created GPU pool manager with thread-safe instance management
- [x] Integrated pool into image_gen.py queue_prompt() function
- [x] Set up second ComfyUI instance on Lovelace GPU 0
- [x] Configured environment variables on Turing agent_runtime
- [x] Verified connectivity between Turing and both GPU instances
- [x] Deployed all code to production (Turing agent_runtime)

### 🔄 In Progress
- [ ] Download FLUX models for better image quality
- [ ] Test parallel generation with real user requests
- [ ] Monitor GPU utilization during peak load

### 📋 Pending
- [ ] Add GPU pool statistics endpoint to API
- [ ] Create monitoring dashboard for GPU utilization
- [ ] Implement priority queue for quality vs speed routing
- [ ] Extend to 3-GPU pool (include Turing RTX 3070 Ti)

## References
- GPU Pool Manager: `agents/specialized/gpu_pool_manager.py`
- Image Generator: `agents/specialized/image_gen.py`
- Lovelace Config: `execution_plane/docker-compose.yml`
- Turing Config: `turing_gateway/docker-compose.yml`
- Memory Note: `/memories/containerization_preference.md`
