---
title: "Service: MemPalace"
---

# MemPalace

Semantic memory service for vector-based knowledge retrieval.

## Deployment

| Property | Value |
|----------|-------|
| **Node** | Control Plane ({{ hopper_ip }}) |
| **Port** | 8200 |
| **URL** | `http://{{ hopper_ip }}:8200` |
| **Backend** | PostgreSQL with pgvector |
| **Compose** | `control_plane/docker-compose.yml` |

## Purpose

MemPalace complements the rule-based Skills Memory with semantic (vector) search. It stores knowledge embeddings and retrieves relevant information based on meaning, not just keywords.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/store` | POST | Store a knowledge entry |
| `/search` | POST | Semantic similarity search |
| `/delete` | DELETE | Remove an entry |

## Client

```python
from agents.mempalace_client import MemPalaceClient

client = MemPalaceClient(url="http://{{ hopper_ip }}:8200")

# Store knowledge
client.store(text="Python best practices for error handling", metadata={"domain": "coding"})

# Search
results = client.search(query="how to handle exceptions", top_k=5)
```

## Related

- [Architecture: Memory System](../../architecture/memory-system.md)
- [Module: Memory](../memory.md)


