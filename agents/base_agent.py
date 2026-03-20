"""
agents/base_agent.py
Base class for every sub-agent.
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Any
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD


def _extract_text(result) -> str:
    """
    Safely extract string from ANY LLM or agent result.
    Handles all shapes returned by LangChain + Ollama:
      - str                        plain string
      - AIMessage.content: str     normal LLM response
      - AIMessage.content: list    Ollama block format [{"type":"text","text":"..."}]
      - dict {"output": "..."}     agent executor result
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


class BaseSubAgent:
    agent_name:   str = "base"
    system_prompt: str = "You are a helpful AI assistant."

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

        self.tools: List[Any] = self._load_tools()

    def _load_tools(self) -> List[Any]:
        return []

    def _build_prompt(self, user_input: str) -> str:
        context = self.memory.get_context()
        parts = [self.system_prompt]
        if context:
            parts.append(context)
        parts.append(f"User: {user_input}")
        return "\n\n".join(parts)

    def invoke(self, user_input: str) -> str:
        try:
            if self.tools:
                agent_executor = create_agent(
                    tools=self.tools,
                    model=self.llm,
                )
                full_prompt = self._build_prompt(user_input)
                result   = agent_executor.invoke({"input": full_prompt})
                response = _extract_text(result)
            else:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=self._build_prompt(user_input)),
                ]
                result   = self.llm.invoke(messages)
                response = _extract_text(result)

        except Exception as e:
            response = f"[{self.agent_name} error]: {e}"

        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response

    def clear_memory(self):
        self.memory.clear()