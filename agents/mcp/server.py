from __future__ import annotations

import os
import json
from typing import Any, Dict, List

from logger_setup import setup_logger
from mcp.schema import (
    MCPClientConfig,
    MCPPromptDescriptor,
    MCPResourceDescriptor,
    MCPToolDescriptor,
)
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
        self._resources = [
            MCPResourceDescriptor(
                uri=f"memex://{self.server_name}/tools",
                name="Registered tools",
                description="JSON descriptor for the tools exposed by this MCP bridge.",
                mimeType="application/json",
            ),
            MCPResourceDescriptor(
                uri=f"memex://{self.server_name}/skills",
                name="Registered skills",
                description="JSON descriptor for the skills currently available to the bridge.",
                mimeType="application/json",
            ),
        ]
        self._prompts = [
            MCPPromptDescriptor(
                name="memex.research",
                description="Research a question with the bridge's web search and fetch tools.",
                arguments=[{"name": "query", "description": "Question or topic to research.", "required": True}],
            ),
            MCPPromptDescriptor(
                name="memex.code_review",
                description="Review code or a change request and return actionable findings.",
                arguments=[{"name": "request", "description": "Code or review request.", "required": True}],
            ),
        ]

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
                        "host": {"type": "string", "description": "Target host name (Lovelace, control-plane, Turing)"},
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
        capabilities = self.capabilities()
        return {
            "enabled": self.enabled,
            "server_name": self.server_name,
            "tools_registered": len(self._tools),
            "resources_registered": len(self._resources),
            "prompts_registered": len(self._prompts),
            "transports": ["http", "sse", "websocket", "stdio"],
            "capabilities": capabilities,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False},
            "prompts": {"listChanged": False},
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
                    "capabilities": self.capabilities(),
                },
                f"{self.server_name}-sse": {
                    "transport": "sse",
                    "url": f"{base}/api/v1/mcp/sse",
                    "capabilities": self.capabilities(),
                },
                f"{self.server_name}-websocket": {
                    "transport": "websocket",
                    "url": f"{base.replace('https://', 'wss://').replace('http://', 'ws://')}/api/v1/mcp/ws",
                    "capabilities": self.capabilities(),
                },
                f"{self.server_name}-stdio": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "mcp.stdio"],
                    "capabilities": self.capabilities(),
                },
            }
        )
        return cfg.model_dump()

    async def handle_rpc(self, method: str, params: Dict[str, Any], auth_header: str | None = None) -> dict[str, Any]:
        """Handle minimal MCP methods with safe, non-breaking behavior."""
        if method == "tools/list":
            return {"tools": self.list_tools()}

        if method == "skills/list":
            return {"skills": self.list_skills()}

        if method == "resources/list":
            return {"resources": [resource.model_dump() for resource in self._resources]}

        if method == "resources/read":
            uri = str(params.get("uri", ""))
            known = {resource.uri: resource for resource in self._resources}
            resource = known.get(uri)
            if resource is None:
                raise ValueError(f"Unknown MCP resource: {uri}")
            if uri.endswith("/tools"):
                text = json.dumps(self.list_tools(), separators=(",", ":"))
            else:
                text = json.dumps(self.list_skills(), separators=(",", ":"))
            return {"contents": [{"uri": uri, "mimeType": resource.mimeType, "text": text}]}

        if method == "prompts/list":
            return {"prompts": [prompt.model_dump() for prompt in self._prompts]}

        if method == "prompts/get":
            name = str(params.get("name", ""))
            prompt = next((item for item in self._prompts if item.name == name), None)
            if prompt is None:
                raise ValueError(f"Unknown MCP prompt: {name}")
            arguments = params.get("arguments") or {}
            missing = [arg.name for arg in prompt.arguments if arg.required and not arguments.get(arg.name)]
            if missing:
                raise ValueError(f"Missing MCP prompt arguments: {', '.join(missing)}")
            if name == "memex.research":
                text = (
                    "Research the following question using web search and fetch, cite the sources, "
                    f"and distinguish facts from inference:\n\n{arguments.get('query', '')}"
                )
            else:
                text = (
                    "Review the following code request. Identify correctness, security, and maintainability "
                    f"issues, then propose focused fixes:\n\n{arguments.get('request', '')}"
                )
            return {"description": prompt.description, "messages": [
                {"role": "user", "content": {"type": "text", "text": text}},
            ]}

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return self.tool_hooks.execute(str(tool_name), arguments, auth_header)

        if method in {"initialize", "ping"}:
            return {
                "server": self.server_name,
                "enabled": self.enabled,
                "protocolVersion": "2025-06-18",
                "capabilities": self.capabilities(),
            }

        raise ValueError(f"Unsupported MCP method: {method}")


_mcp_server_singleton: MCPBridgeServer | None = None


def get_mcp_server() -> MCPBridgeServer:
    global _mcp_server_singleton
    if _mcp_server_singleton is None:
        _mcp_server_singleton = MCPBridgeServer()
    return _mcp_server_singleton


