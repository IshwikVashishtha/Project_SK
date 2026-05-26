from __future__ import annotations
import os, sys
import asyncio
import logging
from typing import List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage
from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD

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


class ConversationAgent:
    """
    Independent ConversationAgent for general chat.
    """
    agent_name = "orchestrator"   # shares orchestrator LLM config
    system_prompt = (
        "You are SK, a friendly, curious, and knowledgeable AI companion. "
        "You are warm, enthusiastic, and speak simply so anyone can understand. "
        "Use examples and analogies. Keep answers helpful and engaging. "
        "Do not use excessive emojis."
    )

    def __init__(self):
        # Initialize LLM and Memory directly
        cfg = AGENT_LLM_CONFIG.get(self.agent_name, AGENT_LLM_CONFIG["orchestrator"])
        self.llm = UniversalLLM(**cfg).get_model()

        sum_cfg = AGENT_LLM_CONFIG["summarizer"]
        self.summarizer_llm = UniversalLLM(**sum_cfg).get_model()

        self.memory = SummarizationMiddleware(
            agent_name=self.agent_name + "_chat",
            summarizer_llm=self.summarizer_llm,
            buffer_window=BUFFER_WINDOW_SIZE,
            summary_threshold=SUMMARY_THRESHOLD,
            memory_dir=MEMORY_DIR,
        )

    async def invoke(self, user_input: str) -> str:
        """
        Handles general conversation (Async).
        """
        context = self.memory.get_context()
        system = self.system_prompt
        if context:
            system += f"\n\n{context}"

        try:
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=user_input),
            ]
            result = await self.llm.ainvoke(messages)
            response = _extract_text(result)
        except Exception as e:
            response = f"I'm having trouble responding right now: {e}"

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response

    async def clear_memory(self):
        """Async clear memory."""
        await self.memory.clear()
