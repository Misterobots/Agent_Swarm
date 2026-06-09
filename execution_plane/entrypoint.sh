#!/bin/bash
# Agent Runtime startup entrypoint.
# Runs an incremental graphify update (AST-only, no LLM cost) before starting uvicorn.
# Fails gracefully: if graph.json doesn't exist yet or the update fails, uvicorn still starts.

GRAPH_DIR="${GRAPHIFY_GRAPH_DIR:-/workspace/agents/graphify-out}"
AGENTS_DIR="/workspace/agents"

if [ -f "$GRAPH_DIR/graph.json" ]; then
    echo "[startup] graphify-out found at $GRAPH_DIR — running incremental update (AST-only)..."
    graphify update "$AGENTS_DIR" 2>&1 | tail -10 || \
        echo "[startup] graphify update failed — serving cached graph as-is"
else
    echo "[startup] No graph.json at $GRAPH_DIR — skipping graphify update (graph not built yet)"
fi

exec "$@"
