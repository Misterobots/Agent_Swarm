
import json
import redis
import os
import sys

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis_queue")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    r.ping()
    print("Connected!")
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

# Task Data
import sys
prompt = sys.argv[1] if len(sys.argv) > 1 else "generate an image of a cybernetic cat"

# Correct Schema for Event.from_json()
task_data = {
    "type": "user_task", # Match EventType.USER_TASK.value
    "payload": {
        "task": prompt,  # Dispatcher expects 'task' in payload
        "intent": "IMAGE", # Router now checks this
        "width": 1024,
        "height": 1024
    },
    "source": "manual_test"
}

# Also support legacy schema if dispatcher expects flat
# task_data = {"task": prompt} 

json_str = json.dumps(task_data)
print(f"Injecting into queue:image: {json_str}")

# Push to queue:image
r.rpush("queue:image", json_str)
print("Done!")
