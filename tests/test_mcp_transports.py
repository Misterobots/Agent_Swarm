"""Transport-level MCP checks that do not require the full runtime app stack."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from mcp.schema import MCPRpcRequest
from mcp.server import MCPBridgeServer
from mcp.transport import error_response, internal_error, ok_response


def _transport_app(server: MCPBridgeServer) -> FastAPI:
    app = FastAPI()

    @app.get("/sse")
    async def sse(request: Request):
        async def events():
            yield "event: endpoint\ndata: http://testserver/rpc\n\n"
            while not await request.is_disconnected():
                # The client closes after the discovery event in this test.
                return
        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/rpc")
    async def rpc(request: MCPRpcRequest):
        try:
            return ok_response(request.id, await server.handle_rpc(request.method, request.params)).model_dump(exclude_none=True)
        except ValueError as exc:
            return error_response(request.id, -32601, str(exc)).model_dump(exclude_none=True)
        except Exception as exc:
            return internal_error(request.id, exc, {"transport": "http"}).model_dump(exclude_none=True)

    @app.websocket("/ws")
    async def websocket(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                payload = await websocket.receive_json()
                try:
                    request = MCPRpcRequest.model_validate(payload)
                    result = await server.handle_rpc(request.method, request.params)
                    response = ok_response(request.id, result)
                except ValueError as exc:
                    response = error_response(payload.get("id"), -32601, str(exc))
                await websocket.send_json(response.model_dump(exclude_none=True))
        except WebSocketDisconnect:
            return

    return app


def test_mcp_lifecycle_controls_are_idempotent():
    server = MCPBridgeServer()
    assert server.running is True
    stopped = server.stop()
    assert stopped["status"] == "stopped"
    assert server.stop()["status"] == "stopped"
    started = server.start()
    assert started["status"] == "running"
    assert server.start()["status"] == "running"


def test_sse_discovery_and_websocket_json_rpc():
    client = TestClient(_transport_app(MCPBridgeServer()))
    with client.stream("GET", "/sse") as response:
        assert response.status_code == 200
        first = next(response.iter_lines())
        assert first == "event: endpoint"

    with client.websocket_connect("/ws") as socket:
        socket.send_json({"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {}})
        result = socket.receive_json()
        assert result["id"] == 4
        assert result["result"]["protocolVersion"] == "2025-06-18"


def test_stdio_round_trip():
    agents_dir = str(Path(__file__).resolve().parents[1] / "agents")
    env = dict(os.environ)
    env["PYTHONPATH"] = agents_dir
    request = {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}}
    result = subprocess.run(
        [sys.executable, "-m", "mcp.stdio"],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
        check=True,
    )
    response = json.loads(result.stdout.strip().splitlines()[-1])
    assert response["id"] == 9
    assert response["result"]["server"] == "home-ai-lab"
