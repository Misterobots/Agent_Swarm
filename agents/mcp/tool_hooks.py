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
            "hive.browser.fetch": ToolHook("browser_fetch", "L2_USER", self._handle_browser_fetch),
            "hive.browser.search": ToolHook("browser_search", "L2_USER", self._handle_browser_search),
            "hive.bash.classify": ToolHook("terminal_classify", "L2_USER", self._handle_bash_classify),
            "hive.bash.parse": ToolHook("terminal_parse", "L2_USER", self._handle_bash_parse),
            "hive.skill.run": ToolHook("skill_exec", "L2_USER", self._handle_skill_run),
            # Phase 5: Remote & Multi-Node
            "hive.remote.exec": ToolHook("remote_exec", "L3_ADMIN", self._handle_remote_exec),
            "hive.bridge.submit": ToolHook("bridge_submit", "L3_ADMIN", self._handle_bridge_submit),
            "hive.bridge.proxy": ToolHook("bridge_proxy", "L3_ADMIN", self._handle_bridge_proxy),
            "hive.daemon.list": ToolHook("daemon_manage", "L2_USER", self._handle_daemon_list),
            "hive.workflow.run": ToolHook("workflow_exec", "L3_ADMIN", self._handle_workflow_run),
            "hive.trigger.list": ToolHook("trigger_manage", "L2_USER", self._handle_trigger_list),
            # Phase 6: OpenClaude gRPC
            "hive.grpc.infer": ToolHook("grpc_infer", "L2_USER", self._handle_grpc_infer),
            "hive.grpc.classify": ToolHook("grpc_classify", "L2_USER", self._handle_grpc_classify),
            "hive.grpc.models": ToolHook("grpc_infer", "L1_PUBLIC", self._handle_grpc_models),
            "hive.grpc.health": ToolHook("grpc_infer", "L1_PUBLIC", self._handle_grpc_health),
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

    @staticmethod
    def _handle_browser_fetch(args: dict[str, Any]) -> dict[str, Any]:
        from tools.web_browser import fetch_page
        url = str(args.get("url", ""))
        result = fetch_page(url)
        is_error = result.get("error", False)
        text = result.get("text", "")
        if result.get("title"):
            text = f"# {result['title']}\n\n{text}"
        return {"isError": is_error, "content": [{"type": "text", "text": text}]}

    @staticmethod
    def _handle_browser_search(args: dict[str, Any]) -> dict[str, Any]:
        from tools.web_browser import web_search
        query = str(args.get("query", ""))
        results = web_search(query)
        text = "\n".join(f"- [{r['title']}]({r['url']}): {r['snippet']}" for r in results)
        return {"isError": False, "content": [{"type": "text", "text": text or "No results found"}]}

    @staticmethod
    def _handle_bash_classify(args: dict[str, Any]) -> dict[str, Any]:
        from tools.bash_classifier import classify_command
        command = str(args.get("command", ""))
        result = classify_command(command)
        return {"isError": False, "content": [{"type": "text", "text": str(result)}]}

    @staticmethod
    def _handle_bash_parse(args: dict[str, Any]) -> dict[str, Any]:
        from tools.bash_parser import parse_bash
        command = str(args.get("command", ""))
        result = parse_bash(command)
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(result.to_dict(), indent=2)}]}

    @staticmethod
    def _handle_skill_run(args: dict[str, Any]) -> dict[str, Any]:
        from skill_registry import skill_registry
        skill_name = str(args.get("skill_name", ""))
        skill = skill_registry.get(skill_name)
        if not skill:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown skill: {skill_name}"}]}
        if not skill.enabled:
            return {"isError": True, "content": [{"type": "text", "text": f"Skill disabled: {skill_name}"}]}
        try:
            return skill.handler(args)
        except Exception as e:
            logger.error(f"[MCPToolHooks] Skill execution failed: {skill_name} - {e}")
            return {"isError": True, "content": [{"type": "text", "text": f"Skill error: {e}"}]}

    # --- Phase 5: Remote & Multi-Node handlers ---

    @staticmethod
    def _handle_remote_exec(args: dict[str, Any]) -> dict[str, Any]:
        from utils.remote_executor import get_remote_executor
        host = str(args.get("host", ""))
        command = str(args.get("command", ""))
        timeout = int(args.get("timeout", 60))
        result = get_remote_executor().execute(host, command, timeout=timeout)
        import json
        return {"isError": not result.success, "content": [{"type": "text", "text": json.dumps(result.to_dict(), indent=2)}]}

    @staticmethod
    def _handle_bridge_submit(args: dict[str, Any]) -> dict[str, Any]:
        from utils.bridge import get_bridge
        target = str(args.get("target_node", ""))
        task = str(args.get("task", ""))
        intent = args.get("intent")
        result = get_bridge().submit_task(target, task, intent=intent)
        import json
        return {"isError": "error" in result, "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}

    @staticmethod
    def _handle_bridge_proxy(args: dict[str, Any]) -> dict[str, Any]:
        from utils.bridge import get_bridge
        target = str(args.get("target_node", ""))
        method = str(args.get("method", "GET"))
        path = str(args.get("path", "/"))
        body = args.get("json_body")
        result = get_bridge().proxy_request(target, method, path, json_body=body)
        import json
        return {"isError": "error" in result, "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}

    @staticmethod
    def _handle_daemon_list(args: dict[str, Any]) -> dict[str, Any]:
        from daemon_registry import get_daemon_registry
        state_filter = args.get("state_filter")
        workers = get_daemon_registry().list_workers(state_filter=state_filter)
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(workers, indent=2, default=str)}]}

    @staticmethod
    def _handle_workflow_run(args: dict[str, Any]) -> dict[str, Any]:
        from workflow_engine import get_workflow_engine
        wf_list = get_workflow_engine().list_workflows()
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(wf_list, indent=2, default=str)}]}

    @staticmethod
    def _handle_trigger_list(args: dict[str, Any]) -> dict[str, Any]:
        from trigger_scheduler import get_trigger_scheduler
        type_filter = args.get("type_filter")
        triggers = get_trigger_scheduler().list_triggers(type_filter=type_filter)
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(triggers, indent=2, default=str)}]}

    # --- Phase 6: OpenClaude gRPC handlers ---

    @staticmethod
    def _handle_grpc_infer(args: dict[str, Any]) -> dict[str, Any]:
        from grpc.client import get_grpc_client
        prompt = str(args.get("prompt", ""))
        model = str(args.get("model", ""))
        intent = str(args.get("intent", ""))
        result = get_grpc_client().infer(prompt=prompt, model=model, intent=intent)
        import json
        return {"isError": bool(result.get("error")), "content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    @staticmethod
    def _handle_grpc_classify(args: dict[str, Any]) -> dict[str, Any]:
        from grpc.client import get_grpc_client
        prompt = str(args.get("prompt", ""))
        result = get_grpc_client().classify(prompt=prompt)
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    @staticmethod
    def _handle_grpc_models(args: dict[str, Any]) -> dict[str, Any]:
        from grpc.client import get_grpc_client
        models = get_grpc_client().list_models()
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(models, indent=2)}]}

    @staticmethod
    def _handle_grpc_health(args: dict[str, Any]) -> dict[str, Any]:
        from grpc.client import get_grpc_client
        health = get_grpc_client().health_check()
        import json
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(health, indent=2)}]}
