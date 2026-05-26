"""
agents/github_agent.py

GitHub specialist agent using the GitHub MCP Server.
Fits into the DeepAgent architecture — inherits BaseSubAgent for
memory, summarization, LLM config, and the standard invoke() loop.

Prerequisites:
  Set in .env:
    GITHUB_PERSONAL_ACCESS_TOKEN=<your PAT>
    GITHUB_MCP_MODE=remote | docker | binary  (default: remote)
    GITHUB_MCP_BINARY_PATH=/path/to/github-mcp-server  (binary mode only)

Capabilities (depends on PAT scopes):
  - Read/search repos, files, commits, branches
  - Create/update issues and PRs
  - Query GitHub Actions runs
  - Dependabot, code-scanning, secret-scanning alerts
  - Discussions, notifications, labels, projects
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from typing import List, Any

from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# from agents.base_agent import BaseSubAgent, _extract_text

logger = logging.getLogger(__name__)


# ── MCP config builder ────────────────────────────────────────────

def _build_mcp_config() -> dict:
    mode  = os.environ.get("GITHUB_MCP_MODE", "remote").lower()
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")

    if not token:
        raise ValueError("GITHUB_PERSONAL_ACCESS_TOKEN is not set in .env")

    if mode == "remote":
        return {
  "servers": {
    "github": {
      "transport": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": f"Bearer {token}"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "github_mcp_pat",
      "description": "GitHub Personal Access Token",
      "password": True
    }
  ]
}

    if mode == "docker":
        return {
            "github": {
                "transport": "stdio",
                "command": "docker",
                "args": [
                    "run", "-i", "--rm",
                    "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                    "ghcr.io/github/github-mcp-server",
                ],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": token},
            }
        }

    if mode == "binary":
        binary = os.environ.get(
            "GITHUB_MCP_BINARY_PATH", "/usr/local/bin/github-mcp-server"
        )
        return {
            "github": {
                "transport": "stdio",
                "command": binary,
                "args": ["stdio"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": token},
            }
        }

    raise ValueError(f"Unknown GITHUB_MCP_MODE: {mode!r}")


# ── Sync tool loader ──────────────────────────────────────────────

def _load_github_tools() -> List[Any]:
    """
    Load GitHub MCP tools synchronously.
    Runs the async client in a fresh event loop so BaseSubAgent.__init__
    can call _load_tools() normally without any async/await.
    """
    async def _fetch():
        from langchain_mcp_adapters.client import MultiServerMCPClient
        config = _build_mcp_config()
        client = MultiServerMCPClient(config)
        return await client.get_tools()

    try:
        # Run in a new event loop — safe to call from __init__
        loop   = asyncio.new_event_loop()
        tools  = loop.run_until_complete(_fetch())
        loop.close()
        logger.info(f"[GitHubAgent] Loaded {len(tools)} GitHub MCP tools")
        return tools
    except ExceptionGroup as eg:
        for exc in eg.exceptions:
            logger.error(f"[GitHubAgent] MCP sub-exception: {type(exc).__name__}: {exc}")
        return []
    except Exception as e:
        logger.error(f"[GitHubAgent] Failed to load tools: {e}")
        return []


# ── ReAct prompt ──────────────────────────────────────────────────

def _build_github_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert GitHub assistant with full access to the GitHub API.\n\n"
            "Tools available:\n{tools}\n\n"
            "Tool names: {tool_names}\n\n"
            "When asked about repositories, issues, pull requests, commits, "
            "Actions workflows, or any other GitHub resource — use your tools "
            "to fetch real data and act on the user's behalf.\n"
            "Always confirm destructive actions before executing.\n\n"
            "ALWAYS use this EXACT format:\n"
            "Thought: <your reasoning>\n"
            "Action: <exact tool name>\n"
            "Action Input: <input for the tool>\n"
            "Observation: <tool result>\n"
            "... (repeat as needed)\n"
            "Thought: I now know the final answer\n"
            "Final Answer: <your complete answer>"
        ),
        ("human", "{input}"),
        ("assistant", "Thought: {agent_scratchpad}"),
    ])


# ── The agent ─────────────────────────────────────────────────────

class GitHubAgent():
    pass