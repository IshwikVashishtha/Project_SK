"""
agents/browser_agent.py
════════════════════════
BrowserAgent — powered by browser-use + Playwright.
EVERYTHING is sync. invoke() is a plain def.
Only _run_browser_async is async, called via asyncio.run() inside sync wrapper.

Install:
  pip install browser-use playwright
  playwright install chromium
"""

from __future__ import annotations
import pathfinder

import os
import asyncio
import logging
from typing import List, Any

from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Browser Agent with full control of a real web browser.

You can:
- Search Google or DuckDuckGo for any information
- Open YouTube and play, pause, skip ads on videos
- Navigate to any website and read its content
- Fill forms, click buttons, scroll pages
- Read Wikipedia, news sites, documentation
- Look up prices, live data, anything on the web

For research: find accurate, up-to-date information and summarise clearly.
For media: open the site, find the content, control playback.
Always give a clear, concise final answer based on what you found.
"""


class BrowserAgent:
    """
    BrowserAgent — powered by browser-use + Playwright.
    Independent of BaseSubAgent and fully async.
    """
    agent_name    = "browser"
    system_prompt = SYSTEM_PROMPT

    def __init__(self):
        # Initialize LLM and Memory directly
        cfg = AGENT_LLM_CONFIG.get(self.agent_name, AGENT_LLM_CONFIG["orchestrator"])
        self.llm = UniversalLLM(**cfg).get_model()

        sum_cfg = AGENT_LLM_CONFIG["summarizer"]
        self.summarizer_llm = UniversalLLM(**sum_cfg).get_model()

        self.memory = SummarizationMiddleware(
            agent_name=self.agent_name,
            summarizer_llm=self.summarizer_llm,
            buffer_window=BUFFER_WINDOW_SIZE,
            summary_threshold=SUMMARY_THRESHOLD,
            memory_dir=MEMORY_DIR,
        )

    async def invoke(self, user_input: str) -> str:
        """
        Main entry point (Async).
        """
        context = self.memory.get_context()
        task    = user_input
        if context:
            task = f"{context}\n\nCurrent request: {user_input}"

        response = await self._run_browser_async(task)

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response

    async def _run_browser_async(self, task: str) -> str:
        """
        Async call to browser-use.
        """
        try:
            from browser_use import Agent as BrowserUseAgent
            from browser_use import BrowserConfig
        except ImportError:
            return (
                "browser-use is not installed.\n"
                "Run: pip install browser-use\n"
                "Then: playwright install chromium"
            )
        try:
            headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
            config   = BrowserConfig(headless=headless)

            agent  = BrowserUseAgent(
                task           = task,
                llm            = self.llm,
                browser_config = config,
            )
            result = await agent.run()

            # Extract final answer from browser-use AgentHistoryList
            if hasattr(result, "final_result"):
                answer = result.final_result()
            elif hasattr(result, "__str__"):
                answer = str(result)
            else:
                answer = repr(result)

            return answer or "Task completed but no text result returned."

        except Exception as e:
            logger.error(f"[BrowserAgent] async error: {e}")
            return f"Browser task failed: {e}"