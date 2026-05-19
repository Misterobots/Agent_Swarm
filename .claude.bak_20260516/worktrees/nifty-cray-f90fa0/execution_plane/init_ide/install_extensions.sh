#!/bin/bash
echo "--- Installing VS Code Extensions ---"

# Install core extension used across IDE containers.
code-server --install-extension Continue.continue --force || true

# Coding workspace gets optional Claude-adjacent extension attempts.
if [ "${SWARM_API_KEY:-}" = "sk-coder-identity" ]; then
	code-server --install-extension Anthropic.claude-code --force || true
fi

echo "--- Extension Installation Complete ---"

