"""
System Sub-Agent
────────────────
Handles: weather, date/time, general system info, OS-level tasks.
"""

from __future__ import annotations
import os, sys
import pathfinder

from datetime import datetime
import requests
from langchain_core.tools import Tool
from agents.base_agent import BaseSubAgent
from config.settings import WEATHER_API_KEY


def _get_weather(city: str) -> str:
    api_key = WEATHER_API_KEY
    if not api_key:
        return "Weather API key not configured. Set WEATHER_API_KEY in .env"
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        r = requests.get(url, params={"q": city, "appid": api_key, "units": "metric"}, timeout=10)
        r.raise_for_status()
        d = r.json()
        return (
            f"Weather in {d['name']}, {d['sys']['country']}:\n"
            f"  Condition : {d['weather'][0]['description'].capitalize()}\n"
            f"  Temp      : {d['main']['temp']}°C (feels like {d['main']['feels_like']}°C)\n"
            f"  Humidity  : {d['main']['humidity']}%\n"
            f"  Wind      : {d['wind']['speed']} m/s"
        )
    except Exception as e:
        return f"Weather error: {e}"


def _get_datetime(_: str = "") -> str:
    now = datetime.now()
    return f"Current date & time: {now.strftime('%A, %d %B %Y  %H:%M:%S')}"


def _get_system_info(_: str = "") -> str:
    import platform
    return (
        f"OS      : {platform.system()} {platform.release()}\n"
        f"Python  : {platform.python_version()}\n"
        f"Machine : {platform.machine()}\n"
        f"Node    : {platform.node()}"
    )


class SystemAgent(BaseSubAgent):
    agent_name = "system"
    system_prompt = (
        "You are a System Agent. You handle:\n"
        "  - Current weather for any city\n"
        "  - Current date and time\n"
        "  - Basic system information\n\n"
        "Always use the appropriate tool. Be concise."
    )

    def _load_tools(self):
        return [
            Tool(
                name="get_weather",
                func=_get_weather,
                description="Get current weather for a city. Input: city name (e.g. 'Meerut' or 'New York')."
            ),
            Tool(
                name="get_datetime",
                func=_get_datetime,
                description="Get the current date and time. Input: empty string."
            ),
            Tool(
                name="get_system_info",
                func=_get_system_info,
                description="Get operating system and Python version info. Input: empty string."
            ),
        ]