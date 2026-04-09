from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from logger_setup import setup_logger
from mcp.security_hooks import enforce_capability
from security.audit_logger import get_audit_logger
from tools.file_ops import read_file as tool_read_file, write_file as tool_write_file, list_dir as tool_list_dir
from tools.terminal import run_command as tool_run_command

logger = setup_logger("MCPToolHooks")


@dataclass
class ToolHook:
    capability: str
    min_level: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]


class ToolHookRegistry:
    def __init__(self):
        self._hooks: Dict[str, ToolHook] = {
            "hive.fs.read": ToolHook("file_read", "L2_USER", self._handle_read_file),
            "hive.fs.write": ToolHook("file_write", "L3_ADMIN", self._handle_write_file),
            "hive.fs.list": ToolHook("file_read", "L2_USER", self._handle_list_dir),
            "hive.terminal.run": ToolHook("terminal_exec", "L3_ADMIN", self._handle_terminal),
        }

    def names(self) -> list[str]:
        return list(self._hooks.keys())

    def execute(self, name: str, arguments: dict[str, Any], auth_header: str | None) -> dict[str, Any]:
        audit = get_audit_logger()
        hook = self._hooks.get(name)
        if not hook:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            }

        decision = enforce_capability(
            auth_header=auth_header,
            required_capability=hook.capability,
            resource=name,
            min_level=hook.min_level,
        )

        if not decision.allowed:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Access denied: {decision.reason}"}],
            }

        card = decision.card
        try:
            result = hook.handler(arguments)
            if card:
                audit.log_operation_executed(
                    agent_name=card.agent_name,
                    agent_id=card.agent_instance_id,
                    operation="tool_call",
                    resource=name,
                    success=True,
                    details={"arguments_keys": sorted(arguments.keys())},
                )
            return result
        except Exception as e:
            logger.error(f"[MCPToolHooks] Tool execution failed: {name} - {e}")
            if card:
                audit.log_operation_executed(
                    agent_name=card.agent_name,
                    agent_id=card.agent_instance_id,
                    operation="tool_call",
                    resource=name,
                    success=False,
                    details={"error": str(e), "arguments_keys": sorted(arguments.keys())},
                )
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool execution failed: {e}"}],
            }

    @staticmethod
    def _handle_read_file(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path", ""))
        content = tool_read_file(path)
        return {"isError": False, "content": [{"type": "text", "text": content}]}

    @staticmethod
    def _handle_write_file(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        output = tool_write_file(path, content)
        return {"isError": False, "content": [{"type": "text", "text": output}]}

    @staticmethod
    def _handle_list_dir(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path", "."))
        output = tool_list_dir(path)
        return {"isError": False, "content": [{"type": "text", "text": output}]}

    @staticmethod
    def _handle_terminal(args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", ""))
        output = tool_run_command(command)
        return {"isError": False, "content": [{"type": "text", "text": output}]}
