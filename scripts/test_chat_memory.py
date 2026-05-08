#!/usr/bin/env python3
"""Test: send a chat to agent_runtime with memory_enabled=true, check if extraction happens."""
import json, urllib.request, time

AGENT_URL = "http://localhost:8008"
MEMPALACE_URL = "http://192.168.2.102:8200"

# 1. Get current memory count
req = urllib.request.Request(f"{MEMPALACE_URL}/v1/palace/layout")
with urllib.request.urlopen(req, timeout=10) as resp:
    before = json.loads(resp.read())
    before_count = before.get("total_memories", 0)
print(f"Before: {before_count} memories")

# 2. Send a chat with memory_enabled
payload = json.dumps({
    "model": "Home-AI-Swarm",
    "messages": [
        {"role": "user", "content": "My favorite programming language is Rust and I work on embedded systems."}
    ],
    "stream": False,
    "memory_enabled": True,
    "owner_id": "test-user"
}).encode()

req2 = urllib.request.Request(
    f"{AGENT_URL}/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
print("Sending chat request...")
try:
    with urllib.request.urlopen(req2, timeout=120) as resp:
        chat_resp = json.loads(resp.read())
        content = chat_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Chat response: {content[:150]}...")
except Exception as e:
    print(f"Chat failed: {e}")
    import sys; sys.exit(1)

# 3. Wait for background extraction
print("Waiting 15s for background extraction...")
time.sleep(15)

# 4. Check memory count again
req3 = urllib.request.Request(f"{MEMPALACE_URL}/v1/palace/layout")
with urllib.request.urlopen(req3, timeout=10) as resp:
    after = json.loads(resp.read())
    after_count = after.get("total_memories", 0)
print(f"After: {after_count} memories (delta: {after_count - before_count})")
if after_count > before_count:
    print("SUCCESS: Memories were extracted and stored!")
else:
    print("WARNING: No new memories detected. Check agent_runtime logs.")
