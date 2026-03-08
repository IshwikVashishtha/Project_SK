"""
Media Sub-Agent
───────────────
Handles: YouTube play, pause/resume, skip ads, volume, close.

Wraps yt_control.YouTubeController and exposes it as a LangChain tool agent.
"""

from __future__ import annotations
import os, sys
import pathfinder

from langchain_core.tools import Tool
from agents.base_agent import BaseSubAgent


class MediaAgent(BaseSubAgent):
    agent_name = "media"
    system_prompt = (
        "You are a Media Control Agent. You control YouTube playback.\n"
        "Available capabilities:\n"
        "  - play_song(query)  : search and play a song/video\n"
        "  - play_pause()      : toggle play / pause\n"
        "  - skip_ad()         : skip advertisements\n"
        "  - close()           : close the YouTube browser\n\n"
        "Interpret the user's request and call the correct tool. "
        "Confirm what action you took in a friendly one-liner."
    )

    def __init__(self):
        # Lazy-load YouTubeController so the agent works even without Selenium
        self._yt = None
        super().__init__()

    def _get_yt(self):
        if self._yt is None:
            try:
                from yt_control import YouTubeController
                self._yt = YouTubeController()
            except Exception as e:
                raise RuntimeError(f"YouTubeController unavailable: {e}")
        return self._yt

    def _load_tools(self):

        def play_song(query: str) -> str:
            try:
                return self._get_yt().play_song(query)
            except Exception as e:
                return f"Error playing song: {e}"

        def play_pause(_: str = "") -> str:
            try:
                return self._get_yt().play_pause()
            except Exception as e:
                return f"Error toggling playback: {e}"

        def skip_ad(_: str = "") -> str:
            try:
                return self._get_yt().skip_ad()
            except Exception as e:
                return f"Error skipping ad: {e}"

        def close_yt(_: str = "") -> str:
            try:
                return self._get_yt().close()
            except Exception as e:
                return f"Error closing YouTube: {e}"

        return [
            Tool(name="play_song",   func=play_song,   description="Play a song or video on YouTube. Input: search query string."),
            Tool(name="play_pause",  func=play_pause,  description="Toggle play or pause the current YouTube video. Input: empty string."),
            Tool(name="skip_ad",     func=skip_ad,     description="Skip advertisement on YouTube if present. Input: empty string."),
            Tool(name="close_youtube", func=close_yt,  description="Close the YouTube browser window. Input: empty string."),
        ]