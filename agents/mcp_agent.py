"""
MCPAgent — thin ReAct agent powered by ToolProxyRegistry.

The orchestrator sends a full user query here.
This agent gets ALL tools from ALL live MCP servers in one flat list,
then runs a ReAct loop to decide which tools to use and how.

No sub-agents. No pre-routing. The LLM figures it out.
"""

from __future__ import annotations
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
from typing import List, Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an MCP Agent with access to powerful external tools.

Your tools may include: file system operations, git/GitHub, email (Gmail), 
messaging (Slack), notes (Notion), databases (SQLite/Postgres), 
web fetching, browser automation, persistent memory, Docker, and more.

How to work:
- Read the user's request carefully
- Look at your available tools and their descriptions
- Plan the steps needed (you may need multiple tool calls)
- Execute step by step, observing results before proceeding
- If a tool fails, try an alternative approach
- Give a clear, concise final answer

Always confirm what action you took and what the result was.
"""


class MCPAgent(BaseSubAgent):
    agent_name    = "mcp"
    system_prompt = SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        # Registry is started once globally — just get the reference here
        try:
            from mcp_server.proxy import get_registry
            self._registry = get_registry()
            caps = self._registry.get_available_capabilities()
            if caps:
                logger.info(f"[MCPAgent] Live capabilities: {caps}")
            else:
                logger.info("[MCPAgent] No MCP servers connected (tools will load if servers come up)")
        except Exception as e:
            logger.warning(f"[MCPAgent] Registry unavailable: {e}")
            self._registry = None

    def _load_tools(self) -> List[Any]:
        # Tools are fetched fresh on every invoke() — not cached here
        return []

    def get_live_tools(self) -> List[Any]:
        """Always fetch the current live tool list from the registry."""
        if self._registry is None:
            return []
        try:
            return self._registry.get_all_tools()
        except Exception as e:
            logger.error(f"[MCPAgent] Failed to get tools: {e}")
            return []

    def invoke(self, user_input: str) -> str:
        tools = self.get_live_tools()

        if not tools:
            # No MCP servers connected — give helpful response
            response = (
                "I don't have any external integrations connected right now. "
                "To enable them, set the relevant keys in your .env file:\n"
                "  - Files/Git: enabled by default (needs npx/uvx installed)\n"
                "  - GitHub: set GITHUB_TOKEN\n"
                "  - Gmail: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN\n"
                "  - Slack: set SLACK_BOT_TOKEN\n"
                "  - Notion: set NOTION_API_KEY\n"
                "Then restart the agent."
            )
            self.memory.add_turn("user", user_input)
            self.memory.add_turn("assistant", response)
            return response

        # Build context from memory
        context = self.memory.get_context()
        full_prompt = user_input
        if context:
            full_prompt = f"{context}\n\nCurrent request: {user_input}"

        try:
            agent_executor = create_agent(
                tools=tools,
                model=self.llm,
            )
            result   = agent_executor.invoke({"input": full_prompt})
            response = result.get("output", str(result))

        except Exception as e:
            logger.error(f"[MCPAgent] ReAct error: {e}")
            response = f"I ran into a problem while working on that: {e}"

        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response

    def get_status(self) -> str:
        if self._registry is None:
            return "MCP registry not initialised."
        return self._registry.status()

    def reconnect(self, server: str = None) -> str:
        if self._registry is None:
            return "MCP registry not initialised."
        if server:
            return self._registry.reconnect_server(server)
        self._registry.reconnect_all()
        return "Reconnect triggered for all MCP servers."