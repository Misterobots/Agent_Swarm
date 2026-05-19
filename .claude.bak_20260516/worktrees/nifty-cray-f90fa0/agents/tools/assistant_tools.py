"""
BMO Smart Assistant Tools
Provides weather, time, and news capabilities using free APIs (no key required).
"""
import os
import logging
import requests
from datetime import datetime
from phi.tools import Toolkit

logger = logging.getLogger("AssistantTools")

# Location config — can be overridden via env vars
DEFAULT_LAT = os.getenv("HOME_LAT", "41.8781")   # Default: Chicago
DEFAULT_LON = os.getenv("HOME_LON", "-87.6298")
DEFAULT_CITY = os.getenv("HOME_CITY", "your area")


class WeatherTool(Toolkit):
    """Weather via Open-Meteo (free, no API key needed)."""

    def __init__(self):
        super().__init__(name="weather")
        self.lat = DEFAULT_LAT
        self.lon = DEFAULT_LON
        self.city = DEFAULT_CITY
        self.register(self.get_current_weather)
        self.register(self.get_forecast)

    def get_current_weather(self, **kwargs) -> str:
        """Get the current weather conditions and temperature.
        Use this when the user asks 'what's the weather like?' or 'is it hot outside?'"""
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={self.lat}&longitude={self.lon}"
                f"&current=temperature_2m,apparent_temperature,precipitation,weathercode,windspeed_10m"
                f"&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=auto"
            )
            r = requests.get(url, timeout=5)
            data = r.json().get("current", {})

            temp = data.get("temperature_2m", "?")
            feels = data.get("apparent_temperature", "?")
            wind = data.get("windspeed_10m", "?")
            code = data.get("weathercode", 0)
            precip = data.get("precipitation", 0)

            condition = _weather_code_to_text(code)
            result = f"{condition}, {temp}°F (feels like {feels}°F), wind {wind} mph"
            if precip > 0:
                result += f", {precip}mm precipitation"
            return result
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")
            return "I couldn't get the weather right now."

    def get_forecast(self, **kwargs) -> str:
        """Get the weather forecast for today and tomorrow.
        Use this when the user asks 'will it rain today?' or 'what's the weather tomorrow?'"""
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={self.lat}&longitude={self.lon}"
                f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum"
                f"&temperature_unit=fahrenheit&timezone=auto&forecast_days=2"
            )
            r = requests.get(url, timeout=5)
            daily = r.json().get("daily", {})
            dates = daily.get("time", [])
            highs = daily.get("temperature_2m_max", [])
            lows = daily.get("temperature_2m_min", [])
            codes = daily.get("weathercode", [])
            precips = daily.get("precipitation_sum", [])

            days = []
            labels = ["Today", "Tomorrow"]
            for i in range(min(2, len(dates))):
                cond = _weather_code_to_text(codes[i] if i < len(codes) else 0)
                high = highs[i] if i < len(highs) else "?"
                low = lows[i] if i < len(lows) else "?"
                precip = precips[i] if i < len(precips) else 0
                rain = f", {precip}mm rain" if precip > 0 else ""
                days.append(f"{labels[i]}: {cond}, {low}–{high}°F{rain}")

            return " | ".join(days) if days else "No forecast available."
        except Exception as e:
            logger.error(f"Forecast fetch failed: {e}")
            return "I couldn't get the forecast right now."


class TimeTool(Toolkit):
    """Provides current time and date."""

    def __init__(self):
        super().__init__(name="time")
        self.register(self.get_current_time)
        self.register(self.get_current_date)

    def get_current_time(self, **kwargs) -> str:
        """Get the current time. Use when the user asks 'what time is it?'"""
        return datetime.now().strftime("%-I:%M %p")

    def get_current_date(self, **kwargs) -> str:
        """Get today's date and day of week. Use when user asks 'what day is it?' or 'what's the date?'"""
        return datetime.now().strftime("%A, %B %-d, %Y")


class NewsTool(Toolkit):
    """Fetches top news headlines via RSS (no API key needed)."""

    def __init__(self):
        super().__init__(name="news")
        self.register(self.get_top_headlines)

    def get_top_headlines(self, topic: str = "general") -> str:
        """Get top news headlines. Use when the user asks 'what's in the news?' or 'any news about X?'
        topic can be: general, technology, sports, science, health"""
        feed_urls = {
            "general": "https://feeds.bbci.co.uk/news/rss.xml",
            "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "sports": "https://feeds.bbci.co.uk/sport/rss.xml",
            "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "health": "https://feeds.bbci.co.uk/news/health/rss.xml",
        }
        url = feed_urls.get(topic.lower(), feed_urls["general"])
        try:
            import xml.etree.ElementTree as ET
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:3]
            headlines = []
            for item in items:
                title = item.findtext("title", "").strip()
                if title:
                    headlines.append(title)
            if headlines:
                return " | ".join(headlines)
            return "No headlines found."
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return "I couldn't get the news right now."


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to human-readable text."""
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
