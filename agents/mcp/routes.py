"""Stateless MCP HTTP transport; mounted before the legacy RPC endpoint."""
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from mcp.schema import MCPRpcRequest
from mcp.server import get_mcp_server
from mcp.transport import error_response, internal_error, ok_response

router = APIRouter()


@router.post('/api/v1/mcp/rpc')
async def rpc(payload: MCPRpcRequest, request: Request):
    # JSON-RPC notifications have no response. Never execute a tools/call
    # notification: side-effecting calls require a request ID and reply.
    if 'id' not in payload.model_fields_set:
        return Response(status_code=202)
    try:
        result = await get_mcp_server().handle_rpc(
            payload.method, payload.params,
            auth_header=request.headers.get('Authorization'),
        )
        reply = ok_response(payload.id, result)
    except ValueError as exc:
        reply = error_response(payload.id, -32601, str(exc))
    except Exception as exc:
        reply = internal_error(payload.id, exc, {'method': payload.method})
    return JSONResponse(reply.model_dump(exclude_none=True))


@router.get('/api/v1/mcp/rpc')
async def no_server_stream():
    # This stateless transport does not offer server-initiated SSE messages.
    return Response(status_code=405, headers={'Allow': 'POST'})
