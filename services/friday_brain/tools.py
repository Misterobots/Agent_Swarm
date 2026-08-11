"""Tools bmo_brain executes itself for callers that don't supply their own `tools`
array (the "self-executing" mode — see main.py's module docstring). Ported from
agents/tools/*.py, reimplemented standalone (async, no phi dependency) since
bmo_brain's Dockerfile only COPYs services/bmo_brain/ and can't cross-import the
agents/ package tree.

web_search is a deliberately simpler DuckDuckGo-only implementation than the
agents/tools/web_browser.py original (no Google CSE fallback, no content-trust
scanning) — the trade-off is a smaller dependency footprint for this microservice.
"""
import contextvars
import difflib
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx

from ha_registry import REGISTRY_DISPATCH

HOME_ASSISTANT_URL   = os.getenv("HOME_ASSISTANT_URL", "http://192.168.2.100:8123").rstrip("/")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
HOME_LAT  = os.getenv("HOME_LAT", "41.8781")
HOME_LON  = os.getenv("HOME_LON", "-87.6298")
HOME_CITY = os.getenv("HOME_CITY", "your area")

# Agent swarm (agent_runtime) — heavy multi-step delegation target.
# Set AGENT_RUNTIME_URL in the service env to agent_runtime's real base URL (NOT bmo_brain's :8000).
AGENT_RUNTIME_URL = os.getenv("AGENT_RUNTIME_URL", "").rstrip("/")
_SWARM_TIMEOUT = float(os.getenv("SWARM_TIMEOUT", "90"))  # swarm runs longer than local tools

_HTTP_TIMEOUT = 8.0


def _weather_code_to_text(code: int) -> str:
    if code == 0: return "Clear skies"
    if code in (1, 2, 3): return "Partly cloudy"
    if code in (45, 48): return "Foggy"
    if code in (51, 53, 55): return "Drizzling"
    if code in (61, 63, 65): return "Rainy"
    if code in (71, 73, 75, 77): return "Snowy"
    if code in (80, 81, 82): return "Rain showers"
    if code in (85, 86): return "Snow showers"
    if code in (95, 96, 99): return "Thunderstorm"
    return "Cloudy"


async def get_current_weather(**_kwargs) -> str:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={HOME_LAT}&longitude={HOME_LON}"
            "&current=temperature_2m,apparent_temperature,precipitation,weathercode,windspeed_10m"
            "&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=auto"
        )
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
            r = await c.get(url)
        data = r.json().get("current", {})
        temp = data.get("temperature_2m", "?")
        feels = data.get("apparent_temperature", "?")
        wind = data.get("windspeed_10m", "?")
        precip = data.get("precipitation", 0)
        condition = _weather_code_to_text(data.get("weathercode", 0))
        result = f"{condition}, {temp}°F (feels like {feels}°F), wind {wind} mph"
        if precip:
            result += f", {precip}mm precipitation"
        return result
    except Exception as e:  # noqa: BLE001
        return f"Weather is unreachable right now ({type(e).__name__})."


async def get_weather_forecast(**_kwargs) -> str:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={HOME_LAT}&longitude={HOME_LON}"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum"
            "&temperature_unit=fahrenheit&timezone=auto&forecast_days=2"
        )
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
            r = await c.get(url)
        daily = r.json().get("daily", {})
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        codes = daily.get("weathercode", [])
        precips = daily.get("precipitation_sum", [])
        labels = ["Today", "Tomorrow"]
        days = []
        for i in range(min(2, len(dates))):
            cond = _weather_code_to_text(codes[i] if i < len(codes) else 0)
            rain = f", {precips[i]}mm rain" if i < len(precips) and precips[i] else ""
            days.append(f"{labels[i]}: {cond}, {lows[i]}–{highs[i]}°F{rain}")
        return " | ".join(days) if days else "No forecast available."
    except Exception as e:  # noqa: BLE001
        return f"Forecast is unreachable right now ({type(e).__name__})."


