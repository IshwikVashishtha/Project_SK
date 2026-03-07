"""
config/settings.py
Central configuration for DeepAgent system.
Assign different LLM providers/models to each agent role.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# LLM Assignments per Agent Role
# Change provider/model here to swap any agent's brain
# ─────────────────────────────────────────────

AGENT_LLM_CONFIG = {

    # Main orchestrator – needs strongest reasoning
    "orchestrator": {
        "provider": os.getenv("ORCHESTRATOR_PROVIDER", "groq"),
        "model":    os.getenv("ORCHESTRATOR_MODEL",    ""),
        "temperature": 0.2,
        "max_tokens":  1500,
    },

    # Research sub-agent – web search + Wikipedia
    "research": {
        "provider": os.getenv("RESEARCH_PROVIDER", "groq"),
        "model":    os.getenv("RESEARCH_MODEL",    ""),
        "temperature": 0.1,
        "max_tokens":  1500,
    },

    # Media sub-agent – YouTube control
    "media": {
        "provider": os.getenv("MEDIA_PROVIDER", "groq"),
        "model":    os.getenv("MEDIA_MODEL",    ""),
        "temperature": 0.1,
        "max_tokens":  500,
    },

    # Data sub-agent – CSV analysis, math, unit conversion
    "data": {
        "provider": os.getenv("DATA_PROVIDER", "groq"),
        "model":    os.getenv("DATA_MODEL",    ""),
        "temperature": 0.0,
        "max_tokens":  800,
    },

    # System sub-agent – weather, OS actions
    "system": {
        "provider": os.getenv("SYSTEM_PROVIDER", "groq"),
        "model":    os.getenv("SYSTEM_MODEL",    ""),
        "temperature": 0.1,
        "max_tokens":  600,
    },

    # Summarizer – lightweight, used by middleware
    "summarizer": {
        "provider": os.getenv("SUMMARIZER_PROVIDER", "groq"),
        "model":    os.getenv("SUMMARIZER_MODEL",    ""),
        "temperature": 0.1,
        "max_tokens":  400,
    },
}

# ─────────────────────────────────────────────
# Memory settings
# ─────────────────────────────────────────────
MEMORY_DIR           = os.getenv("MEMORY_DIR", "memory_store")
BUFFER_WINDOW_SIZE   = int(os.getenv("BUFFER_WINDOW_SIZE", "6"))   # last N exchanges kept verbatim
SUMMARY_THRESHOLD    = int(os.getenv("SUMMARY_THRESHOLD",  "10"))  # summarize after N exchanges

# ─────────────────────────────────────────────
# Interface settings
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
WHATSAPP_TOKEN       = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID    = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_VERIFY_TOKEN= os.getenv("WHATSAPP_VERIFY_TOKEN", "deepagent")

# ─────────────────────────────────────────────
# Tool API keys
# ─────────────────────────────────────────────
SERPAPI_KEY          = os.getenv("SERPAPI_API_KEY", "")
WEATHER_API_KEY      = os.getenv("WEATHER_API_KEY", os.getenv("WETHER_API_KEY", ""))
# groq_BASE_URL      = os.getenv("groq_BASE_URL", "http://localhost:11434")