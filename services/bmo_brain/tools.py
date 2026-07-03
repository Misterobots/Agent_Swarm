"""Tools bmo_brain executes itself for callers that don't supply their own `tools`
array (the "self-executing" mode — see main.py's module docstring). Ported from
agents/tools/*.py, reimplemented standalone (async, no phi dependency) since
bmo_brain's Dockerfile only COPYs services/bmo_brain/ and can't cross-import the
agents/ package tree.

web_search is a deliberately simpler DuckDuckGo-only implementation than the
agents/tools/web_browser.py original (no Google CSE fallback, no content-trust
scanning) — the trade-off is a smaller dependency footprint for this microservice.
"""
import os
import xml.etree.ElementTree as ET

import httpx

HOME_ASSISTANT_URL   = os.getenv("HOME_ASSISTANT_URL", "http://192.168.2.100:8123").rstrip("/")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
HOME_LAT  = os.getenv("HOME_LAT", "41.8781")
HOME_LON  = os.getenv("HOME_LON", "-87.6298")
HOME_CITY = os.getenv("HOME_CITY", "your area")

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


async def get_current_time(**_kwargs) -> str:
    import datetime
    return datetime.datetime.now().strftime("%-I:%M %p")


async def get_current_date(**_kwargs) -> str:
    import datetime
    return datetime.datetime.now().strftime("%A, %B %-d, %Y")


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
]

_DISPATCH = {
    "get_current_weather": get_current_weather,
    "get_weather_forecast": get_weather_forecast,
    "get_current_time": get_current_time,
    "get_current_date": get_current_date,
    "get_news_headlines": get_news_headlines,
    "web_search": web_search,
    "turn_on_device": turn_on_device,
    "turn_off_device": turn_off_device,
    "get_device_state": get_device_state,
    "list_devices": list_devices,
}


async def call_tool(name: str, arguments: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return await fn(**(arguments or {}))
    except Exception as e:  # noqa: BLE001
        return f"Error running {name}: {e}"
