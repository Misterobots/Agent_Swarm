"""Home Assistant registry editing for bmo_brain — move a device to an area, assign a single
entity to an area, rename a device/entity, and create an area.

These are HA *config-registry writes*, which Home Assistant exposes ONLY over its WebSocket
API — there is no REST endpoint for them (unlike the REST /api/services and /api/template
calls that tools.py and hass_resolver.py use). That's the whole reason this module exists
separately and reaches for `websockets` (already present in the image via uvicorn[standard]).

Name → id resolution mirrors hass_resolver.py's approach (normalize + exact, then stdlib
difflib fuzzy) so spoken names like "Living Room Lamp" or "the garage" resolve against the
real registry. Areas also match on their HA aliases. A device can be named directly, or
addressed by one of its entities (we walk entity -> device_id).

Wired into BOTH tool-calling paths:
  - self-executing (Pi driver): added to tools.py's TOOL_SCHEMAS / _DISPATCH
  - passthrough (HA Assist voice): executed by main.py's gated passthrough loop, since HA has
    no Assist intent for registry edits and cannot execute these itself.

Every operation opens a fresh short-lived WS session (auth handshake + the list/update
commands it needs), so there is no long-lived socket to keep healthy and no stale cache to
go wrong across an edit — registry edits are infrequent, correctness matters more than the
few hundred ms a reconnect costs. Every public function returns a short spoken-style string
and never raises: any failure (HA unreachable, auth, not-found, HA refusal) degrades to a
plain sentence the model can relay.
"""
import asyncio
import contextlib
import difflib
import json
import logging
import os
import re

# websockets >= 13 exposes the new asyncio client at websockets.asyncio.client; older
# versions only have the top-level (now-legacy) connect. Prefer the new one.
try:  # pragma: no cover - import shim
    from websockets.asyncio.client import connect as _ws_connect
except ImportError:  # pragma: no cover
    from websockets import connect as _ws_connect

logger = logging.getLogger(__name__)

HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "http://192.168.2.100:8123").rstrip("/")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")

_WS_TIMEOUT = float(os.getenv("HASS_WS_TIMEOUT", "10"))
# Shorter CONNECT timeout so a firewalled/unreachable HA WebSocket fails fast instead of stacking
# 10s hangs across the several ops a registry turn issues (which could exceed HA Assist's own
# conversation timeout). The per-message recv timeout stays at _WS_TIMEOUT.
_WS_CONNECT_TIMEOUT = float(os.getenv("HASS_WS_CONNECT_TIMEOUT", "5"))
# Registry edits are IRREVERSIBLE writes, so name resolution here is intentionally stricter than
# the 0.72 hass_resolver uses for reversible on/off: a near-miss ("lamp" vs "ramp", ratio 0.75)
# must NOT silently mutate the wrong device/entity/area. Better to fail with "couldn't find X"
# and let the user rephrase than to move or rename the wrong thing.
_FUZZY_CUTOFF = float(os.getenv("HASS_REG_FUZZY_CUTOFF", "0.85"))
_MAX_MSG = 16 * 1024 * 1024  # a large household's registry list can be a few hundred KB


def _ws_url() -> str:
    base = HOME_ASSISTANT_URL
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):] + "/api/websocket"
    if base.startswith("http://"):
        return "ws://" + base[len("http://"):] + "/api/websocket"
    return "ws://" + base + "/api/websocket"


def _norm(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"[^a-z0-9 ]", "", raw.lower())
    return re.sub(r"\s+", " ", s).strip()


def _best_id(name: str, candidates: list):
    """candidates: list of (id, text). Returns the best-matching id (exact normalized match,
    then stdlib difflib fuzzy at _FUZZY_CUTOFF) or None. First candidate wins ties per norm."""
    n = _norm(name)
    if not n or not candidates:
        return None
    by_norm = {}
    for id_, text in candidates:
        nt = _norm(text)
        if nt:
            by_norm.setdefault(nt, id_)
    if n in by_norm:
        return by_norm[n]
    close = difflib.get_close_matches(n, list(by_norm.keys()), n=1, cutoff=_FUZZY_CUTOFF)
    return by_norm[close[0]] if close else None


class _HAWebSocket:
    """Thin wrapper over an authenticated HA WS connection: sends a command with an
    auto-incrementing id and returns the matching `result` message (ignoring anything else)."""

    def __init__(self, conn):
        self._conn = conn
        self._id = 0

    async def command(self, msg_type: str, **payload) -> dict:
        self._id += 1
        await self._conn.send(json.dumps({"id": self._id, "type": msg_type, **payload}))
        while True:
            raw = await asyncio.wait_for(self._conn.recv(), timeout=_WS_TIMEOUT)
            data = json.loads(raw)
            if data.get("id") == self._id and data.get("type") == "result":
                return data
            # No subscriptions are made, so anything else is noise — keep reading.


