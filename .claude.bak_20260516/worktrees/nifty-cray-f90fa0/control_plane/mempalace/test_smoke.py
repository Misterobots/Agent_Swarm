"""Quick smoke test for MemPalace API."""
import urllib.request
import json

BASE = "http://localhost:8200"

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())

# 1. Health
print("1. Health:", get("/health"))

# 2. Store a memory
mem1 = post("/v1/memories", {
    "content": "User prefers cyberpunk aesthetic with neon colors and rain",
    "memory_type": "procedural",
    "domain": "visual",
    "owner_id": "test_user",
})
print(f"2. Stored memory: id={mem1['id']}, type={mem1['memory_type']}")

# 3. Store another
mem2 = post("/v1/memories", {
    "content": "Python code should always use type hints and follow PEP-8",
    "memory_type": "procedural",
    "domain": "coding",
    "owner_id": "test_user",
})
print(f"3. Stored memory: id={mem2['id']}, type={mem2['memory_type']}")

# 4. Semantic search
results = post("/v1/memories/search", {
    "query": "what style does the user like for images?",
    "owner_id": "test_user",
    "limit": 3,
})
print(f"4. Search results ({len(results)} hits):")
for r in results:
    print(f"   [{r['score']:.3f}] {r['content'][:80]}")

# 5. Stats
stats = get("/v1/memories/stats")
print(f"5. Stats: {stats}")

# 6. Extract from conversation
extracted = post("/v1/extract", {
    "conversation": (
        "User: Can you help me set up a Docker container for my Python API?\n"
        "Assistant: Sure! I'll use Python 3.11-slim as the base image with uvicorn.\n"
        "User: I always prefer alpine images, they are smaller.\n"
        "Assistant: Got it, switching to python:3.11-alpine. Also adding a non-root user."
    ),
    "owner_id": "test_user",
})
print(f"6. Extracted {len(extracted)} memories:")
for e in extracted:
    print(f"   [{e['memory_type']}/{e.get('domain', '?')}] {e['content'][:80]}")

# 7. Agent snapshot
snap = post("/v1/snapshots", {
    "agent_id": "architect",
    "owner_id": "test_user",
    "snapshot_data": {"learned_rules": ["prefer alpine images", "always use type hints"]},
})
print(f"7. Snapshot saved: agent={snap['agent_id']} v{snap['version']}")

# 8. Get snapshot
snap2 = get("/v1/snapshots/architect?owner_id=test_user")
print(f"8. Snapshot loaded: v{snap2['version']}, data={snap2['snapshot_data']}")

# 9. Team memory
team = post("/v1/team/coord-test123", {
    "key": "research_summary",
    "value": "Docker containers should use non-root users and minimal base images.",
    "author_agent": "researcher",
})
print(f"9. Team memory stored: {team['key']}")

# 10. Get team memories
team_mems = get("/v1/team/coord-test123")
print(f"10. Team memories: {len(team_mems)} items")

print("\n✅ All MemPalace smoke tests passed!")
