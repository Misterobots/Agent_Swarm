"""
computer_use_mcp — screenshot-grounded desktop control for Qwen Code (and any MCP client).

RUNS ON THE HOST, not in Docker: it needs the real desktop to capture and click.

Design (2026-09-13): the server calls the vision model ITSELF and returns TEXT, rather than
handing an image content block back to the CLI. Two reasons:

  1. Whether a given CLI forwards MCP image blocks through to the model is not guaranteed;
     returning text works regardless of the host's multimodal support.
  2. A screenshot costs ~1300 prompt tokens. Feeding one into the coding session on every step
     would shred the context budget of the very conversation doing the work. Grounding happens
     out-of-band and only coordinates come back.

Grounding goes through code_gateway -> Ollama -> qwen3.8:27b, measured on this hardware at
2-11 px of error on a 1440x900 UI screenshot (all three test targets landed inside their
element). That accuracy is what makes "screenshot -> place a click" viable rather than wishful.

SAFETY: locate_on_screen() never clicks. find_and_click() refuses below a confidence threshold
and instead returns instructions for the human — the deliberate fallback rather than a guess at
someone's desktop. Every action is appended to ACTION_LOG. COMPUTER_USE_DRY_RUN=1 makes every
input a no-op that still reports what it would have done.
"""

from __future__ import annotations

import base64
import ctypes
import datetime
import io
import json
import os
import re
import urllib.request
from typing import Any

from PIL import ImageGrab
# mcp SDK 2.x renamed FastMCP -> MCPServer; the @tool() decorator and run() are unchanged.
from mcp.server.mcpserver import MCPServer

GATEWAY_URL = os.getenv("COMPUTER_USE_GATEWAY", "http://localhost:8010/v1/chat/completions")
VISION_MODEL = os.getenv("COMPUTER_USE_MODEL", "qwen3.8:27b")
VISION_TIMEOUT = float(os.getenv("COMPUTER_USE_TIMEOUT", "600"))
DRY_RUN = os.getenv("COMPUTER_USE_DRY_RUN", "0").lower() in ("1", "true", "yes")
ACTION_LOG = os.getenv("COMPUTER_USE_LOG", os.path.expanduser("~/.qwen/computer_use.log"))
# Below this, find_and_click hands off to the human instead of clicking.
MIN_CONFIDENCE = float(os.getenv("COMPUTER_USE_MIN_CONFIDENCE", "0.7"))
# Downscale OURSELVES rather than letting the model do it: we then know the exact factor to
# scale coordinates back by. Deliberately well under qwen3.8's image_max_pixels of 4194304 —
# a full-size 3440x1440 grab crashed the runner on 2026-09-13, because vision tokens land on top
# of a KV slot that may already be near the window limit, and llama.cpp's context checkpoints
# (~617 MiB each, up to 32) are not budgeted against VRAM. ~1.4 MP keeps grounding accurate
# (a 3440-wide screen still maps to ~1800px) at a third of the token cost.
MAX_PIXELS = int(os.getenv("COMPUTER_USE_MAX_PIXELS", str(1_400_000)))

mcp = MCPServer("computer-use")

# Per-monitor DPI awareness. Without this Windows lies about coordinates on any scaled display:
# the screenshot comes back at physical resolution while SetCursorPos works in virtual units, so
# every click lands off-target by the scaling factor. Must run before any capture or cursor call.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:  # pragma: no cover — older Windows
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

_user32 = ctypes.windll.user32


def _log_action(kind: str, detail: dict) -> None:
    try:
        os.makedirs(os.path.dirname(ACTION_LOG), exist_ok=True)
        line = json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                           "action": kind, "dry_run": DRY_RUN, **detail})
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # logging must never break an action


def _screen_size() -> tuple[int, int]:
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)  # SM_CXSCREEN, SM_CYSCREEN


