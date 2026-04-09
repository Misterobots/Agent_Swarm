from __future__ import annotations

import os
from typing import Any, Dict, List

from logger_setup import setup_logger
from mcp.schema import MCPToolDescriptor, MCPClientConfig
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
        ]

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "server_name": self.server_name,
            "tools_registered": len(self._tools),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in self._tools]

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
