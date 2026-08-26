"""Line-delimited JSON-RPC stdio transport for the MCP bridge.

Run with ``python -m mcp.stdio`` from the Agent_Swarm ``agents`` path. One
JSON-RPC request is read per line and one response is written per line; logs
remain on stderr so stdout stays protocol-clean.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp.schema import MCPRpcRequest
from mcp.server import get_mcp_server
from mcp.transport import error_response, internal_error, ok_response


async def serve() -> None:
    server = get_mcp_server()
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return
        if not line.strip():
            continue
        request_id = None
        try:
            request = MCPRpcRequest.model_validate(json.loads(line))
            request_id = request.id
            result = await server.handle_rpc(request.method, request.params)
            response = ok_response(request.id, result)
        except ValueError as exc:
            response = error_response(request_id, -32601, str(exc))
        except Exception as exc:
            response = internal_error(request_id, exc, {"transport": "stdio"})
        sys.stdout.write(json.dumps(response.model_dump(exclude_none=True), separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(serve())
