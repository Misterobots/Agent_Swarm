"""
Remote pairing — WebSocket-based session sharing between Memex Desktop instances.

Flow:
  Host  → POST /api/v1/pairing/create        → { code, token }
  Guest → POST /api/v1/pairing/join/{code}   → { token, host_info }
  Both  → WS   /api/v1/pairing/ws/{token}    → bidirectional relay

Rooms expire after 30 minutes of inactivity. Max 2 participants per room.
"""

import asyncio
import secrets
import time
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])

# ---------------------------------------------------------------------------
# In-memory room store (single-node; good enough for home lab)
# ---------------------------------------------------------------------------
class Room:
    def __init__(self, code: str, host_info: dict):
        self.code       = code
        self.host_info  = host_info
        self.host_token = secrets.token_urlsafe(24)
        self.guest_token: str | None = None
        self.sockets:    Dict[str, WebSocket] = {}  # token → socket
        self.created_at = time.time()
        self.last_activity = time.time()

    def touch(self):
        self.last_activity = time.time()

    @property
    def expired(self) -> bool:
        return time.time() - self.last_activity > 30 * 60  # 30 min

_rooms_by_code:  Dict[str, Room] = {}
_rooms_by_token: Dict[str, Room] = {}

def _cleanup():
    expired = [c for c, r in _rooms_by_code.items() if r.expired]
    for code in expired:
        room = _rooms_by_code.pop(code, None)
        if room:
            _rooms_by_token.pop(room.host_token, None)
            if room.guest_token:
                _rooms_by_token.pop(room.guest_token, None)

def _make_code() -> str:
    """6 uppercase alphanumeric characters, easy to read aloud."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
class CreateRequest(BaseModel):
    display_name: str = "Memex Desktop"
    memex_url:    str = ""

class JoinRequest(BaseModel):
    display_name: str = "Memex Desktop"

@router.post("/create")
async def create_room(body: CreateRequest, request: Request):
    _cleanup()
    code = _make_code()
    while code in _rooms_by_code:
        code = _make_code()

    room = Room(code, {
        "display_name": body.display_name,
        "memex_url":    body.memex_url,
        "uid":          request.headers.get("X-authentik-uid", "desktop"),
    })
    _rooms_by_code[code]             = room
    _rooms_by_token[room.host_token] = room

    return {
        "code":        code,
        "token":       room.host_token,
        "expires_in":  30 * 60,
    }


@router.post("/join/{code}")
async def join_room(code: str, body: JoinRequest, request: Request):
    _cleanup()
    room = _rooms_by_code.get(code.upper())
    if not room:
        raise HTTPException(status_code=404, detail="Room not found or expired")
    if room.guest_token:
        raise HTTPException(status_code=409, detail="Room already has a guest")

    room.guest_token = secrets.token_urlsafe(24)
    _rooms_by_token[room.guest_token] = room

    return {
        "token":     room.guest_token,
        "host_info": room.host_info,
        "code":      code,
    }


@router.delete("/leave/{token}")
async def leave_room(token: str):
    room = _rooms_by_token.pop(token, None)
    if not room:
        return {"ok": True}
    if token == room.host_token:
        # Host left — dissolve the room
        _rooms_by_code.pop(room.code, None)
        if room.guest_token:
            _rooms_by_token.pop(room.guest_token, None)
    else:
        room.guest_token = None
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket relay
# ---------------------------------------------------------------------------
@router.websocket("/ws/{token}")
async def pairing_ws(websocket: WebSocket, token: str):
    room = _rooms_by_token.get(token)
    if not room:
        await websocket.close(code=4404, reason="Room not found")
        return

    await websocket.accept()
    room.sockets[token] = websocket
    room.touch()

    role = "host" if token == room.host_token else "guest"
    peer_token = room.guest_token if role == "host" else room.host_token

    # Announce presence to peer
    if peer_token and peer_token in room.sockets:
        try:
            await room.sockets[peer_token].send_json({"type": "peer_joined", "role": role})
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_json()
            room.touch()
            # Relay to peer only (not back to sender)
            peer = _rooms_by_token.get(peer_token) if peer_token else None
            if peer and peer_token and peer_token in room.sockets:
                try:
                    await room.sockets[peer_token].send_json({**data, "_from": role})
                except Exception:
                    pass
    except WebSocketDisconnect:
        room.sockets.pop(token, None)
        if peer_token and peer_token in room.sockets:
            try:
                await room.sockets[peer_token].send_json({"type": "peer_left", "role": role})
            except Exception:
                pass