@contextlib.asynccontextmanager
async def _session():
    """Open + authenticate a HA WS connection, yield an _HAWebSocket, close on exit.
    Raises if the token is missing or auth fails; callers convert that to a spoken error."""
    if not HOME_ASSISTANT_TOKEN:
        raise RuntimeError("HOME_ASSISTANT_TOKEN not set")
    async with _ws_connect(_ws_url(), open_timeout=_WS_CONNECT_TIMEOUT, max_size=_MAX_MSG) as conn:
        await asyncio.wait_for(conn.recv(), timeout=_WS_TIMEOUT)  # auth_required
        await conn.send(json.dumps({"type": "auth", "access_token": HOME_ASSISTANT_TOKEN}))
        resp = json.loads(await asyncio.wait_for(conn.recv(), timeout=_WS_TIMEOUT))
        if resp.get("type") != "auth_ok":
            raise RuntimeError(f"HA WebSocket auth failed ({resp.get('type')})")
        yield _HAWebSocket(conn)


def _result(resp: dict) -> list:
    return resp.get("result", []) if resp.get("success") else []


def _err(resp: dict) -> str:
    e = resp.get("error") or {}
    return e.get("message") or (str(e) if e else "unknown error")


# --- resolution helpers (operate on already-fetched registry lists) -------------------

def _area_candidates(areas: list) -> list:
    out = []
    for a in areas:
        aid = a.get("area_id")
        if not aid:
            continue
        if a.get("name"):
            out.append((aid, a["name"]))
        for alias in (a.get("aliases") or []):
            out.append((aid, alias))
    return out


def _area_name(area_id, areas: list) -> str:
    return next((a.get("name") or area_id for a in areas if a.get("area_id") == area_id), area_id)


def _device_display(d: dict) -> str:
    return d.get("name_by_user") or d.get("name") or d.get("id") or ""


def _device_candidates(devices: list) -> list:
    return [(d.get("id"), _device_display(d)) for d in devices if d.get("id")]


def _device_name(device_id, devices: list) -> str:
    return next((_device_display(d) for d in devices if d.get("id") == device_id), device_id)


def _entity_display(e: dict) -> str:
    return e.get("name") or e.get("original_name") or e.get("entity_id") or ""


def _entity_candidates(entities: list) -> list:
    out = []
    for e in entities:
        eid = e.get("entity_id")
        if not eid:
            continue
        out.append((eid, _entity_display(e)))
        out.append((eid, eid))  # allow addressing by raw entity_id too
    return out


def _entity_name(entity_id, entities: list) -> str:
    return next((_entity_display(e) for e in entities if e.get("entity_id") == entity_id), entity_id)


def _device_id_for_entity(entity_id, entities: list):
    return next((e.get("device_id") for e in entities if e.get("entity_id") == entity_id), None)


# --- public operations ----------------------------------------------------------------

async def move_device_to_area(device: str = "", area: str = "", **_) -> str:
    """Move a whole DEVICE (all its entities) to an area. Device can be named directly or
    via one of its entities."""
    if not device or not area:
        return "I need both a device and a room to move it to."
    try:
        async with _session() as ws:
            areas = _result(await ws.command("config/area_registry/list"))
            devices = _result(await ws.command("config/device_registry/list"))
            area_id = _best_id(area, _area_candidates(areas))
            if not area_id:
                return f"I couldn't find a room called {area}."
            device_id = _best_id(device, _device_candidates(devices))
            if not device_id:
                # Fall back: the user may have named one of the device's entities.
                entities = _result(await ws.command("config/entity_registry/list"))
                ent_id = _best_id(device, _entity_candidates(entities))
                device_id = _device_id_for_entity(ent_id, entities) if ent_id else None
            if not device_id:
                return f"I couldn't find a device called {device}."
            res = await ws.command("config/device_registry/update",
                                   device_id=device_id, area_id=area_id)
            if not res.get("success"):
                return f"Home Assistant wouldn't move that. {_err(res)}"
            return f"Moved {_device_name(device_id, devices)} to {_area_name(area_id, areas)}."
    except Exception as e:  # noqa: BLE001
        logger.warning("move_device_to_area failed: %s", e)
        return f"I couldn't reach Home Assistant to move that ({type(e).__name__})."


async def assign_entity_to_area(entity: str = "", area: str = "", **_) -> str:
    """Assign a single ENTITY to an area, overriding its device's area."""
    if not entity or not area:
        return "I need both a thing and a room to put it in."
    try:
        async with _session() as ws:
            areas = _result(await ws.command("config/area_registry/list"))
            entities = _result(await ws.command("config/entity_registry/list"))
            area_id = _best_id(area, _area_candidates(areas))
            if not area_id:
                return f"I couldn't find a room called {area}."
            entity_id = _best_id(entity, _entity_candidates(entities))
            if not entity_id:
                return f"I couldn't find anything called {entity}."
            res = await ws.command("config/entity_registry/update",
                                   entity_id=entity_id, area_id=area_id)
            if not res.get("success"):
                return f"Home Assistant wouldn't move that. {_err(res)}"
            return f"Put {_entity_name(entity_id, entities)} in {_area_name(area_id, areas)}."
    except Exception as e:  # noqa: BLE001
        logger.warning("assign_entity_to_area failed: %s", e)
        return f"I couldn't reach Home Assistant to move that ({type(e).__name__})."


