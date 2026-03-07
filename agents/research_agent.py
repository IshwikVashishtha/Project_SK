"""
agents/research_agent.py

Research Sub-Agent
─────────────────
Handles: web search, Wikipedia lookups, fact-finding, news.

Sub-agents under Research:
  • WebSearchAgent  – uses SerpAPI
  • WikiAgent       – uses Wikipedia
  
ResearchAgent routes between them and synthesises a final answer.
"""

from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.tools import Tool
from langchain_community.utilities import WikipediaAPIWrapper
from agents.base_agent import BaseSubAgent
from config.settings import SERPAPI_KEY


# ─────────────────────────────────────────────
# Leaf agents (specialist sub-sub-agents)
# ─────────────────────────────────────────────

class WebSearchAgent(BaseSubAgent):
    agent_name = "research"
    system_prompt = (
        "You are a web-search specialist. "
        "Use the Search tool to find current, accurate information. "
        "Return concise, factual summaries. No fluff."
    )

    def _load_tools(self):
        tools = []
        if SERPAPI_KEY:
            try:
                from langchain.utilities import SerpAPIWrapper
                serp = SerpAPIWrapper(serpapi_api_key=SERPAPI_KEY)
                tools.append(Tool(
                    name="Search",
                    func=serp.run,
                    description="Search the internet for current information, news, facts."
                ))
            except Exception:
                pass
        return tools


class WikiAgent(BaseSubAgent):
    agent_name = "research"
    system_prompt = (
        "You are a Wikipedia knowledge specialist. "
        "Use the Wikipedia tool to look up detailed background information. "
        "Summarise clearly and concisely."
    )

    def _load_tools(self):
        try:
            wiki = WikipediaAPIWrapper()
            return [Tool(
                name="Wikipedia",
                func=wiki.run,
                description="Look up encyclopaedic background information on any topic."
            )]
        except Exception:
            return []


# ─────────────────────────────────────────────
# ResearchAgent — routes to sub-sub-agents
# ─────────────────────────────────────────────

class ResearchAgent(BaseSubAgent):
    """
    Orchestrates WebSearchAgent and WikiAgent.
    Decides which source to query (or both) then merges results.
    """
    agent_name = "research"
    system_prompt = (
        "You are a Research Agent. You have two specialist sub-agents:\n"
        "  1. WebSearch  – for current events, news, prices, weather\n"
        "  2. Wikipedia  – for background knowledge, history, concepts\n\n"
        "Route the query appropriately, collect results, and synthesise a clear, "
        "concise final answer. Do not repeat raw search results verbatim."
    )

    def __init__(self):
        super().__init__()
        self.web_agent  = WebSearchAgent()
        self.wiki_agent = WikiAgent()

    def _load_tools(self):
        return []  # This agent uses sub-agents, not direct tools

    def invoke(self, user_input: str) -> str:
        lower = user_input.lower()

        # Decide routing
        needs_web  = any(k in lower for k in ["today", "current", "latest", "news", "weather", "price", "now", "2024", "2025"])
        needs_wiki = any(k in lower for k in ["what is", "who is", "explain", "define", "history", "how does", "meaning"])

        # Default: try web first, then wiki for depth
        results = []

        if needs_web or (not needs_wiki):
            r = self.web_agent.invoke(user_input)
            if r and "[research error]" not in r:
                results.append(f"Web Search Result:\n{r}")

        if needs_wiki or (not results):
            r = self.wiki_agent.invoke(user_input)
            if r and "[research error]" not in r:
                results.append(f"Wikipedia Result:\n{r}")

        if not results:
            combined = "I could not find relevant information from web or Wikipedia."
        else:
            combined = "\n\n---\n\n".join(results)

        # Synthesise using own LLM
        synthesis_prompt = (
            f"Synthesise the following research results into one clear, concise answer "
            f"for the question: '{user_input}'\n\n{combined}"
        )
        from langchain_core.messages import HumanMessage, SystemMessage
        try:
            messages = [
                SystemMessage(content="You are a helpful research synthesiser. Be concise and accurate."),
                HumanMessage(content=synthesis_prompt),
            ]
            result = self.llm.invoke(messages)
            response = result.content
        except Exception as e:
            response = combined  # fallback: return raw

        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response