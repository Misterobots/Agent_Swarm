import logging
import time
from typing import Dict, Optional, List
import pynvml
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger("GPUAllocator")

class GPUStats(BaseModel):
    index: int
    name: str
    total_memory: int
    free_memory: int
    utilization: int

class GPUAllocator:
    """
    Manages dynamic allocation of GPU resources based on real-time VRAM usage
    and task-specific weighted preferences.
    """
    def __init__(self):
        self.initialized = False
        try:
            pynvml.nvmlInit()
            self.device_count = pynvml.nvmlDeviceGetCount()
            self.initialized = True
            logger.info(f"GPUAllocator initialized. Detected {self.device_count} devices.")
        except pynvml.NVMLError as e:
            logger.error(f"Failed to initialize NVML: {e}")
            self.device_count = 0

    def get_gpu_stats(self) -> List[GPUStats]:
        """Returns real-time stats for all available GPUs."""
        if not self.initialized:
            return []
        
        stats = []
        for i in range(self.device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                stats.append(GPUStats(
                    index=i,
                    name=str(name), # Ensure string
                    total_memory=mem_info.total,
                    free_memory=mem_info.free,
                    utilization=util.gpu
                ))
            except pynvml.NVMLError as e:
                logger.warning(f"Failed to get stats for GPU {i}: {e}")
        return stats

    def allocate(self, task_type: str, min_vram_gb: int = 4, preferred_gpu_index: Optional[int] = None) -> int:
        """
        Determines the best GPU for a task.
        
        Args:
            task_type: Label for the task (e.g., "IMAGE_GEN", "LLM")
            min_vram_gb: Minimum required VRAM in GB.
            preferred_gpu_index: Index of the preferred GPU (e.g., 0 for 5060 Ti).
            
        Returns:
            int: The index of the allocated GPU (0, 1, etc.) or -1 if none suitable.
        """
        if not self.initialized:
            logger.warning("NVML not initialized. Defaulting to GPU 0.")
            return 0

        stats = self.get_gpu_stats()
        if not stats:
            return 0

        best_gpu = -1
        best_score = -float('inf')
        
        min_vram_bytes = min_vram_gb * 1024 * 1024 * 1024

        logger.info(f"Allocating for {task_type} (Min VRAM: {min_vram_gb}GB, Pref: {preferred_gpu_index})")

        for gpu in stats:
            # 1. Hard Constraint: Must have enough VRAM
            if gpu.free_memory < min_vram_bytes:
                logger.info(f"GPU {gpu.index} ({gpu.name}) skipped. Not enough VRAM ({gpu.free_memory/1024**3:.2f}GB < {min_vram_gb}GB)")
                continue

            # 2. Calculate Score
            # Base score is free memory (favor empty GPUs)
            score = (gpu.free_memory / gpu.total_memory) * 100

            # Penalize high utilization
            score -= (gpu.utilization * 0.5)

            # Apply Preference Bonus
            if preferred_gpu_index is not None and gpu.index == preferred_gpu_index:
                score += 50 # Strong bias towards preferred GPU
                logger.info(f"GPU {gpu.index} gets preference bonus.")

            logger.info(f"GPU {gpu.index} ({gpu.name}) Score: {score:.2f}")

            if score > best_score:
                best_score = score
                best_gpu = gpu.index

        if best_gpu == -1:
            logger.warning("No suitable GPU found (VRAM constraints). returning GPU with most free memory as fallback.")
            # Fallback: Just get the one with max free memory
            max_free = -1
            for gpu in stats:
                if gpu.free_memory > max_free:
                    max_free = gpu.free_memory
                    best_gpu = gpu.index
            
        logger.info(f"Selected GPU {best_gpu} for {task_type}")
        return best_gpu

    def cleanup(self):
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