async def get_hourly_forecast(**_kwargs) -> str:
    """Today's hourly temperature curve — for 'hottest/coolest part of the day', 'when will it
    peak / warm up'. Returns the peak and dip hour + temp so Friday answers with real numbers."""
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={HOME_LAT}&longitude={HOME_LON}"
            "&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=auto&forecast_days=1"
        )
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
            r = await c.get(url)
        h = r.json().get("hourly", {})
        pairs = [(t, temp) for t, temp in zip(h.get("time", []), h.get("temperature_2m", []))
                 if temp is not None]
        if not pairs:
            return "The hourly forecast is unavailable right now."
        import datetime as _dt

        def _fmt(iso):
            try:
                return _dt.datetime.fromisoformat(iso).strftime("%-I %p")
            except Exception:
                return iso
        hot_t, hot = max(pairs, key=lambda p: p[1])
        cold_t, cold = min(pairs, key=lambda p: p[1])
        return (f"Today peaks around {_fmt(hot_t)} at {round(hot)}°F, "
                f"and is coolest around {_fmt(cold_t)} at {round(cold)}°F.")
    except Exception as e:  # noqa: BLE001
        return f"The hourly forecast is unreachable right now ({type(e).__name__})."


def _tz_now():
    """Local time. The container has no TZ set, so a bare datetime.now() is UTC (~5h off). Resolve
    through FRIDAY_TZ (IANA name, e.g. America/Chicago) via zoneinfo; fall back to system time."""
    import datetime, os
    tz = os.getenv("FRIDAY_TZ")
    if tz:
        try:
            from zoneinfo import ZoneInfo
            return datetime.datetime.now(ZoneInfo(tz))
        except Exception:  # noqa: BLE001
            pass
    return datetime.datetime.now()


async def get_current_time(**_kwargs) -> str:
    return _tz_now().strftime("%-I:%M %p")


async def get_current_date(**_kwargs) -> str:
    return _tz_now().strftime("%A, %B %-d, %Y")


_NEWS_FEEDS = {
    "general": "https://feeds.bbci.co.uk/news/rss.xml",
    "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "sports": "https://feeds.bbci.co.uk/sport/rss.xml",
    "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "health": "https://feeds.bbci.co.uk/news/health/rss.xml",
}


async def get_news_headlines(topic: str = "general", **_kwargs) -> str:
    url = _NEWS_FEEDS.get((topic or "general").lower(), _NEWS_FEEDS["general"])
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        headlines = [t.strip() for t in (item.findtext("title", "") for item in root.findall(".//item")[:3]) if t.strip()]
        return " | ".join(headlines) if headlines else "No headlines found."
    except Exception as e:  # noqa: BLE001
        return f"News is unreachable right now ({type(e).__name__})."


async def web_search(query: str, **_kwargs) -> str:
    """DuckDuckGo HTML-lite search — no API key, no extra dependencies."""
    if not query:
        return "No search query given."
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as c:
            r = await c.post("https://html.duckduckgo.com/html/", data={"q": query},
                              headers={"User-Agent": "Mozilla/5.0"})
        import re as _re
        titles = _re.findall(r'class="result__a"[^>]*>(.*?)</a>', r.text, _re.DOTALL)
        snippets = _re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, _re.DOTALL)
        def _clean(s):
            return _re.sub(r"<[^>]+>", "", s).strip()
        lines = []
        for title, snippet in zip(titles[:4], snippets[:4]):
            title, snippet = _clean(title), _clean(snippet)
            if title or snippet:
                lines.append(f"{title}: {snippet}" if title else snippet)
        return "\n".join(lines) if lines else "No results found."
    except Exception as e:  # noqa: BLE001
        return f"Search is unreachable right now ({type(e).__name__})."


