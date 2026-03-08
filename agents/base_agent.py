"""
agents/base_agent.py

Base class for every sub-agent.
Handles: LLM init, summarization middleware, tool binding, and invoke().
"""

from __future__ import annotations
import sys
import os
import pathfinder

from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD


class BaseSubAgent:
    """
    All sub-agents inherit from this.

    Each sub-agent has:
      - Its own LLM (configured in settings.py)
      - Its own SummarizationMiddleware (so its context never blows up)
      - A list of LangChain tools it can call
      - A system prompt describing its role
    """

    agent_name: str = "base"
    system_prompt: str = "You are a helpful AI assistant."

    def __init__(self):
        cfg = AGENT_LLM_CONFIG.get(self.agent_name, AGENT_LLM_CONFIG["orchestrator"])

        # Primary LLM for this agent
        self.llm = UniversalLLM(**cfg).get_model()

        # Summarizer (can be lighter model)
        sum_cfg = AGENT_LLM_CONFIG["summarizer"]
        self.summarizer_llm = UniversalLLM(**sum_cfg).get_model()

        # Per-agent memory with summarization
        self.memory = SummarizationMiddleware(
            agent_name=self.agent_name,
            summarizer_llm=self.summarizer_llm,
            buffer_window=BUFFER_WINDOW_SIZE,
            summary_threshold=SUMMARY_THRESHOLD,
            memory_dir=MEMORY_DIR,
        )

        # Tools — subclasses fill this
        self.tools: List[Any] = self._load_tools()

    def _load_tools(self) -> List[Any]:
        """Override in subclasses to return relevant LangChain tools."""
        return []

    def _build_prompt(self, user_input: str) -> str:
        """Build the full prompt with context injected."""
        context = self.memory.get_context()
        parts = [self.system_prompt]
        if context:
            parts.append(context)
        parts.append(f"User: {user_input}")
        return "\n\n".join(parts)

    def invoke(self, user_input: str) -> str:
        """
        Run the agent on a user input.
        Uses tools if available, falls back to plain LLM.
        """
        try:
            if self.tools:
                agent_executor = create_agent(
                    tools=self.tools,
                    model=self.llm,
                    # middleware=[self.memory],
                )
                full_prompt = self._build_prompt(user_input)
                result = agent_executor.invoke({"input": full_prompt})
                response = result.get("output", str(result))
            else:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=self._build_prompt(user_input)),
                ]
                result = self.llm.invoke(messages)
                response = result.content

        except Exception as e:
            response = f"[{self.agent_name} error]: {e}"

        # Store in this agent's memory
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)

        return response

    def clear_memory(self):
        self.memory.clear()