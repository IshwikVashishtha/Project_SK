"""
agents/conversation_agent.py

Conversation Sub-Agent
───────────────────────
Handles: general chat, follow-up questions, greetings, small talk.
Falls back here when no specialist agent matches.
"""

from __future__ import annotations
import os, sys
import pathfinder

from langchain_core.messages import SystemMessage, HumanMessage
from agents.base_agent import BaseSubAgent


class ConversationAgent(BaseSubAgent):
    agent_name = "orchestrator"   # shares orchestrator LLM config
    system_prompt = (
        "You are SK, a friendly, curious, and knowledgeable AI companion. "
        "You are warm, enthusiastic, and speak simply so anyone can understand. "
        "Use examples and analogies. Keep answers helpful and engaging. "
        "Do not use excessive emojis."
    )

    def _load_tools(self):
        return []  # Pure LLM — no tools needed for chat

    def invoke(self, user_input: str) -> str:
        context = self.memory.get_context()
        system = self.system_prompt
        if context:
            system += f"\n\n{context}"

        try:
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=user_input),
            ]
            result = self.llm.invoke(messages)
            response = result.content
            response = response[0]['text']
        except Exception as e:
            response = f"I'm having trouble responding right now: {e}"

        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response