async def rename_device_or_entity(target: str = "", new_name: str = "", **_) -> str:
    """Rename a device or entity. Prefers an entity match, then a device match — an entity
    is the more specific, more commonly-named thing a person says 'rename the X' about."""
    if not target or not new_name:
        return "I need to know what to rename and what to call it."
    try:
        async with _session() as ws:
            entities = _result(await ws.command("config/entity_registry/list"))
            entity_id = _best_id(target, _entity_candidates(entities))
            if entity_id:
                res = await ws.command("config/entity_registry/update",
                                       entity_id=entity_id, name=new_name)
                if not res.get("success"):
                    return f"Home Assistant wouldn't rename that. {_err(res)}"
                return f"Renamed {_entity_name(entity_id, entities)} to {new_name}."
            devices = _result(await ws.command("config/device_registry/list"))
            device_id = _best_id(target, _device_candidates(devices))
            if device_id:
                res = await ws.command("config/device_registry/update",
                                       device_id=device_id, name_by_user=new_name)
                if not res.get("success"):
                    return f"Home Assistant wouldn't rename that. {_err(res)}"
                return f"Renamed {_device_name(device_id, devices)} to {new_name}."
            return f"I couldn't find a device or entity called {target}."
    except Exception as e:  # noqa: BLE001
        logger.warning("rename_device_or_entity failed: %s", e)
        return f"I couldn't reach Home Assistant to rename that ({type(e).__name__})."


async def create_area(name: str = "", **_) -> str:
    """Create a new area/room. No-ops with a friendly note if one already exists by that name."""
    if not name:
        return "I need a name for the new room."
    try:
        async with _session() as ws:
            areas = _result(await ws.command("config/area_registry/list"))
            # Exact (normalized) duplicate check only — NOT fuzzy _best_id, which would refuse to
            # create a legitimately-distinct room whose name is merely similar to an existing one
            # (e.g. "Bathroom 2" fuzzy-matches "Bathroom" at 0.89 and would be wrongly blocked).
            existing = {_norm(text) for _id, text in _area_candidates(areas) if text}
            if _norm(name) in existing:
                return f"There's already a room called {name}."
            res = await ws.command("config/area_registry/create", name=name)
            if not res.get("success"):
                return f"Home Assistant wouldn't create that room. {_err(res)}"
            return f"Created a new room called {name}."
    except Exception as e:  # noqa: BLE001
        logger.warning("create_area failed: %s", e)
        return f"I couldn't reach Home Assistant to create that room ({type(e).__name__})."


REGISTRY_TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "move_device_to_area", "description":
        "Move a whole smart-home DEVICE (and all its entities) to a different area/room in "
        "Home Assistant. Use for 'move the X to the Y', 'put the X device in the Y room'.",
        "parameters": {"type": "object", "properties": {
            "device": {"type": "string", "description": "device name, e.g. 'Living Room Lamp' or 'Front Porch'"},
            "area": {"type": "string", "description": "target room/area name, e.g. 'Garage', 'Upstairs'"}},
            "required": ["device", "area"]}}},
    {"type": "function", "function": {
        "name": "assign_entity_to_area", "description":
        "Assign a SINGLE entity (one light, switch, or sensor) to an area, overriding its "
        "device's area. Use when only one specific thing should change rooms, not the whole device.",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string", "description": "the entity/thing name"},
            "area": {"type": "string", "description": "target room/area name"}},
            "required": ["entity", "area"]}}},
    {"type": "function", "function": {
        "name": "rename_device_or_entity", "description":
        "Rename a device or entity in Home Assistant. Use for 'rename the X to Y', 'call the X Y instead'.",
        "parameters": {"type": "object", "properties": {
            "target": {"type": "string", "description": "the current device or entity name"},
            "new_name": {"type": "string", "description": "the new name"}},
            "required": ["target", "new_name"]}}},
    {"type": "function", "function": {
        "name": "create_area", "description":
        "Create a new area/room in Home Assistant. Use for 'make a new room called X', 'add an area named X'.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "the new room/area name"}},
            "required": ["name"]}}},
]

REGISTRY_DISPATCH = {
    "move_device_to_area": move_device_to_area,
    "assign_entity_to_area": assign_entity_to_area,
    "rename_device_or_entity": rename_device_or_entity,
    "create_area": create_area,
}
REGISTRY_TOOL_NAMES = set(REGISTRY_DISPATCH)


async def call_registry_tool(name: str, arguments: dict) -> str:
    fn = REGISTRY_DISPATCH.get(name)
    if fn is None:
        return f"Error: unknown registry tool '{name}'"
    try:
        return await fn(**(arguments or {}))
    except Exception as e:  # noqa: BLE001
        return f"Error running {name}: {e}"
