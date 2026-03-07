"""
middleware/summarizer.py

Summarization middleware used by every sub-agent.
Keeps a rolling window of recent messages + a running summary
so the LLM context never grows unbounded.

Architecture:
  [new message]
      │
      ▼
  buffer (last N turns verbatim)
      │  when buffer > threshold
      ▼
  summarizer LLM ──► running_summary (compressed history)
      │
      ▼
  context sent to agent = running_summary + recent buffer
"""

import os
import json
from typing import List, Dict, Optional
from pathlib import Path


class ConversationTurn:
    def __init__(self, role: str, content: str):
        self.role = role        # "user" | "assistant" | "tool"
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationTurn":
        return cls(d["role"], d["content"])


class SummarizationMiddleware:
    """
    Per-agent summarization middleware.
    Each agent gets its own instance with its own memory file and summary.
    """

    def __init__(
        self,
        agent_name: str,
        summarizer_llm,                  # a LangChain chat model
        buffer_window: int = 6,          # last N turns kept verbatim
        summary_threshold: int = 10,     # summarize when buffer exceeds this
        memory_dir: str = "memory_store",
    ):
        self.agent_name = agent_name
        self.llm = summarizer_llm
        self.buffer_window = buffer_window
        self.summary_threshold = summary_threshold

        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / f"{agent_name}_memory.json"

        self.buffer: List[ConversationTurn] = []
        self.running_summary: str = ""

        self._load()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def add_turn(self, role: str, content: str):
        """Add a new conversation turn."""
        self.buffer.append(ConversationTurn(role, content))
        if len(self.buffer) >= self.summary_threshold:
            self._compress()
        self._save()

    def get_context(self) -> str:
        """
        Return a compact context string to inject into the agent's prompt.
        Format:  [Summary of past conversation] + [Recent turns]
        """
        parts = []
        if self.running_summary:
            parts.append(f"[Conversation so far]\n{self.running_summary}")
        if self.buffer:
            recent = "\n".join(
                f"{t.role.capitalize()}: {t.content}"
                for t in self.buffer[-self.buffer_window:]
            )
            parts.append(f"[Recent messages]\n{recent}")
        return "\n\n".join(parts) if parts else ""

    def clear(self):
        """Reset memory for this agent."""
        self.buffer = []
        self.running_summary = ""
        self._save()

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _compress(self):
        """Summarize the current buffer and merge into running_summary."""
        turns_text = "\n".join(
            f"{t.role.capitalize()}: {t.content}" for t in self.buffer
        )
        prompt = (
            "You are a concise summarizer. "
            "Compress the conversation below into a short paragraph (3-5 sentences max). "
            "Preserve key facts, decisions, and outcomes. "
            "Do NOT add commentary.\n\n"
            f"Previous summary:\n{self.running_summary or 'None'}\n\n"
            f"New conversation:\n{turns_text}\n\n"
            "Updated summary:"
        )
        try:
            from langchain_core.messages import HumanMessage
            result = self.llm.invoke([HumanMessage(content=prompt)])
            new_summary = result.content.strip()
        except Exception as e:
            # Fallback: keep last few turns as summary
            new_summary = (
                (self.running_summary + " | " if self.running_summary else "")
                + turns_text[-500:]
            )

        self.running_summary = new_summary
        # Keep only the most recent buffer_window turns after compression
        self.buffer = self.buffer[-self.buffer_window:]

    def _save(self):
        try:
            data = {
                "running_summary": self.running_summary,
                "buffer": [t.to_dict() for t in self.buffer],
            }
            with open(self.memory_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file) as f:
                    data = json.load(f)
                self.running_summary = data.get("running_summary", "")
                self.buffer = [
                    ConversationTurn.from_dict(d) for d in data.get("buffer", [])
                ]
            except Exception:
                pass