async def delegate_to_swarm(task: str, mode: str = "auto", **_kwargs) -> str:
    """Hand a HEAVY multi-step task (deep research, building/writing something substantial,
    complex analysis) to the agent swarm via agent_runtime's OpenAI-compatible endpoint.

    Synchronous: blocks until the swarm answers, so Friday warns the user it may take a moment
    before this is called (enforced by the persona rules). Returns the final text only.

    Requires AGENT_RUNTIME_URL to be set to agent_runtime's base URL — inert until then."""
    if not task:
        return "No task was given to hand off."
    if not AGENT_RUNTIME_URL:
        return "The swarm is not reachable — its endpoint is not configured yet."
    flags = {
        "research": {"research_mode": True, "skill": "research"},
        "build":    {"swarm_mode": True, "skill": "code"},
        "plan":     {"ultraplan_mode": True},
        # 'auto' sends NO mode flag, so agent_runtime's neural router reasons about the (clarified)
        # task and picks the depth itself instead of Friday hard-forcing deep-research on everything.
        "auto":     {},
    }.get((mode or "auto").lower(), {})
    payload = {"model": "default", "stream": False,
               "messages": [{"role": "user", "content": task}], **flags}
    try:
        async with httpx.AsyncClient(timeout=_SWARM_TIMEOUT) as c:
            r = await c.post(f"{AGENT_RUNTIME_URL}/v1/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "The swarm is still working on that one — it is taking longer than expected."
    except Exception as e:  # noqa: BLE001
        return f"Could not reach the swarm right now ({type(e).__name__})."


async def _ha_call(method: str, path: str, json_body: dict | None = None) -> dict:
    url = f"{HOME_ASSISTANT_URL}/api/{path}"
    headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
        r = await c.request(method, url, headers=headers, json=json_body)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    return r.json()


async def turn_on_device(entity_id: str, **_kwargs) -> str:
    domain = entity_id.split(".")[0]
    result = await _ha_call("POST", f"services/{domain}/turn_on", {"entity_id": entity_id})
    return f"Error: {result['error']}" if "error" in result else f"Turned on {entity_id}"


async def turn_off_device(entity_id: str, **_kwargs) -> str:
    domain = entity_id.split(".")[0]
    result = await _ha_call("POST", f"services/{domain}/turn_off", {"entity_id": entity_id})
    return f"Error: {result['error']}" if "error" in result else f"Turned off {entity_id}"


async def get_device_state(entity_id: str, **_kwargs) -> str:
    result = await _ha_call("GET", f"states/{entity_id}")
    if "error" in result:
        return f"Error: {result['error']}"
    state = result.get("state", "unknown")
    attrs = result.get("attributes", {})
    name = attrs.get("friendly_name", entity_id)
    unit = attrs.get("unit_of_measurement", "")
    return f"{name} is {state} {unit}".strip()


async def list_devices(**_kwargs) -> str:
    result = await _ha_call("GET", "states")
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    if isinstance(result, list):
        lines = [f"- {e.get('attributes', {}).get('friendly_name', e.get('entity_id', ''))} "
                 f"({e.get('entity_id', '')}): {e.get('state', '?')}" for e in result[:30]]
        return "\n".join(lines) if lines else "No devices found"
    return "Could not list devices"


# --- Media playback (HA media_player domain) --------------------------------------------------
# Transport + volume control work on any media_player entity. play_media casts a direct stream URL
# or a named internet-radio station (_STATIONS: SomaFM defaults, extendable via the
# FRIDAY_RADIO_STATIONS JSON env var). Resolving an arbitrary song/artist BY NAME needs a music
# provider (Music Assistant / Spotify) on the HA side — none is installed here — so play_media is
# stream/URL based by design.
_DEFAULT_STATIONS = {
    "groove salad": "https://ice1.somafm.com/groovesalad-128-mp3",
    "chill":        "https://ice1.somafm.com/groovesalad-128-mp3",
    "ambient":      "https://ice1.somafm.com/dronezone-128-mp3",
    "drone zone":   "https://ice1.somafm.com/dronezone-128-mp3",
    "indie":        "https://ice1.somafm.com/indiepop-128-mp3",
    "indie pop":    "https://ice1.somafm.com/indiepop-128-mp3",
    "jazz":         "https://ice1.somafm.com/sonicuniverse-128-mp3",
    "lounge":       "https://ice1.somafm.com/secretagent-128-mp3",
    "80s":          "https://ice1.somafm.com/u80s-128-mp3",
    "eighties":     "https://ice1.somafm.com/u80s-128-mp3",
}
try:
    _STATIONS = {**_DEFAULT_STATIONS, **json.loads(os.getenv("FRIDAY_RADIO_STATIONS", "") or "{}")}
except Exception:  # noqa: BLE001 — a malformed override must never break tool loading
    _STATIONS = dict(_DEFAULT_STATIONS)

_MEDIA_SERVICE = {
    "play": "media_play", "resume": "media_play", "unpause": "media_play",
    "pause": "media_pause",
    "stop": "media_stop",
    "next": "media_next_track", "skip": "media_next_track",
    "previous": "media_previous_track", "back": "media_previous_track",
    "volume_up": "volume_up", "louder": "volume_up",
    "volume_down": "volume_down", "quieter": "volume_down",
    "mute": "volume_mute", "unmute": "volume_mute",
}


def _ha_service_ok(result) -> bool:
    """HA service calls return a JSON list of changed states on success; _ha_call returns a
    {"error": ...} dict on a non-200. Success = anything that isn't that error dict."""
    return not (isinstance(result, dict) and "error" in result)


# --- Media entity resolution ladder: exact -> room/substring -> difflib fuzzy -> clarify -------
# Small models fumble exact entity_ids ('media_player.office' vs 'media_player.office_speaker').
# resolve_media_player() forgives that locally (no LLM, no extra network beyond a short-TTL cached
# /states): a confident single hit is used silently; anything ambiguous returns candidates so the
# caller can ask. MEDIA_SEARCH_SENTINEL is play_media's signal that the SOURCE (not the speaker)
# couldn't be resolved locally — main.py turns that into the swarm-search fallback.
MEDIA_SEARCH_SENTINEL = "\x00MEDIA_SEARCH\x00"
_media_players_cache = {"list": [], "ts": 0.0}
_MEDIA_PLAYERS_TTL = 120.0
_MEDIA_STOPWORDS = frozenset({"the", "a", "an", "in", "on", "to", "my", "our", "please",
                              "speaker", "speakers", "player", "media", "device", "tv"})


def _norm_media(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


# --- Node identity: which physical satellite+speaker issued this request ----------------------
# HA's chat request carries no device_id (see main.py's ANNOUNCE_TARGET note) — the only per-turn
# signal available today is the caller-chosen `model` string that reaches _answer(), since HA lets
# you register a SEPARATE Ollama-conversation-agent entry per Assist pipeline, each pointed at this
# same brain but naming a distinct model (advertised via /api/tags, see main.py). NODE_SPEAKER_MAP
# maps that model string (tag stripped, e.g. "friday-library" not "friday-library:latest") to the
# media_player entity_id co-located with that node, so a bare "volume up"/"turn it up" with no room
# named defaults to the node's own speaker instead of clarifying. Configured via FRIDAY_NODE_SPEAKERS
# (JSON object). Empty/unset (the default, and every caller that isn't a registered node) = no
# behavior change — falls through to the existing clarify path exactly as before.
try:
    NODE_SPEAKER_MAP = json.loads(os.getenv("FRIDAY_NODE_SPEAKERS", "") or "{}")
except Exception:  # noqa: BLE001 — a malformed override must never break tool loading
    NODE_SPEAKER_MAP = {}

_current_node: "contextvars.ContextVar[str]" = contextvars.ContextVar("_current_node", default="")


def set_current_node(node: str) -> None:
    """Called once per request (main.py's _answer) with the caller-identified node/model string.
    A no-op for any caller whose model string isn't a key in NODE_SPEAKER_MAP — existing callers
    (the Pi driver, the default 'bmo'/'friday' model) are unaffected."""
    _current_node.set((node or "").split(":", 1)[0])


def _node_default_speaker(players: list) -> str | None:
    """This request's node-default media_player, if one is configured AND still a real player."""
    default = NODE_SPEAKER_MAP.get(_current_node.get())
    if default and default in {eid for eid, _ in players}:
        return default
    return None


def current_node_speaker() -> str | None:
    """This request's configured node-default media_player entity_id, if any — unvalidated
    against the live player list (unlike _node_default_speaker), since this is for PROMPT
    HINTS only (main.py's state-fallback nudge), not a value used directly in a tool call."""
    return NODE_SPEAKER_MAP.get(_current_node.get()) or None


async def list_media_players() -> list:
    """[(entity_id, friendly_name)] for every media_player entity — short-TTL cached so the resolver
    and the prompt-context injection share one HA /states call."""
    now = time.time()
    if _media_players_cache["list"] and (now - _media_players_cache["ts"]) < _MEDIA_PLAYERS_TTL:
        return _media_players_cache["list"]
    states = await _ha_call("GET", "states")
    if isinstance(states, list):
        players = [(e.get("entity_id", ""),
                    (e.get("attributes", {}) or {}).get("friendly_name", "") or e.get("entity_id", ""))
                   for e in states if e.get("entity_id", "").startswith("media_player.")]
        _media_players_cache["list"] = players
        _media_players_cache["ts"] = now
        return players
    return _media_players_cache["list"]


async def resolve_media_player(target: str):
    """(entity_id | None, candidates). entity_id is set ONLY on a confident single match (exact id,
    a room/substring hit, or a clear difflib winner >= 0.8); otherwise None plus a candidate list
    for a spoken clarify."""
    want = (target or "").strip()
    players = await list_media_players()
    if not players:
        return None, []
    if want in {eid for eid, _ in players}:
        return want, players
    nwant = _norm_media(want)
    if not nwant:
        # No usable target phrase at all — a bare "volume up"/"pause" with no room/speaker named.
        # This is exactly the case that used to always clarify; a known node default resolves it
        # silently instead. No default configured -> unchanged (clarify with the full list).
        node_default = _node_default_speaker(players)
        return (node_default, players) if node_default else (None, players)
    toks = [t for t in nwant.split() if t not in _MEDIA_STOPWORDS]
    scored = []
    for eid, fn in players:
        hay = _norm_media(eid.split(".", 1)[-1].replace("_", " ")) + " " + _norm_media(fn)
        if nwant in hay:
            score = 1.0
        elif toks and all(t in hay for t in toks):
            score = 0.95
        else:
            score = difflib.SequenceMatcher(None, nwant, _norm_media(fn)).ratio()
        scored.append((eid, fn, score))
    scored.sort(key=lambda x: -x[2])
    best = scored[0]
    runner = scored[1][2] if len(scored) > 1 else 0.0
    if best[2] >= 0.8 and (best[2] - runner) >= 0.1:
        return best[0], players
    close = [(eid, fn) for eid, fn, sc in scored if sc >= 0.55]
    if not close:
        # The phrase (e.g. "the speaker", stripped to nothing but stopwords) didn't even loosely
        # match anything real — same dead-end as the empty-phrase case above.
        node_default = _node_default_speaker(players)
        if node_default:
            return node_default, players
    return None, (close or players)


def _media_clarify(candidates: list) -> str:
    names = [fn for _, fn in candidates][:6]
    if not names:
        return "I couldn't find any speakers to control. Which device did you mean?"
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
    return f"I couldn't tell which one you meant. I can use the {listed}. Which should I use?"


async def control_media(entity_id: str, action: str, **_kwargs) -> str:
    """Transport + volume control on a media_player: play/resume, pause, stop, next, previous,
    volume_up, volume_down, mute, unmute."""
    act = (action or "").lower().strip()
    svc = _MEDIA_SERVICE.get(act)
    if not svc:
        return (f"Error: unknown media action '{action}'. Use play, pause, stop, next, previous, "
                "volume_up, volume_down, mute, or unmute.")
    eid, candidates = await resolve_media_player(entity_id)
    if not eid:
        return _media_clarify(candidates)
    body = {"entity_id": eid}
    if svc == "volume_mute":
        body["is_volume_muted"] = act != "unmute"
    result = await _ha_call("POST", f"services/media_player/{svc}", body)
    if not _ha_service_ok(result):
        return f"Error: {result['error']}"
    return f"Done: {act} on {eid}"


async def set_volume(entity_id: str, level=None, volume=None, **_kwargs) -> str:
    """Set a media_player's volume. Accepts 0-100 (percent) or 0-1 (fraction)."""
    raw = level if level is not None else volume
    try:
        lvl = float(raw)
    except (TypeError, ValueError):
        return "Error: volume must be a number from zero to one hundred."
    if lvl > 1:
        lvl /= 100.0
    lvl = max(0.0, min(1.0, lvl))
    eid, candidates = await resolve_media_player(entity_id)
    if not eid:
        return _media_clarify(candidates)
    result = await _ha_call("POST", "services/media_player/volume_set",
                            {"entity_id": eid, "volume_level": lvl})
    if not _ha_service_ok(result):
        return f"Error: {result['error']}"
    return f"Set {eid} to {round(lvl * 100)} percent volume"


async def adjust_volume(entity_id: str, direction: str, amount=1, **_kwargs) -> str:
    """Adjust a media player's current volume by an exact number of percentage points."""
    eid, candidates = await resolve_media_player(entity_id)
    if not eid:
        return _media_clarify(candidates)
    state = await _ha_call("GET", f"states/{eid}")
    if "error" in state:
        return f"Error: {state['error']}"
    current = (state.get("attributes") or {}).get("volume_level")
    try:
        delta = abs(float(amount)) / 100.0
        current = float(current)
    except (TypeError, ValueError):
        return "Error: the current volume or requested adjustment is unavailable."
    if (direction or "").lower() == "down":
        delta = -delta
    elif (direction or "").lower() != "up":
        return "Error: volume direction must be up or down."
    target = max(0.0, min(1.0, current + delta))
    result = await _ha_call("POST", "services/media_player/volume_set",
                            {"entity_id": eid, "volume_level": target})
    if not _ha_service_ok(result):
        return f"Error: {result['error']}"
    return f"Adjusted {eid} {direction} by {round(abs(delta) * 100)} percent"


async def play_media(entity_id: str, source: str = "", url: str = "", query: str = "",
                     media_type: str = "music", **_kwargs) -> str:
    """Start audio on a media_player from a direct stream URL or a known station name (_STATIONS).
    Not a by-name song lookup (no music provider installed) — streams/URLs only."""
    eid, candidates = await resolve_media_player(entity_id)
    if not eid:
        return _media_clarify(candidates)
    want = (source or url or query or "").strip()
    key = want.lower()
    if want.startswith(("http://", "https://")):
        media_url = want
    elif key in _STATIONS:
        media_url = _STATIONS[key]
    else:
        media_url = next((u for name, u in _STATIONS.items() if name in key), "")
        if not media_url and any(w in key for w in
                                 ("music", "song", "tune", "something", "anything", "radio", "playlist")):
            media_url = _STATIONS.get("groove salad") or next(iter(_STATIONS.values()), "")
    if not media_url:
        # Tier 3 (music): source isn't a known station/URL. Signal main.py to engage the swarm to
        # hunt a stream. On the self-exec/Pi path (no sentinel handling) this degrades to a plain
        # spoken message — see _self_execute_tools / _passthrough_with_media.
        return MEDIA_SEARCH_SENTINEL + json.dumps({"entity_id": eid, "source": want})
    result = await _ha_call("POST", "services/media_player/play_media",
                            {"entity_id": eid, "media_content_id": media_url,
                             "media_content_type": media_type or "music"})
    if not _ha_service_ok(result):
        return f"Error: {result['error']}"
    return f"Playing on {eid}"


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_current_weather", "description":
        "Get the current weather conditions and temperature. Use for 'what's the weather like?' or 'is it hot outside?'",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_weather_forecast", "description":
        "Get the weather forecast for today and tomorrow. Use for 'will it rain today?' or 'weather tomorrow?'",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_hourly_forecast", "description":
        "Today's hour-by-hour temperature — the peak and coolest times. Use for 'hottest part of the "
        "day?', 'when will it be warmest/coolest?', 'when does it peak?'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_current_time", "description": "Get the current time. Use for 'what time is it?'",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_current_date", "description": "Get today's date and day of week. Use for 'what day is it?'",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_news_headlines", "description":
        "Get top news headlines. Use for 'what's in the news?' or 'any news about X?'",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "general, technology, sports, science, or health"}}}}},
    {"type": "function", "function": {
        "name": "web_search", "description":
        "Search the web for real-time info: store hours, prices, facts, events. Use whenever you don't know "
        "something or it may have changed. ALWAYS call this before saying you don't know a real-world fact.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "the search query"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "turn_on_device", "description":
        "Turn ON a smart home device. Use for 'turn on/enable/activate X'.",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description": "e.g. 'light.bedroom' or 'switch.fan'"}},
            "required": ["entity_id"]}}},
    {"type": "function", "function": {
        "name": "turn_off_device", "description":
        "Turn OFF a smart home device. Use for 'turn off/disable/deactivate X'.",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description": "e.g. 'light.bedroom' or 'switch.fan'"}},
            "required": ["entity_id"]}}},
    {"type": "function", "function": {
        "name": "get_device_state", "description":
        "Get the current state of a smart home device or sensor. Use for 'what's the temperature?' or 'are the lights on?'",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description": "e.g. 'sensor.temperature', 'light.bedroom'"}},
            "required": ["entity_id"]}}},
    {"type": "function", "function": {
        "name": "list_devices", "description":
        "List available smart home devices. Use when the user asks what devices exist or you need to discover an entity_id.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "control_media", "description":
        "Control playback on a speaker or media player: play/resume, pause, stop, next, previous, "
        "volume_up, volume_down, mute, unmute. Use for 'pause the living room speaker', 'skip this "
        "song', 'turn it up', 'resume the music', 'mute the kitchen'.",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description":
                "media_player entity, e.g. 'media_player.living_room_speaker' or 'media_player.kitchen_display'"},
            "action": {"type": "string", "description":
                "play, pause, stop, next, previous, volume_up, volume_down, mute, or unmute"}},
            "required": ["entity_id", "action"]}}},
    {"type": "function", "function": {
        "name": "set_volume", "description":
        "Set a speaker/media player's volume to a specific level. Use for 'set the kitchen volume to "
        "forty percent' or 'make the living room half volume'.",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description":
                "media_player entity, e.g. 'media_player.kitchen_display'"},
            "level": {"type": "number", "description": "volume 0-100 (percent) or 0-1 (fraction)"}},
            "required": ["entity_id", "level"]}}},
    {"type": "function", "function": {
        "name": "play_media", "description":
        "Start audio on a speaker from an internet-radio station name or a direct stream URL. Use for "
        "'play some jazz in the living room' or 'put on the chill station in the kitchen'. NOTE: this "
        "plays radio streams, NOT specific songs/artists by name (no music service is set up).",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description": "media_player entity to play on"},
            "source": {"type": "string", "description":
                "a station name (e.g. 'jazz', 'chill', 'indie', '80s') or a direct stream URL"}},
            "required": ["entity_id", "source"]}}},
    {"type": "function", "function": {
        "name": "delegate_to_swarm", "description":
        "Hand off a HEAVY, multi-step task to the agent swarm: deep research, building or writing "
        "something substantial, or complex analysis. Do NOT use for quick facts (use web_search) "
        "or device control. Before calling, tell the user in one short line that you are handing it "
        "to the swarm and it may take a moment. "
        "mode: 'research' = investigate or find out, 'build' = make/write/code, 'plan' = decompose only.",
        "parameters": {"type": "object", "properties": {
            "task": {"type": "string", "description": "full, self-contained description of the task"},
            "mode": {"type": "string", "description": "research | build | plan"}},
            "required": ["task"]}}},
]

