"""
Master Orchestrator

Routing priority:
  1. LLM classification  ← PRIMARY (understands context and ambiguity)
  2. Keyword fallback    ← only if LLM fails or is unavailable

The LLM receives:
  - the user message
  - available agent categories
  - live MCP capabilities (so it knows what's actually connected)
"""

from __future__ import annotations
import sys
import os
import asyncio
import logging
from typing import List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD

# Lazy imports to avoid circular dependencies
from agents.research_agent     import ResearchAgent
from agents.conversation_agent import ConversationAgent
from agents.file_agent         import FileAgent
from agents.github_agent       import GitHubAgent
# Missing imports for other agents

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


VALID_INTENTS = {"research", "file", "mcp", "conversation", "github"}    

# ─────────────────────────────────────────────
# Keyword fallback tables (used ONLY if LLM fails)
# ─────────────────────────────────────────────

_FALLBACK_KEYWORDS: dict[str, list[str]] = {
    # "github": [
    #     "github", "git", "commit", "branch", "pull request", "issue",
    #     "repository", "repo", "merge",
    # ],
    "file": [
        "send me a file", "send the file", "send a file", "give me the file",
        "get me a file", "i want a file", "create a file", "make a file",
        "generate a file", "export to", "save as", "write to file",
        ".csv", ".txt", ".json", ".pdf", ".xlsx", ".md", ".py", ".log",
        ".yaml", ".html", "folder", "directory", "mkdir", "zip the",
        "zip folder", "compress", "archive", "list folder", "contents of",
        "what's in", "whats in", "create folder", "make folder",
    ],
    "mcp": [
    "github", "git", "commit", "branch", "pull request", "issue",
        "repository", "repo", "merge", "diff", "email", "gmail",
        "slack", "notion", "sql", "query", "database", "postgres",
        "sqlite", "browse", "screenshot", "fetch url", "scrape",
        "remember this", "store this", "recall", "docker", "container",
    ],
    "research": [
        "search", "look up", "what is", "who is", "explain", "define",
        "news", "latest", "wikipedia", "history", "tell me about",
        "why is", "how does",
    ],
}


def _keyword_fallback(text: str, has_mcp: bool) -> str:
    """
    Simple keyword fallback — only called when LLM classification fails.
    Scores each category and returns the highest match.
    """
    lower = text.lower()
    scores: dict[str, int] = {k: 0 for k in _FALLBACK_KEYWORDS}

    for intent, keywords in _FALLBACK_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[intent] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "conversation"


class Orchestrator:
    """
    Master Orchestrator — handles classification and routing.
    Independent of BaseSubAgent.
    """
    agent_name    = "orchestrator"
    system_prompt = (
        "You are the master orchestrator of a multi-agent AI system called SK. "
        "Classify the user message into exactly one category. "
        "Reply with only the category word, nothing else."
    )

    def __init__(self):
        # Initialize LLM and Memory directly
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

        self._research_agent     = None
        self._conversation_agent = None
        self._file_agent         = None
        self._github_agent       = None
        logger.info("✅ Orchestrator ready (Lazy loading agents)")

    @property
    def research_agent(self):
        if self._research_agent is None:
            self._research_agent = ResearchAgent()
        return self._research_agent

    @property
    def conversation_agent(self):
        if self._conversation_agent is None:
            self._conversation_agent = ConversationAgent()
        return self._conversation_agent

    @property
    def file_agent(self):
        if self._file_agent is None:
            self._file_agent = FileAgent()
        return self._file_agent

    @property
    def github_agent(self):
        if self._github_agent is None:
            self._github_agent = GitHubAgent()
        return self._github_agent

    # ── Primary: LLM classification ──────────

    async def _llm_classify(self, text: str) -> str:
        """
        Ask the LLM to classify the intent.
        Gives it the full context — live MCP capabilities + available categories.
        """

        # Describe what each category does so the LLM makes an informed choice
        descriptions = {
            "github":       "GitHub operations, pull requests, issues, commits",
            "research":     "web search, Wikipedia, facts, news, explanations",
            "file":         "find/send/create files, list/zip/create folders",
            "conversation": "general chat, questions, anything else",
        }

        category_list = "\n".join(
            f"  {c}: {descriptions[c]}"
            for c in categories
            if descriptions.get(c)
        )

        prompt = (
            f"Classify the user message below into exactly ONE category.\n\n"
            f"Categories:\n{category_list}\n\n"
            f"User message: {text}\n\n"
            f"Reply with only the category word."
        )

        try:
            result = await self.llm.ainvoke([HumanMessage(content=prompt)])
            intent = _extract_text(result).strip().lower().split()[0]
            # Strip punctuation the LLM might add
            intent = intent.strip(".,!?\"'")
            if intent in VALID_INTENTS:
                logger.info(f"[Orchestrator] LLM classified as: {intent}")
                return intent
            logger.warning(f"[Orchestrator] LLM returned unknown intent '{intent}' — falling back to keywords")
        except Exception as e:
            logger.warning(f"[Orchestrator] LLM classification failed: {e} — falling back to keywords")

        # Fallback to keywords if LLM fails
        return _keyword_fallback(text, has_mcp=has_mcp)


    # ── Main entry ────────────────────────────

    async def invoke(self, user_input: str) -> str:
        user_input = user_input.strip()
        if not user_input:
            return "Please say something!"

        intent = await self._llm_classify(user_input)

        routing = {
            "github":       self.github_agent,
            "research":     self.research_agent,
            "file":         self.file_agent,
            "conversation": self.conversation_agent,
        }

        agent = routing.get(intent, self.conversation_agent)
        logger.info(f"Routing to agent: {intent}")
        print(f"  → [{intent.upper()}]")

        try:
            response = await agent.invoke(user_input)
        except Exception as e:
            logger.error(f"[Orchestrator] Error calling agent {intent}: {e}")
            response = f"I ran into an error while handling your request: {e}"

        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", f"[{intent}] {response}")
        return response

    def get_status(self) -> str:
        lines = [
            "DeepAgent Status",
            "════════════════════════════════",
            "  Orchestrator      ✅  (LLM-first routing)",
            "  GitHubAgent       ✅  (GitHub API)",
            "  ResearchAgent     ✅  (web + Wikipedia)",
            "  ConversationAgent ✅  (chat fallback)",
            "  FileAgent         ✅  (files + folders)",
            "",
            self.mcp_agent.get_status(),
        ]
        return "\n".join(lines)