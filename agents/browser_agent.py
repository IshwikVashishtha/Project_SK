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

from agents.base_agent import BaseSubAgent

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


class BrowserAgent(BaseSubAgent):
    agent_name    = "browser"
    system_prompt = SYSTEM_PROMPT

    def _load_tools(self):
        return []   # browser-use manages its own tools internally

    # ── SYNC invoke — plain def, no async ────────────────────────

    def invoke(self, user_input: str) -> str:          # <-- plain def, NOT async def
        context = self.memory.get_context()
        task    = user_input
        if context:
            task = f"{context}\n\nCurrent request: {user_input}"

        response = self._run_browser_sync(task)        # sync call

        self.memory.add_turn("user", user_input)       # sync
        self.memory.add_turn("assistant", response)    # sync
        return response

    # ── Sync wrapper around async browser-use ────────────────────

    def _run_browser_sync(self, task: str) -> str:
        """
        Runs browser-use (which is async) from sync code.
        asyncio.run() creates a fresh event loop — safe because our
        entire agent stack is sync so there is no outer running loop.
        """
        try:
            return asyncio.run(self._run_browser_async(task))
        except RuntimeError as e:
            # Rare edge case: called from inside an already-running loop
            if "cannot run" in str(e).lower() or "already running" in str(e).lower():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._run_browser_async(task))
                    return future.result(timeout=120)
            return f"Browser runtime error: {e}"
        except Exception as e:
            logger.error(f"[BrowserAgent] error: {e}")
            return f"Browser task failed: {e}"

    # ── Async internals (only called via asyncio.run above) ───────

    async def _run_browser_async(self, task: str) -> str:
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