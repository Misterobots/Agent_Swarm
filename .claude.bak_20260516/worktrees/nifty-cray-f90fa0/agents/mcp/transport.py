from __future__ import annotations

from typing import Any, Dict

from mcp.schema import MCPRpcError, MCPRpcResponse


def ok_response(request_id: str | int | None, result: Dict[str, Any]) -> MCPRpcResponse:
    return MCPRpcResponse(id=request_id, result=result)


def error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    data: Dict[str, Any] | None = None,
) -> MCPRpcResponse:
    return MCPRpcResponse(id=request_id, error=MCPRpcError(code=code, message=message, data=data))


def internal_error(request_id: str | int | None, exc: Exception, context: Dict[str, Any]) -> MCPRpcResponse:
    return error_response(
        request_id=request_id,
        code=-32603,
        message="Internal MCP bridge error",
        data={"error": str(exc), **context},
    )
