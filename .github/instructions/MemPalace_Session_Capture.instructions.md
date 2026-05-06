---
description: MemPalace memory capture and recall for VS Code Copilot Chat sessions. Governs when and how the AI agent reads from and writes to the persistent memory store.
applyTo: "**"
---

## MemPalace Memory Integration

You have access to the MemPalace semantic memory service via MCP tools. Use them to build persistent knowledge that survives across Copilot Chat sessions.

### Available tools
| Tool | Purpose |
|------|---------|
| `search_memories_mcp` | Semantic search — recall relevant prior context |
| `store_memory_mcp` | Store a single discrete fact immediately |
| `extract_from_conversation_mcp` | Bulk-extract multiple facts from a session summary |
| `get_memory_stats_mcp` | Check how many memories are stored |

---

### At session START
When the user describes a task or asks a question:
1. Call `search_memories_mcp` with the topic/keywords to surface relevant prior context
2. If results with score > 0.5 exist, incorporate them silently into your reasoning (no need to announce "I found memories")
3. If scores are low, proceed without recall noise

### During a session
Store a memory **immediately** when any of the following occur:
- A bug is identified and fixed (what it was, what fixed it)
- A design decision is made (what was chosen and why)
- A working configuration or command is confirmed (exact values matter)
- A pattern or anti-pattern is discovered in the codebase
- A deployment procedure is validated end-to-end

Use `store_memory_mcp` with the right `domain`:
| Domain | Use for |
|--------|---------|
| `infrastructure` | Nodes, Docker, networking, ports, IPs |
| `agents` | church.py, main.py, agent behavior, prompts |
| `ui` | Hive UI, React, SSE frontend pipeline |
| `mempalace` | Memory system itself |
| `comfyui` | Image generation, workflows |
| `general` | Cross-cutting concerns |

### At session END
After completing the user's main request, call `extract_from_conversation_mcp` with a concise (~300-500 word) summary covering:
- What problem was solved
- Key files changed and why
- Any gotchas, bugs discovered, or non-obvious behavior
- Confirmed working state

This lets the LLM extraction pipeline atomize the summary into individual searchable facts automatically.

---

### What NOT to store
- Obvious facts already in code (don't store "FastAPI is a Python framework")
- Transient debug output
- Information that will be stale in one session (e.g. "currently testing X")

### owner_id convention
Use `owner_id="justin"` when storing facts that are user/project-specific decisions.
Leave empty for general codebase facts.
