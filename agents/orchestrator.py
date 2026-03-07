"""
agents/orchestrator.py

Master Orchestrator
═══════════════════

This is the ONLY entry-point the user interacts with.

Architecture:
                        ┌─────────────────────────────┐
  User ──────────────►  │      ORCHESTRATOR           │
                        │  (intent classification)    │
                        └──┬────┬────┬────┬───────────┘
                           │    │    │    │
                    ┌──────┘    │    │    └──────────┐
                    ▼           ▼    ▼               ▼
             ResearchAgent  Media  Data           System
             (web+wiki)    Agent  Agent          Agent
              ┌──────┐              ┌──────┐
              │ Web  │              │ Math │
              │ Wiki │              │ CSV  │
              └──────┘              └──────┘
                    └────────────────────────────────────►
                                                  ConversationAgent
                                                  (fallback / chat)

Each sub-agent has its own SummarizationMiddleware.
The orchestrator also has its own memory of what sub-agents were called.
"""

from __future__ import annotations
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent
from agents.research_agent     import ResearchAgent
from agents.media_agent        import MediaAgent
# from agents.data_agent         import DataAgent
from agents.system_agent       import SystemAgent
from agents.conversation_agent import ConversationAgent


# ─────────────────────────────────────────────
# Intent labels and keywords
# ─────────────────────────────────────────────

INTENT_KEYWORDS = {
    "research": [
        "search", "look up", "find", "what is", "who is", "explain", "define",
        "news", "latest", "wikipedia", "history", "tell me about", "information about",
        "facts", "research", "why is", "how does", "learn about",
    ],
    "media": [
        "play", "song", "music", "youtube", "video", "pause", "resume",
        "skip ad", "stop playing", "open youtube", "close youtube",
    ],
    # "data": [
    #     "calculate", "compute", "solve", "math", "sqrt", "factorial",
    #     "convert", "units", "csv", "dataset", "dataframe", "analyse data",
    #     "how many rows", "statistics", "average", "sum of",
    # ],
    "system": [
        "weather", "temperature", "forecast", "what time", "current time",
        "date today", "what day", "system info", "os version",
    ],
}


class Orchestrator(BaseSubAgent):
    """
    Top-level orchestrator.
    Classifies intent → delegates to the right sub-agent → returns response.
    """

    agent_name = "orchestrator"
    system_prompt = (
        "You are the master orchestrator of a multi-agent AI system named SK. "
        "You receive user requests, decide which specialist sub-agent should handle them, "
        "and return the final answer clearly. "
        "Sub-agents available: Research, Media, Data, System, Conversation.\n"
        "Be concise. Do not repeat the routing decision in your reply."
    )

    def __init__(self):
        super().__init__()
        # Initialise all sub-agents
        self.research_agent     = ResearchAgent()
        self.media_agent        = MediaAgent()
        # self.data_agent         = DataAgent()
        self.system_agent       = SystemAgent()
        self.conversation_agent = ConversationAgent()

        print("✅ Orchestrator initialised with all sub-agents.")

    def _load_tools(self):
        return []  # Orchestrator delegates, doesn't use tools directly

    # ──────────────────────────────────────────
    # Intent classification
    # ──────────────────────────────────────────

    def _classify_intent(self, text: str) -> str:
        """Rule-based + LLM-fallback intent classification."""
        lower = text.lower()
        scores = {intent: 0 for intent in INTENT_KEYWORDS}

        for intent, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    scores[intent] += 1

        best_intent = max(scores, key=scores.get)
        if scores[best_intent] == 0:
            # Fallback: ask the LLM to classify
            best_intent = self._llm_classify(text)

        return best_intent

    def _llm_classify(self, text: str) -> str:
        """Use the LLM to classify intent when keyword matching fails."""
        prompt = (
            "Classify this user message into exactly ONE category:\n"
            "research | media | data | system | conversation\n\n"
            f"Message: {text}\n\n"
            "Reply with only the category word, nothing else."
        )
        try:
            result = self.llm.invoke([HumanMessage(content=prompt)])
            intent = result.content.strip().lower()
            valid = {"research", "media", "data", "system", "conversation"}
            return intent if intent in valid else "conversation"
        except Exception:
            return "conversation"

    # ──────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────

    def invoke(self, user_input: str) -> str:
        """
        Route the user message to the correct sub-agent and return the response.
        """
        user_input = user_input.strip()
        if not user_input:
            return "Please say something!"

        # Classify
        intent = self._classify_intent(user_input)

        # Dispatch
        routing_map = {
            "research":     self.research_agent,
            "media":        self.media_agent,
            # "data":         self.data_agent,
            "system":       self.system_agent,
            "conversation": self.conversation_agent,
        }
        agent = routing_map.get(intent, self.conversation_agent)

        # Log routing (visible in CLI, not sent to user)
        print(f"  → Routing to [{intent.upper()} AGENT]")

        try:
            response = agent.invoke(user_input)
        except Exception as e:
            response = f"I encountered an error while processing your request: {e}"

        # Store in orchestrator's own memory
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", f"[{intent}] {response}")

        return response

    def get_status(self) -> str:
        """Return a status summary of all sub-agents."""
        return (
            "DeepAgent Status\n"
            "════════════════\n"
            "  Orchestrator    : ✅ Active\n"
            "  ResearchAgent   : ✅ Active (web + wiki sub-agents)\n"
            "  MediaAgent      : ✅ Active (YouTube)\n"
            # "  DataAgent       : ✅ Active (math + CSV sub-agents)\n"
            "  SystemAgent     : ✅ Active (weather, time, OS)\n"
            "  ConversationAgent: ✅ Active (chat fallback)\n"
        )