from __future__ import annotations

import os
from typing import Any, Dict, List

from logger_setup import setup_logger
from mcp.schema import MCPToolDescriptor, MCPSkillDescriptor, MCPClientConfig
from mcp.tool_hooks import ToolHookRegistry

logger = setup_logger("MCPBridge")


class MCPBridgeServer:
    """Lightweight JSON-RPC MCP bridge.

    Non-breaking by design: tools are read-only metadata unless explicitly
    enabled via env toggles in future phases.
    """

    def __init__(self):
        self.enabled = os.getenv("MCP_BRIDGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        self.server_name = os.getenv("MCP_SERVER_NAME", "home-ai-lab")
        self.base_url = os.getenv("MCP_BASE_URL", "http://localhost:8000")
        self.tool_hooks = ToolHookRegistry()

        self._tools: list[MCPToolDescriptor] = [
            MCPToolDescriptor(
                name="hive.fs.read",
                description="Read a file from workspace-scoped path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            ),
            MCPToolDescriptor(
                name="hive.fs.write",
                description="Write file content under workspace path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            ),
            MCPToolDescriptor(
                name="hive.fs.list",
                description="List directory entries in workspace path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                },
            ),
            MCPToolDescriptor(
                name="hive.terminal.run",
                description="Run a shell command through the sandbox terminal tool.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                    },
                    "required": ["command"],
                },
            ),
            MCPToolDescriptor(
                name="hive.browser.fetch",
                description="Fetch a web page and return its text content.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
            ),
            MCPToolDescriptor(
                name="hive.browser.search",
                description="Search the web and return results.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            ),
            MCPToolDescriptor(
                name="hive.bash.classify",
                description="Classify a bash command for safety risk level.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to classify"},
                    },
                    "required": ["command"],
                },
            ),
            MCPToolDescriptor(
                name="hive.bash.parse",
                description="Parse a bash command into structural components (AST).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to parse"},
                    },
                    "required": ["command"],
                },
            ),
            MCPToolDescriptor(
                name="hive.skill.run",
                description="Execute a registered skill by name.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string", "description": "Name of the skill to execute"},
                        "input": {"type": "string", "description": "Input data for the skill"},
                    },
                    "required": ["skill_name"],
                },
            ),
        ]

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "server_name": self.server_name,
            "tools_registered": len(self._tools),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in self._tools]

    def list_skills(self) -> list[dict[str, Any]]:
        """Return all registered skills from the SkillRegistry."""
        try:
            from skill_registry import skill_registry
            return skill_registry.to_mcp_descriptors()
        except ImportError:
            logger.debug("[MCPBridge] SkillRegistry not available")
            return []

    def client_config(self, host_hint: str | None = None) -> dict[str, Any]:
        base = (host_hint or self.base_url).rstrip("/")
        cfg = MCPClientConfig(
            mcpServers={
                self.server_name: {
                    "transport": "http",
                    "url": f"{base}/api/v1/mcp/rpc",
                    "headers": {"x-hive-client": "free-code"},
                }
            }
        )
        return cfg.model_dump()

    async def handle_rpc(self, method: str, params: Dict[str, Any], auth_header: str | None = None) -> dict[str, Any]:
        """Handle minimal MCP methods with safe, non-breaking behavior."""
        if method == "tools/list":
            return {"tools": self.list_tools()}

        if method == "skills/list":
            return {"skills": self.list_skills()}

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return self.tool_hooks.execute(str(tool_name), arguments, auth_header)

        if method in {"initialize", "ping"}:
            return {
                "server": self.server_name,
                "enabled": self.enabled,
            }

        raise ValueError(f"Unsupported MCP method: {method}")


_mcp_server_singleton: MCPBridgeServer | None = None


def get_mcp_server() -> MCPBridgeServer:
    global _mcp_server_singleton
    if _mcp_server_singleton is None:
        _mcp_server_singleton = MCPBridgeServer()
    return _mcp_server_singleton
