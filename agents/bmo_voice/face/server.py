"""
BMO Face Server — serves the face UI and handles WebSocket connections.

Lightweight aiohttp server that:
  1. Serves the static HTML/CSS/JS face UI
  2. Accepts WebSocket connections for real-time expression control
  3. Designed to run on Raspberry Pi 3B in kiosk mode
"""

import asyncio
import logging
import pathlib

from aiohttp import web

# Import relative to this package, assuming this structure
from .ws_handler import WebSocketHandler

logger = logging.getLogger(__name__)

# Correct path logic: 'static' is in the same directory as this file
STATIC_DIR = pathlib.Path(__file__).parent.resolve() / "static"

# Map of content types for static files
CONTENT_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}


class FaceServer:
    """HTTP + WebSocket server for BMO's face display."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, on_message=None):
        self.host = host
        self.port = port
        self.ws_handler = WebSocketHandler(on_message=on_message)
        self.app = web.Application()
        self._setup_routes()
        self._runner = None

    def _setup_routes(self):
        logger.debug(f"Static dir: {STATIC_DIR} (exists={STATIC_DIR.exists()})")
        self.app.router.add_get("/ws", self._websocket_handler)
        self.app.router.add_get("/", self._index_handler)
        # Serve static files with an explicit handler (more reliable than add_static on Windows)
        self.app.router.add_get("/static/{filename:.+}", self._static_handler)

    async def _index_handler(self, request: web.Request) -> web.FileResponse:
        """Serve the main face HTML page."""
        return web.FileResponse(STATIC_DIR / "index.html")

    async def _static_handler(self, request: web.Request) -> web.Response:
        """Serve static files from the static directory."""
        filename = request.match_info["filename"]
        filepath = STATIC_DIR / filename

        # Security: ensure the path doesn't escape the static directory
        try:
            filepath = filepath.resolve()
            # Simple check to ensure we are inside static dir
            if not str(filepath).startswith(str(STATIC_DIR.resolve())):
                raise web.HTTPForbidden()
        except (ValueError, OSError):
            raise web.HTTPNotFound()

        if not filepath.is_file():
            raise web.HTTPNotFound()

        content_type = CONTENT_TYPES.get(filepath.suffix, "application/octet-stream")
        return web.FileResponse(filepath, headers={"Content-Type": content_type})

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections from the face UI."""
        return await self.ws_handler.handle(request)

    async def start(self):
        """Start the face server (non-blocking)."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"BMO Face server running at http://localhost:{self.port}")

    async def stop(self):
        """Gracefully stop the face server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("BMO Face server stopped")

    async def send_expression(self, expression: str, mouth_sync: list = None):
        """Send an expression command to the face UI."""
        await self.ws_handler.send_expression(expression, mouth_sync)

    async def send_text(self, text: str):
        """Send text to display on BMO's face (e.g. subtitles)."""
        await self.ws_handler.send_message({
            "type": "text",
            "value": text
        })
