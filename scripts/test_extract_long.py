#!/usr/bin/env python3
"""Test extraction with a longer, more realistic conversation."""
import json, urllib.request

BASE = "http://localhost:8200"

conversation = (
    "User: I've been working on setting up my home lab with a Dell Turing server "
    "running Ubuntu. I use Docker Compose for orchestration and Traefik as my "
    "reverse proxy with Authentik for SSO.\n"
    "Assistant: That sounds like a solid setup! The Turing is a great workhorse "
    "server. Using Traefik with Authentik gives you a nice balance of ease of "
    "configuration and strong authentication.\n"
    "User: Yeah, I also have three machines - Lovelace as the execution node "
    "running Ollama with GPU, a control plane node, and the Turing as the gateway. "
    "My favorite programming language is Python but I also enjoy Rust for "
    "embedded work.\n"
    "Assistant: Having dedicated nodes for different roles is excellent for "
    "separation of concerns. Python and Rust are a powerful combination - "
    "Python for rapid development and Rust for performance-critical embedded "
    "systems.\n"
    "User: I prefer dark themes in my IDE and I always use VS Code with "
    "GitHub Copilot. My email is justin@shivelymail.com.\n"
    "Assistant: Great tools! VS Code with Copilot is a fantastic productivity "
    "booster. Dark themes are definitely easier on the eyes for long coding "
    "sessions."
)

payload = json.dumps({"conversation": conversation, "owner_id": "justin"}).encode()
req = urllib.request.Request(
    f"{BASE}/v1/extract",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        print(f"Extracted {len(data)} memories:")
        for m in data:
            print(f"  - [{m.get('memory_type','?')}] {m.get('content','')[:100]}")
except Exception as e:
    print(f"Extract failed: {e}")

# Check layout
req2 = urllib.request.Request(f"{BASE}/v1/palace/layout")
with urllib.request.urlopen(req2, timeout=10) as resp:
    layout = json.loads(resp.read())
    print(f"\nPalace: {layout.get('total_memories',0)} total memories, "
          f"{len(layout.get('wings',[]))} wings")
    for w in layout.get("wings", []):
        print(f"  Wing: {w['name']}")
        for h in w.get("halls", []):
            print(f"    Hall: {h['name']}")
            for r in h.get("rooms", []):
                print(f"      Room: {r['name']} ({r['drawer_count']} drawers)")

