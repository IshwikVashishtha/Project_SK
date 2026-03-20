"""
agents/orchestrator.py
════════════════════════
Master Orchestrator — binary routing decision:
  1. Clearly a specialist task? → Research / Media / Data / System / Conversation
  2. Needs external integration? → MCPAgent (handles everything itself via ReAct)

The orchestrator checks the LIVE MCP capability list before routing to MCPAgent,
so it never routes there when no servers are connected.
"""

from __future__ import annotations
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
from langchain_core.messages import HumanMessage

from agents.base_agent        import BaseSubAgent, _extract_text
from agents.research_agent    import ResearchAgent
from agents.media_agent       import MediaAgent
# from agents.data_agent        import DataAgent
from agents.system_agent      import SystemAgent
from agents.conversation_agent import ConversationAgent
from agents.mcp_agent         import MCPAgent
from agents.file_agent        import FileAgent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Keyword tables
# ─────────────────────────────────────────────

SPECIALIST_KEYWORDS: dict[str, list[str]] = {
    "research": [
        "search", "look up", "find out", "what is", "who is", "explain",
        "define", "news", "latest", "wikipedia", "history", "tell me about",
        "facts about", "why is", "how does", "learn about",
    ],
    "media": [
        "play", "song", "music", "youtube", "video", "pause", "resume",
        "skip ad", "stop playing", "open youtube", "close youtube",
    ],
    "system": [
        "weather", "temperature", "forecast", "what time", "current time",
        "date today", "what day", "system info", "os version",
    ],
}


FILE_KEYWORDS: list[str] = [
    "send me a file", "send the file", "send a file",
    "give me the file", "get me a file", "i want a file",
    "i need a file", "create a file", "make a file",
    "generate a file", "download", "export to", "save as",
    "write to file", "send me the", ".csv", ".txt", ".json",
    ".pdf", ".xlsx", ".md", ".py", ".log", ".yaml", ".html",
]

# MCP keywords — only used when MCP servers are actually live
MCP_KEYWORDS: list[str] = [
    # filesystem
    "read file", "write file", "create file", "list files", "delete file",
    "open file", "folder", "directory", "find file", "edit file",
    # git / github
    "git", "github", "commit", "branch", "pull request", " pr ", "issue",
    "repository", "repo", "diff", "merge", "clone",
    # communication
    "email", "gmail", "send mail", "inbox", "slack", "send message",
    "notify", "notion", "post in",
    # database
    "sql", "query", "database", "postgres", "sqlite", "select ", "insert ",
    # browser / fetch
    "browse", "screenshot", "open url", "fetch url", "scrape", "visit site",
    # memory
    "remember this", "store this", "recall", "what did i tell you",
    "save this for later",
    # docker
    "docker", "container",
]


class Orchestrator(BaseSubAgent):
    agent_name    = "orchestrator"
    system_prompt = (
        "You are the master orchestrator of a multi-agent AI system called SK. "
        "Classify the user message into exactly one category: "
        "research | media | data | system | mcp | conversation. "
        "Reply with only the category word."
    )

    def __init__(self):
        super().__init__()
        self.research_agent      = ResearchAgent()
        self.media_agent         = MediaAgent()
        # self.data_agent          = DataAgent()
        self.system_agent        = SystemAgent()
        self.conversation_agent  = ConversationAgent()
        self.mcp_agent           = MCPAgent()
        self.file_agent          = FileAgent()

        logger.info("✅ Orchestrator ready (Research | Media | System | MCP | Chat)")

    def _load_tools(self):
        return []

    # ── Routing ───────────────────────────────

    def _score_specialist(self, text: str) -> tuple[str, int]:
        lower = text.lower()
        best, best_score = "conversation", 0
        for intent, kws in SPECIALIST_KEYWORDS.items():
            score = sum(1 for kw in kws if kw in lower)
            if score > best_score:
                best, best_score = intent, score
        return best, best_score

    def _wants_mcp(self, text: str) -> bool:
        """Check if text matches MCP keywords AND MCP has live servers."""
        lower = text.lower()
        keyword_match = any(kw in lower for kw in MCP_KEYWORDS)
        if not keyword_match:
            return False
        # Only route to MCP if servers are actually up
        caps = self.mcp_agent._registry.get_available_capabilities() \
               if self.mcp_agent._registry else []
        return bool(caps)

    def _llm_classify(self, text: str, has_mcp: bool) -> str:
        categories = "research | media | system | file | conversation"
        if has_mcp:
            categories = "research | media | system | file | mcp | conversation"

        mcp_note = ""
        if has_mcp:
            caps = self.mcp_agent._registry.get_available_capabilities() \
                   if self.mcp_agent._registry else []
            mcp_note = f"\nLive MCP capabilities: {', '.join(caps)}"

        prompt = (
            f"Classify this message into exactly one category: {categories}\n"
            f"{mcp_note}\n\n"
            f"Message: {text}\n\n"
            "Reply with only the category word."
        )
        try:
            result  = self.llm.invoke([HumanMessage(content=prompt)])
            intent  = _extract_text(result).strip().lower().split()[0]
            valid   = {"research", "media", "data", "system", "conversation", "mcp", "file"}
            return  intent if intent in valid else "conversation"
        except Exception:
            return "conversation"

    def _classify(self, text: str) -> str:
        has_mcp = bool(
            self.mcp_agent._registry and
            self.mcp_agent._registry.get_available_capabilities()
        )

        # Stage 1: strong specialist keyword match
        specialist, score = self._score_specialist(text)
        if score >= 2:
            return specialist

        # Stage 2: File send/create request
        if any(kw in text.lower() for kw in FILE_KEYWORDS):
            return "file"

        # Stage 3: MCP keyword match (only if servers live)
        if self._wants_mcp(text):
            return "mcp"

        # Stage 4: single specialist keyword match
        if score == 1:
            return specialist

        # Stage 5: LLM fallback
        return self._llm_classify(text, has_mcp)

    # ── Main entry ────────────────────────────

    def invoke(self, user_input: str) -> str:
        user_input = user_input.strip()
        if not user_input:
            return "Please say something!"

        intent = self._classify(user_input)

        routing = {
            "research":     self.research_agent,
            "media":        self.media_agent,
            # "data":         self.data_agent,
            "system":       self.system_agent,
            "file":         self.file_agent,
            "mcp":          self.mcp_agent,
            "conversation": self.conversation_agent,
        }
        agent = routing.get(intent, self.conversation_agent)
        print(f"  → [{intent.upper()}]")

        try:
            response = agent.invoke(user_input)
        except Exception as e:
            response = f"Something went wrong: {e}"

        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", f"[{intent}] {response}")
        return response

    def get_status(self) -> str:
        lines = [
            "DeepAgent Status",
            "════════════════════════════════",
            "  Orchestrator      ✅",
            "  ResearchAgent     ✅  (web + Wikipedia)",
            "  MediaAgent        ✅  (YouTube)",
            # "  DataAgent         ✅  (math + CSV)",
            "  SystemAgent       ✅  (weather / time)",
            "  ConversationAgent ✅  (chat fallback)",
            "  FileAgent         ✅  (create / find / send files)",
            "",
            self.mcp_agent.get_status(),
        ]
        return "\n".join(lines)