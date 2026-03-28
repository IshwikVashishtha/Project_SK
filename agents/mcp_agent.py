"""
agents/mcp_agent.py
════════════════════
MCPAgent — thin ReAct agent powered by ToolProxyRegistry.
Uses create_react_agent + AgentExecutor with a self-contained
ChatPromptTemplate — works with Groq, Gemini, OpenAI, Anthropic, Ollama.
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import time
from typing import List, Any

from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent, _extract_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an MCP Agent with access to powerful external tools.

Your tools may include: file system operations, git/GitHub, email (Gmail),
messaging (Slack), notes (Notion), databases (SQLite/Postgres),
web fetching, browser automation, persistent memory, Docker, and more.

How to work:
- Read the user request carefully
- Look at your available tools and their descriptions
- Plan the steps needed (you may need multiple tool calls)
- Execute step by step, observing results before proceeding
- If a tool fails, try an alternative approach
- Give a clear, concise final answer

Always confirm what action you took and what the result was.
"""



def _trim_tool_descriptions(tools: list, max_chars: int = 120) -> list:
    """
    Trim tool descriptions to reduce token usage.
    Critical for rate-limited providers (Groq free tier = 12k TPM).
    With 62 tools, full descriptions can be 6000+ tokens just for the tool list.
    """
    from langchain_core.tools import Tool
    trimmed = []
    for t in tools:
        if len(t.description) > max_chars:
            short_desc = t.description[:max_chars].rsplit(' ', 1)[0] + "..."
            trimmed.append(Tool(
                name=t.name,
                func=t.func,
                description=short_desc,
            ))
        else:
            trimmed.append(t)
    return trimmed

def _build_mcp_prompt() -> ChatPromptTemplate:
    """
    Self-contained ReAct ChatPromptTemplate for MCPAgent.
    No hub.pull — works offline and with all providers.
    Variables required by create_react_agent:
        {tools}             — tool descriptions
        {tool_names}        — comma-separated tool names
        {input}             — user input
        {agent_scratchpad}  — ReAct thinking steps
    """
    return ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an MCP Agent with access to powerful external tools.\n\n"
            "Tools available to you:\n{tools}\n\n"
            "Tool names: {tool_names}\n\n"
            "Your tools may include: filesystem, git/GitHub, email, Slack, "
            "Notion, databases, web fetching, browser automation, memory, Docker.\n\n"
            "ALWAYS use this EXACT format:\n"
            "Thought: <your reasoning>\n"
            "Action: <exact tool name from tool_names>\n"
            "Action Input: <input for the tool>\n"
            "Observation: <tool result will appear here>\n"
            "... (repeat Thought/Action/Action Input/Observation as needed)\n"
            "Thought: I now know the final answer\n"
            "Final Answer: <your complete answer to the user>\n\n"
            "Never skip the Thought step. Never invent tool names."
        ),
        ("human", "{input}"),
        ("assistant", "Thought: {agent_scratchpad}"),
    ])


class MCPAgent(BaseSubAgent):
    agent_name    = "mcp"
    system_prompt = SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        try:
            from mcp_servers.proxy import get_registry
            self._registry = get_registry()
            caps = self._registry.get_available_capabilities()
            if caps:
                logger.info(f"[MCPAgent] Live capabilities: {caps}")
            else:
                logger.info("[MCPAgent] No MCP servers connected yet")
        except Exception as e:
            logger.warning(f"[MCPAgent] Registry unavailable: {e}")
            self._registry = None

    def _load_tools(self) -> List[Any]:
        # Tools fetched fresh on every invoke() from the live registry
        return []

    def get_live_tools(self) -> List[Any]:
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
            response = (
                "I don't have any external integrations connected right now.\n"
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

        # Inject conversation memory context into the prompt
        context = self.memory.get_context()
        full_prompt = user_input
        if context:
            full_prompt = f"{context}\n\nCurrent request: {user_input}"

        # Trim tool descriptions to save tokens on rate-limited providers
        trimmed_tools = _trim_tool_descriptions(tools, max_chars=120)

        try:
            prompt = _build_mcp_prompt()
            agent  = create_react_agent(
                llm=self.llm,
                tools=trimmed_tools,
                prompt=prompt,
            )
            agent_executor = AgentExecutor(
                agent=agent,
                tools=trimmed_tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                early_stopping_method="generate",
            )
            result   = agent_executor.invoke({"input": full_prompt})
            response = _extract_text(result)

        except Exception as e:
            err = str(e)
            # Auto-retry once on rate limit after waiting
            if "rate_limit_exceeded" in err or "429" in err:
                import re
                wait = 5
                m = re.search(r'try again in ([0-9.]+)s', err)
                if m:
                    wait = float(m.group(1)) + 1
                logger.warning(f"[MCPAgent] Rate limited — waiting {wait}s then retrying")
                time.sleep(wait)
                try:
                    result   = agent_executor.invoke({"input": full_prompt})
                    response = _extract_text(result)
                except Exception as e2:
                    response = f"I ran into a problem: {e2}"
            else:
                logger.error(f"[MCPAgent] ReAct error: {e}")
                response = f"I ran into a problem: {e}"

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