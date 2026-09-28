"""
GPU Pool Manager - Distributes image generation across multiple GPUs
"""
import os
import asyncio
import time
from threading import Lock
from logger_setup import setup_logger

logger = setup_logger("GPUPoolManager")

class GPUPool:
    """Manages multiple ComfyUI instances across different GPUs"""
    
    def __init__(self):
        self.lock = Lock()
        self.instances = []
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Discover available ComfyUI instances from environment"""
        # Primary instance (default)
        primary_host = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
        self.instances.append({
            "host": primary_host,
            "gpu_id": 0,
            "name": "GPU0-Primary",
            "in_use": False,
            "last_used": 0,
            "total_requests": 0
        })
        
        # Secondary instance (if configured)
        secondary_host = os.getenv("COMFYUI_HOST_GPU1", None)
        if secondary_host:
            self.instances.append({
                "host": secondary_host,
                "gpu_id": 1,
                "name": "GPU1-Secondary",
                "in_use": False,
                "last_used": 0,
                "total_requests": 0
            })
            logger.info(f"Multi-GPU mode enabled: {len(self.instances)} instances detected")
        else:
            logger.info("Single-GPU mode: Set COMFYUI_HOST_GPU1 for multi-GPU support")
    
    def get_available_instance(self, prefer_gpu=None):
        """
        Get the least busy ComfyUI instance
        
        Args:
            prefer_gpu: Preferred GPU ID (0 or 1), or None for auto-select
        
        Returns:
            dict: Instance info, or None if all busy
        """
        with self.lock:
            # If specific GPU requested and available, use it
            if prefer_gpu is not None:
                for instance in self.instances:
                    if instance["gpu_id"] == prefer_gpu and not instance["in_use"]:
                        instance["in_use"] = True
                        instance["last_used"] = time.time()
                        instance["total_requests"] += 1
                        logger.info(f"Assigned request to {instance['name']} (requested)")
                        return instance
            
            # Find least recently used available instance
            available = [i for i in self.instances if not i["in_use"]]
            if not available:
                logger.warning("All GPU instances busy - request will queue")
                return None
            
            # Select by least recent use
            selected = min(available, key=lambda x: x["last_used"])
            selected["in_use"] = True
            selected["last_used"] = time.time()
            selected["total_requests"] += 1
            
            logger.info(
                f"Assigned request to {selected['name']} "
                f"(total: {selected['total_requests']} requests)"
            )
            return selected
    
    def release_instance(self, instance):
        """Mark instance as available"""
        with self.lock:
            for i in self.instances:
                if i["host"] == instance["host"]:
                    i["in_use"] = False
                    logger.debug(f"Released {i['name']}")
                    break
    
    def get_stats(self):
        """Get current pool statistics"""
        with self.lock:
            stats = {
                "total_instances": len(self.instances),
                "available": sum(1 for i in self.instances if not i["in_use"]),
                "busy": sum(1 for i in self.instances if i["in_use"]),
                "instances": [
                    {
                        "name": i["name"],
                        "gpu_id": i["gpu_id"],
                        "status": "busy" if i["in_use"] else "available",
                        "total_requests": i["total_requests"]
                    }
                    for i in self.instances
                ]
            }
            return stats


# Global pool instance
_gpu_pool = None

def get_gpu_pool():
    """Get or create the global GPU pool"""
    global _gpu_pool
    if _gpu_pool is None:
        _gpu_pool = GPUPool()
    return _gpu_pool
