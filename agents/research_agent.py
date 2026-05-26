"""
Handles: web search, Wikipedia lookups, fact-finding, news.

Sub-agents under Research:
  • WebSearchAgent  – uses SerpAPI
  • WikiAgent       – uses Wikipedia
  
ResearchAgent routes between them and synthesises a final answer.
"""

from __future__ import annotations
import os, sys
import asyncio
import logging
from typing import List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.tools import Tool
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage

from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD, SERPAPI_KEY

logger = logging.getLogger(__name__)


def _extract_text(result) -> str:
    """
    Safely extract string from ANY LLM or agent result.
    """
    if isinstance(result, dict):
        return result.get("output", str(result))

    content = getattr(result, "content", result)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)

    return str(content)


# ─────────────────────────────────────────────
# Leaf agents (specialist sub-sub-agents)
# ─────────────────────────────────────────────

class WebSearchAgent:
    """
    Independent WebSearchAgent using SerpAPI.
    """
    agent_name = "research"
    system_prompt = (
        "You are a web-search specialist. "
        "Use the Search tool to find current, accurate information. "
        "Return concise, factual summaries. No fluff."
    )

    def __init__(self):
        cfg = AGENT_LLM_CONFIG.get(self.agent_name, AGENT_LLM_CONFIG["orchestrator"])
        self.llm = UniversalLLM(**cfg).get_model()

        sum_cfg = AGENT_LLM_CONFIG["summarizer"]
        self.summarizer_llm = UniversalLLM(**sum_cfg).get_model()

        self.memory = SummarizationMiddleware(
            agent_name=self.agent_name + "_web",
            summarizer_llm=self.summarizer_llm,
            buffer_window=BUFFER_WINDOW_SIZE,
            summary_threshold=SUMMARY_THRESHOLD,
            memory_dir=MEMORY_DIR,
        )
        self.tools = self._load_tools()

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

    def _build_prompt(self, user_input: str) -> str:
        context = self.memory.get_context()
        parts = [self.system_prompt]
        if context:
            parts.append(context)
        parts.append(f"User: {user_input}")
        return "\n\n".join(parts)

    async def invoke(self, user_input: str) -> str:
        try:
            if self.tools:
                from langchain.agents import AgentExecutor, create_react_agent
                from langchain import hub
                try:
                    prompt = hub.pull("hwchase17/react")
                except Exception:
                    from langchain_core.prompts import PromptTemplate
                    prompt = PromptTemplate.from_template(
                        "Answer the following question using the tools available.\n\n"
                        "Tools: {tools}\n\nTool names: {tool_names}\n\n"
                        "Question: {input}\n\nScratchpad: {agent_scratchpad}"
                    )
                agent = create_react_agent(self.llm, self.tools, prompt)
                executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False, handle_parsing_errors=True)
                
                result = await executor.ainvoke({"input": self._build_prompt(user_input)})
                response = _extract_text(result)
            else:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=self._build_prompt(user_input)),
                ]
                result = await self.llm.ainvoke(messages)
                response = _extract_text(result)
        except Exception as e:
            response = f"[WebSearch error]: {e}"

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response


class WikiAgent:
    """
    Independent WikiAgent using Wikipedia.
    """
    agent_name = "research"
    system_prompt = (
        "You are a Wikipedia knowledge specialist. "
        "Use the Wikipedia tool to look up detailed background information. "
        "Summarise clearly and concisely."
    )

    def __init__(self):
        cfg = AGENT_LLM_CONFIG.get(self.agent_name, AGENT_LLM_CONFIG["orchestrator"])
        self.llm = UniversalLLM(**cfg).get_model()

        sum_cfg = AGENT_LLM_CONFIG["summarizer"]
        self.summarizer_llm = UniversalLLM(**sum_cfg).get_model()

        self.memory = SummarizationMiddleware(
            agent_name=self.agent_name + "_wiki",
            summarizer_llm=self.summarizer_llm,
            buffer_window=BUFFER_WINDOW_SIZE,
            summary_threshold=SUMMARY_THRESHOLD,
            memory_dir=MEMORY_DIR,
        )
        self.tools = self._load_tools()

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

    def _build_prompt(self, user_input: str) -> str:
        context = self.memory.get_context()
        parts = [self.system_prompt]
        if context:
            parts.append(context)
        parts.append(f"User: {user_input}")
        return "\n\n".join(parts)

    async def invoke(self, user_input: str) -> str:
        try:
            if self.tools:
                from langchain.agents import AgentExecutor, create_react_agent
                from langchain import hub
                try:
                    prompt = hub.pull("hwchase17/react")
                except Exception:
                    from langchain_core.prompts import PromptTemplate
                    prompt = PromptTemplate.from_template(
                        "Answer the following question using the tools available.\n\n"
                        "Tools: {tools}\n\nTool names: {tool_names}\n\n"
                        "Question: {input}\n\nScratchpad: {agent_scratchpad}"
                    )
                agent = create_react_agent(self.llm, self.tools, prompt)
                executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False, handle_parsing_errors=True)
                
                result = await executor.ainvoke({"input": self._build_prompt(user_input)})
                response = _extract_text(result)
            else:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=self._build_prompt(user_input)),
                ]
                result = await self.llm.ainvoke(messages)
                response = _extract_text(result)
        except Exception as e:
            response = f"[Wiki error]: {e}"

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response


# ─────────────────────────────────────────────
# ResearchAgent — routes to sub-sub-agents
# ─────────────────────────────────────────────

class ResearchAgent:
    """
    Orchestrates WebSearchAgent and WikiAgent.
    Independent of BaseSubAgent.
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

        self.web_agent  = WebSearchAgent()
        self.wiki_agent = WikiAgent()

    async def invoke(self, user_input: str) -> str:
        """
        Orchestrates research by querying sub-agents asynchronously.
        """
        lower = user_input.lower()

        # Decide routing
        needs_web  = any(k in lower for k in ["today", "current", "latest", "news", "weather", "price", "now", "2024", "2025"])
        needs_wiki = any(k in lower for k in ["what is", "who is", "explain", "define", "history", "how does", "meaning"])

        results = []
        tasks = []

        if needs_web or (not needs_wiki):
            tasks.append(self.web_agent.invoke(user_input))

        if needs_wiki:
            tasks.append(self.wiki_agent.invoke(user_input))

        if tasks:
            raw_results = await asyncio.gather(*tasks)
            for r in raw_results:
                if r and "[research error]" not in r:
                    results.append(r)

        if not results:
            combined = "I could not find relevant information from web or Wikipedia."
        else:
            combined = "\n\n---\n\n".join(results)

        # Synthesise using own LLM
        synthesis_prompt = (
            f"Synthesise the following research results into one clear, concise answer "
            f"for the question: '{user_input}'\n\n{combined}"
        )
        try:
            messages = [
                SystemMessage(content="You are a helpful research synthesiser. Be concise and accurate."),
                HumanMessage(content=synthesis_prompt),
            ]
            result = await self.llm.ainvoke(messages)
            response = _extract_text(result)
        except Exception as e:
            response = combined  # fallback: return raw

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response