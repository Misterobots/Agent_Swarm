#!/usr/bin/env python3
"""Quick test: call MemPalace /v1/extract and /v1/palace/layout."""
import json, urllib.request

BASE = "http://localhost:8200"

# 1. Extract a test memory
payload = json.dumps({
    "conversation": "User: What is the capital of France?\nAssistant: The capital of France is Paris. It is known as the City of Light."
}).encode()

req = urllib.request.Request(
    f"{BASE}/v1/extract",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
        print(f"Extracted {len(data)} memories:")
        for m in data:
            print(f"  - [{m.get('memory_type','?')}] {m.get('content','')[:80]}")
            print(f"    wing={m.get('wing')} hall={m.get('hall')} room={m.get('room')}")
except Exception as e:
    print(f"Extract failed: {e}")

# 2. Check palace layout
req2 = urllib.request.Request(f"{BASE}/v1/palace/layout")
try:
    with urllib.request.urlopen(req2, timeout=10) as resp:
        layout = json.loads(resp.read())
        print(f"\nPalace layout: {len(layout.get('wings',[]))} wings, {layout.get('total_memories',0)} total memories")
        for w in layout.get("wings", []):
            print(f"  Wing: {w['name']}")
            for h in w.get("halls", []):
                print(f"    Hall: {h['name']}")
                for r in h.get("rooms", []):
                    print(f"      Room: {r['name']} ({r['drawer_count']} drawers)")
except Exception as e:
    print(f"Layout failed: {e}")
