"""
BMO Face WebSocket Handler — manages real-time communication with the face UI.

Broadcasts expression commands, mouth sync data, and text messages
to all connected face UI clients.
"""

import json
import logging
import asyncio
from typing import Optional, Set, Callable, Awaitable

from aiohttp import web

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Manages WebSocket connections to the BMO face UI."""

    def __init__(self, on_message: Callable[[str], Awaitable[None]] = None):
        self._clients: Set[web.WebSocketResponse] = set()
        self.on_message = on_message

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._clients.add(ws)
        logger.info(f"Client connected. Total: {len(self._clients)}")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "chat" and self.on_message:
                            # Context isolation: run callback
                            asyncio.create_task(self.on_message(data.get("text", "")))
                        else:
                            logger.debug(f"Received unknown: {msg.data}")
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON: {msg.data}")
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WS connection closed with exception {ws.exception()}")
        finally:
            self._clients.remove(ws)
            logger.info("Client disconnected")

        return ws

    async def send_expression(self, expression: str, mouth_sync: Optional[list] = None):
        """
        Send an expression change command to all connected face UIs.

        Args:
            expression: One of: neutral, happy, sad, surprised, thinking,
                        listening, speaking, sleeping, error, excited
            mouth_sync: Optional list of amplitude values (0.0-1.0) for
                        mouth animation during speech
        """
        message = {
            "type": "expression",
            "value": expression,
        }
        if mouth_sync is not None:
            message["mouth_sync"] = mouth_sync

        await self.send_message(message)

    async def send_message(self, message: dict):
        """Broadcast a JSON message to all connected face UI clients."""
        if not self._clients:
            logger.debug("No face UI clients connected, skipping broadcast")
            return

        data = json.dumps(message)
        disconnected = set()

        for ws in self._clients:
            try:
                await ws.send_str(data)
            except (ConnectionResetError, ConnectionError):
                disconnected.add(ws)
                logger.warning("Client disconnected during send")

        # Clean up disconnected clients
        for ws in disconnected:
            self._clients.discard(ws)