def _capture() -> tuple[bytes, int, int, float]:
    """Grab the primary screen. Returns (png_bytes, sent_w, sent_h, scale).

    `scale` is sent_size / native_size — coordinates the model returns must be divided by it to
    get back to real screen pixels.
    """
    img = ImageGrab.grab()
    native_w, native_h = img.size
    scale = 1.0
    if native_w * native_h > MAX_PIXELS:
        scale = (MAX_PIXELS / (native_w * native_h)) ** 0.5
        img = img.resize((int(native_w * scale), int(native_h * scale)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), img.size[0], img.size[1], scale


_PROMPT = """This screenshot is exactly {w} pixels wide and {h} pixels tall.

Find this element: {target}

Reply with ONLY JSON, no prose, no code fence:
{{"found": true, "x": <center x>, "y": <center y>, "confidence": <0.0-1.0>, "description": "<what you found>"}}

If you cannot find it, reply exactly:
{{"found": false, "confidence": 0.0, "description": "<what you see instead>"}}

Coordinates must be the CENTER of the element, in the {w}x{h} space, origin top-left."""


def _ask_vision(png: bytes, w: int, h: int, target: str) -> dict:
    body = {
        "model": VISION_MODEL, "stream": False, "max_tokens": 300, "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": _PROMPT.format(w=w, h=h, target=target)},
            {"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(png).decode()}},
        ]}],
    }
    req = urllib.request.Request(GATEWAY_URL, json.dumps(body).encode(),
                                 {"Content-Type": "application/json",
                                  "Authorization": "Bearer ollama"})
    with urllib.request.urlopen(req, timeout=VISION_TIMEOUT) as r:
        text = json.load(r)["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"found": False, "confidence": 0.0, "description": f"unparseable reply: {text[:200]}"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"found": False, "confidence": 0.0, "description": f"bad JSON: {m.group(0)[:200]}"}


def _locate(target: str) -> dict:
    png, w, h, scale = _capture()
    res = _ask_vision(png, w, h, target)
    if res.get("found") and "x" in res and "y" in res:
        # Scale back from the (possibly downscaled) image space to real screen pixels.
        res["x"] = int(round(res["x"] / scale))
        res["y"] = int(round(res["y"] / scale))
    res["screen_size"] = list(_screen_size())
    res.setdefault("confidence", 0.0)
    return res


# --- Tools ---------------------------------------------------------------------------------
@mcp.tool()
def screen_info() -> str:
    """Report the primary screen's pixel dimensions and whether input is in dry-run mode.

    Call this first when you need to reason about screen positions."""
    w, h = _screen_size()
    return json.dumps({"width": w, "height": h, "dry_run": DRY_RUN,
                       "vision_model": VISION_MODEL, "min_confidence": MIN_CONFIDENCE})


@mcp.tool()
def locate_on_screen(target: str) -> str:
    """Screenshot the screen and find a UI element, WITHOUT clicking anything.

    Use this to see what is on screen, or to get coordinates you will hand to the user.
    `target` is a natural-language description, e.g. "the Save button" or "the search box
    in the top toolbar".

    Returns JSON: {found, x, y, confidence, description, screen_size}. Coordinates are real
    screen pixels. This tool never moves the mouse."""
    res = _locate(target)
    _log_action("locate", {"target": target, "found": res.get("found"),
                           "x": res.get("x"), "y": res.get("y"),
                           "confidence": res.get("confidence")})
    return json.dumps(res)


@mcp.tool()
def click(x: int, y: int, button: str = "left", double: bool = False) -> str:
    """Click at explicit screen coordinates. Prefer find_and_click unless you already have
    verified coordinates — this performs the click with no confidence check of its own."""
    w, h = _screen_size()
    if not (0 <= x < w and 0 <= y < h):
        return json.dumps({"ok": False, "error": f"({x},{y}) is outside the {w}x{h} screen"})
    _log_action("click", {"x": x, "y": y, "button": button, "double": double})
    if DRY_RUN:
        return json.dumps({"ok": True, "dry_run": True,
                           "would_click": {"x": x, "y": y, "button": button, "double": double}})
    down, up = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
                "middle": (0x0020, 0x0040)}.get(button, (0x0002, 0x0004))
    _user32.SetCursorPos(int(x), int(y))
    for _ in range(2 if double else 1):
        _user32.mouse_event(down, 0, 0, 0, 0)
        _user32.mouse_event(up, 0, 0, 0, 0)
    return json.dumps({"ok": True, "clicked": {"x": x, "y": y, "button": button, "double": double}})


@mcp.tool()
def find_and_click(target: str, button: str = "left", double: bool = False) -> str:
    """Locate a UI element by description and click it — but ONLY if the match is confident.

    Below the confidence threshold this deliberately does NOT click. It returns
    needs_human=true plus the coordinates and what it saw, so you can ask the user to do it
    instead. Guessing at someone's desktop is worse than handing off."""
    res = _locate(target)
    conf = float(res.get("confidence") or 0.0)

    if not res.get("found"):
        _log_action("find_and_click:not_found", {"target": target, "description": res.get("description")})
        return json.dumps({"ok": False, "clicked": False, "needs_human": True, "target": target,
                           "reason": "element not found",
                           "saw": res.get("description"), "screen_size": res["screen_size"]})

    if conf < MIN_CONFIDENCE:
        _log_action("find_and_click:low_confidence",
                    {"target": target, "x": res.get("x"), "y": res.get("y"), "confidence": conf})
        return json.dumps({
            "ok": True, "clicked": False, "needs_human": True, "target": target,
            "confidence": conf, "x": res["x"], "y": res["y"],
            "reason": f"confidence {conf:.2f} is below the {MIN_CONFIDENCE} threshold",
            "instruct_user": f"Please click {res.get('description') or target} "
                             f"at approximately ({res['x']}, {res['y']}).",
        })

    result = json.loads(click(res["x"], res["y"], button=button, double=double))
    return json.dumps({"ok": result.get("ok", False), "clicked": not DRY_RUN, "dry_run": DRY_RUN,
                       "target": target, "x": res["x"], "y": res["y"], "confidence": conf,
                       "description": res.get("description")})


@mcp.tool()
def type_text(text: str) -> str:
    """Type text at the current focus, via synthetic unicode keystrokes.

    Click the target field first — this types wherever focus already is."""
    _log_action("type_text", {"length": len(text)})
    if DRY_RUN:
        return json.dumps({"ok": True, "dry_run": True, "would_type_chars": len(text)})

    # KEYEVENTF_UNICODE carries the character directly, so this handles any character without
    # depending on the active keyboard layout (which VkKeyScan-based approaches do not).
    class _KbdInput(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _InputUnion(ctypes.Union):
        _fields_ = [("ki", _KbdInput), ("_pad", ctypes.c_byte * 24)]

    class _Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("u", _InputUnion)]

    KEYEVENTF_UNICODE, KEYEVENTF_KEYUP, INPUT_KEYBOARD = 0x0004, 0x0002, 1
    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = _Input(type=INPUT_KEYBOARD,
                         u=_InputUnion(ki=_KbdInput(0, ord(ch), flags, 0, None)))
            _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_Input))
    return json.dumps({"ok": True, "typed_chars": len(text)})


if __name__ == "__main__":
    mcp.run()
