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
            # Phase 5: Remote & Multi-Node
            MCPToolDescriptor(
                name="hive.remote.exec",
                description="Execute a command on a remote host via SSH.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "Target host name (justin-pc, control-plane, r730)"},
                        "command": {"type": "string", "description": "Shell command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
                    },
                    "required": ["host", "command"],
                },
            ),
            MCPToolDescriptor(
                name="hive.bridge.submit",
                description="Submit an async task to a remote Hive node.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_node": {"type": "string", "description": "Target node name"},
                        "task": {"type": "string", "description": "Task description"},
                        "intent": {"type": "string", "description": "Optional intent override"},
                    },
                    "required": ["target_node", "task"],
                },
            ),
            MCPToolDescriptor(
                name="hive.bridge.proxy",
                description="Proxy an API request to a remote Hive node.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_node": {"type": "string", "description": "Target node name"},
                        "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
                        "path": {"type": "string", "description": "API path (e.g. /v1/models)"},
                        "json_body": {"type": "object", "description": "Optional JSON body"},
                    },
                    "required": ["target_node", "method", "path"],
                },
            ),
            MCPToolDescriptor(
                name="hive.daemon.list",
                description="List registered daemon workers.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "state_filter": {"type": "string", "description": "Filter by state (pending, running, stopped, failed)"},
                    },
                },
            ),
            MCPToolDescriptor(
                name="hive.workflow.run",
                description="List or inspect workflow executions.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "Optional workflow ID to inspect"},
                    },
                },
            ),
            MCPToolDescriptor(
                name="hive.trigger.list",
                description="List registered triggers (cron, interval, once).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "type_filter": {"type": "string", "description": "Filter by type (cron, interval, once)"},
                    },
                },
            ),
            # Phase 6: OpenClaude gRPC
            MCPToolDescriptor(
                name="hive.grpc.infer",
                description="Run inference via the OpenClaude gRPC gateway with auto model routing.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt to send"},
                        "model": {"type": "string", "description": "Explicit model name (auto-routes if empty)"},
                        "intent": {"type": "string", "description": "Routing hint: CODE, GENERAL, RESEARCH, VISION"},
                    },
                    "required": ["prompt"],
                },
            ),
            MCPToolDescriptor(
                name="hive.grpc.classify",
                description="Classify the intent of a prompt using the router model.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Prompt to classify"},
                    },
                    "required": ["prompt"],
                },
            ),
            MCPToolDescriptor(
                name="hive.grpc.models",
                description="List models available across all Ollama nodes.",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPToolDescriptor(
                name="hive.grpc.health",
                description="Health check of the OpenClaude gRPC inference gateway.",
                input_schema={"type": "object", "properties": {}},
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