_DISPATCH = {
    "get_current_weather": get_current_weather,
    "get_weather_forecast": get_weather_forecast,
    "get_hourly_forecast": get_hourly_forecast,
    "get_current_time": get_current_time,
    "get_current_date": get_current_date,
    "get_news_headlines": get_news_headlines,
    "web_search": web_search,
    "turn_on_device": turn_on_device,
    "turn_off_device": turn_off_device,
    "get_device_state": get_device_state,
    "list_devices": list_devices,
    "control_media": control_media,
    "set_volume": set_volume,
    "adjust_volume": adjust_volume,
    "play_media": play_media,
    "delegate_to_swarm": delegate_to_swarm,
}

# HA registry editing (move device -> area, assign entity -> area, rename, create area) lives in
# ha_registry.py (WebSocket-based, unlike these REST tools). Register the DISPATCH so call_tool
# can EXECUTE them, but do NOT fold their schemas into TOOL_SCHEMAS: these are irreversible WRITES,
# so main.py's _answer decides per-turn whether to OFFER them (gated behind the registry-intent
# regex, on both the passthrough and self-executing paths) rather than exposing them to the model
# on every turn.
_DISPATCH.update(REGISTRY_DISPATCH)


async def call_tool(name: str, arguments: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return await fn(**(arguments or {}))
    except Exception as e:  # noqa: BLE001
        return f"Error running {name}: {e}"
