
import logging
import threading
import json
import time
import os
from typing import Callable, Dict, List
from enum import Enum
from logger_setup import setup_logger

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis_queue")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# --- SELF-HEALING: Mock Redis for Fallback ---
class MockRedis:
    def __init__(self):
        self.queues = {}
        self.lock = threading.Lock()
        
    def rpush(self, queue, data):
        with self.lock:
            if queue not in self.queues: self.queues[queue] = []
            self.queues[queue].append(data)
            
    def blpop(self, queue, timeout=0):
        # Simulate blocking pop with polling
        start = time.time()
        while True:
            with self.lock:
                if queue in self.queues and self.queues[queue]:
                    return (queue, self.queues[queue].pop(0))
            if timeout and (time.time() - start > timeout):
                return None
            time.sleep(0.1)
            
    def ping(self):
        return True

try:
    import redis
    REDIS_LIB_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_LIB_AVAILABLE = False

# Logging Setup
logger = setup_logger("Dispatcher")

class EventType(Enum):
    USER_TASK = "user_task"
    FILE_CHANGED = "file_changed"
    SYSTEM_ALERT = "system_alert"

class Event:
    def __init__(self, type: EventType, payload: dict, source: str = "system"):
        self.type = type
        self.payload = payload
        self.source = source

    def to_json(self):
        return json.dumps({
            "type": self.type.value,
            "payload": self.payload,
            "source": self.source
        })

    @classmethod
    def from_json(cls, json_str):
        # Handle bytes or string
        if isinstance(json_str, bytes):
            json_str = json_str.decode('utf-8')
        data = json.loads(json_str)
        return cls(EventType(data["type"]), data["payload"], data["source"])

def detect_intent(input_text: str) -> str:
    """
    Simple keyword classifier for routing.
    Duplicated minimal logic to avoid circular dependency with router.py
    """
    text = input_text.lower()
    if "3d" in text or "forge" in text or ("model" in text and "generate" in text):
        return "3D"
    if "image" in text or "picture" in text or "draw" in text or "photo" in text:
        return "IMAGE"
    return "DEFAULT"

class Dispatcher:
    """
    Redis-backed Event Bus with Throttling and Persistence.
    """
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        
        # Connect to Redis (Self-Healing Logic)
        self.redis_available = False
        
        if REDIS_LIB_AVAILABLE:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
                self.redis.ping()
                logger.info(f"--- [Dispatcher] Connected to Redis at {REDIS_HOST}:{REDIS_PORT} ---")
                self.redis_available = True
            except Exception as e:
                logger.warning(f"--- [Dispatcher] Redis Connection Failed: {e}. Switching to In-Memory Fallback. ---")
                self.redis = MockRedis()
                self.redis_available = True # We are "available" via mock
        else:
            logger.warning("--- [Dispatcher] 'redis' module missing. Switching to In-Memory Fallback. ---")
            self.redis = MockRedis()
            self.redis_available = True

        # Queue Configuration: (Queue Name, Concurrency Limit)
        self.queues = {
            "queue:3d": 1,      # MAX 1 3D Job (Protect GPU)
            "queue:image": 2,   # MAX 2 Image Jobs
            "queue:default": 5  # Chat/Code (Lightweight)
        }
        
        # Start Consumers
        if self.redis_available:
            self.start_consumers()

    def register(self, event_type: EventType, handler: Callable):
        """Register a function to handle specific events."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}: {handler.__name__}")

    def emit(self, event: Event):
        """Push event to Redis Queue."""
        if not self.redis_available:
            logger.error("Cannot emit event: Redis unavailable.")
            return

        if event.type == EventType.USER_TASK:
            # Smart Routing
            user_input = event.payload.get("task", "")
            intent = detect_intent(user_input)
            
            queue_name = "queue:default"
            if intent == "3D":
                queue_name = "queue:3d"
            elif intent == "IMAGE":
                queue_name = "queue:image"
            
            logger.info(f"--- [Dispatcher] Enqueuing Task to {queue_name} (Intent: {intent}) ---")
            self.redis.rpush(queue_name, event.to_json())
        else:
            # System events go to default
            self.redis.rpush("queue:default", event.to_json())

    def start_consumers(self):
        """Starts background threads for each queue."""
        for queue_name, concurrency in self.queues.items():
            for i in range(concurrency):
                t = threading.Thread(target=self._consumer_loop, args=(queue_name,), daemon=True)
                t.start()
            logger.info(f"--- [Dispatcher] Started {concurrency} consumers for {queue_name} ---")

    def _consumer_loop(self, queue_name):
        """Infinite loop processing tasks from a specific queue."""
        while True:
            try:
                # Blocking Pop (waits until item available)
                # Returns (queue_name, data)
                item = self.redis.blpop(queue_name, timeout=5)
                
                if item:
                    _, data = item
                    event = Event.from_json(data.decode('utf-8'))
                    self._dispatch_local(event)
                    
            except redis.ConnectionError:
                logger.error("Redis connection lost. Retrying...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in consumer loop {queue_name}: {e}")
                time.sleep(1)

    def _dispatch_local(self, event: Event):
        """Executes the handler locally (in the worker thread)."""
        if event.type in self._handlers:
            for handler in self._handlers[event.type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error executing handler: {e}")
        else:
            logger.warning(f"No handlers for {event.type}")

# Global Singleton
dispatcher = Dispatcher()
