"""Update a Home Assistant Assist pipeline using its supported WebSocket API.

Run inside a container that has HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN.
"""

from __future__ import annotations

import asyncio
import json
import os

import websockets

PIPELINE_ID = os.environ["PIPELINE_ID"]
CONVERSATION_ENGINE = os.environ["CONVERSATION_ENGINE"]


async def _command(websocket, message: dict) -> dict:
    await websocket.send(json.dumps(message))
    while True:
        response = json.loads(await websocket.recv())
        if response.get("id") == message["id"]:
            return response


async def _update() -> None:
    base_url = os.environ["HOME_ASSISTANT_URL"].rstrip("/")
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/api/websocket"

    async with websockets.connect(ws_url) as websocket:
        await websocket.recv()  # auth_required
        await websocket.send(
            json.dumps({"type": "auth", "access_token": os.environ["HOME_ASSISTANT_TOKEN"]})
        )
        auth = json.loads(await websocket.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"Home Assistant WebSocket authentication failed: {auth}")

        current = await _command(
            websocket,
            {
                "id": 1,
                "type": "assist_pipeline/pipeline/get",
                "pipeline_id": PIPELINE_ID,
            },
        )
        if not current.get("success"):
            raise RuntimeError(f"Could not read pipeline: {current}")

        pipeline = current["result"]
        pipeline["conversation_engine"] = CONVERSATION_ENGINE
        pipeline.update(
            {
                "id": 2,
                "type": "assist_pipeline/pipeline/update",
                "pipeline_id": PIPELINE_ID,
            }
        )
        updated = await _command(websocket, pipeline)
        if not updated.get("success"):
            raise RuntimeError(f"Could not update pipeline: {updated}")

        result = updated["result"]
        print(
            json.dumps(
                {
                    "pipeline_id": result["id"],
                    "name": result["name"],
                    "conversation_engine": result["conversation_engine"],
                }
            )
        )


asyncio.run(_update())
