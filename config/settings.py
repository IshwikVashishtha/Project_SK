"""
config/settings.py
═══════════════════
Central configuration for DeepAgent system.
Assign different LLM providers/models to each agent role.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# LLM Assignments per Agent Role
# ─────────────────────────────────────────────

AGENT_LLM_CONFIG = {

    # Orchestrator — needs strong reasoning for routing decisions
    "orchestrator": {
        "provider":    os.getenv("ORCHESTRATOR_PROVIDER", "google"),
        "model":       os.getenv("ORCHESTRATOR_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.2,
        "max_tokens":  1500,
    },

    # Browser agent — needs strong reasoning to control a browser
    # Groq Llama 70B is free and fast, great for browser-use
    "browser": {
        "provider":    os.getenv("BROWSER_PROVIDER", "google"),
        "model":       os.getenv("BROWSER_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.2,
        "max_tokens":  2000,
    },

    # System agent — weather, time, OS info (small model fine)
    "system": {
        "provider":    os.getenv("SYSTEM_PROVIDER", "google"),
        "model":       os.getenv("SYSTEM_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.1,
        "max_tokens":  600,
    },

    # MCP agent — needs tool-calling support
    "mcp": {
        "provider":    os.getenv("MCP_PROVIDER", "openrouter"),
        "model":       os.getenv("MCP_MODEL",    "nvidia/nemotron-3-super-120b-a12b:free"),
        # "provider":    os.getenv("MCP_PROVIDER", "google"),
        # "model":       os.getenv("MCP_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.1,
        "max_tokens":  1500,
    },

    # File agent — generates file content, needs decent quality
    "file": {
        "provider":    os.getenv("FILE_PROVIDER", "google"),
        "model":       os.getenv("FILE_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.2,
        "max_tokens":  2000,
    },

    # Conversation agent — general chat, warm and friendly
    "conversation": {
        "provider":    os.getenv("CONVERSATION_PROVIDER", "google"),
        "model":       os.getenv("CONVERSATION_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.4,
        "max_tokens":  1000,
    },

    # Summarizer — compresses memory, keep it lightweight
    "summarizer": {
        "provider":    os.getenv("SUMMARIZER_PROVIDER", "google"),
        "model":       os.getenv("SUMMARIZER_MODEL",    "gemini-3-flash-preview"),
        "temperature": 0.1,
        "max_tokens":  400,
    },
}

# ─────────────────────────────────────────────
# Memory settings
# ─────────────────────────────────────────────
MEMORY_DIR           = os.getenv("MEMORY_DIR",         "memory_store")
BUFFER_WINDOW_SIZE   = int(os.getenv("BUFFER_WINDOW_SIZE", "6"))
SUMMARY_THRESHOLD    = int(os.getenv("SUMMARY_THRESHOLD",  "10"))

# ─────────────────────────────────────────────
# Interface settings
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN",    "")
WHATSAPP_TOKEN        = os.getenv("WHATSAPP_TOKEN",        "")
WHATSAPP_PHONE_ID     = os.getenv("WHATSAPP_PHONE_ID",     "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "deepagent")

# ─────────────────────────────────────────────
# Tool API keys
# ─────────────────────────────────────────────
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", os.getenv("WETHER_API_KEY", ""))
SERPAPI_KEY          = os.getenv("SERPAPI_API_KEY", "")

# ─────────────────────────────────────────────
# Browser settings
# ─────────────────────────────────────────────
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

# ─────────────────────────────────────────────
# MCP server toggles
# ─────────────────────────────────────────────
MCP_FILESYSTEM_ENABLED = os.getenv("MCP_FILESYSTEM_ENABLED", "true").lower()  == "true"
MCP_GIT_ENABLED        = os.getenv("MCP_GIT_ENABLED",        "true").lower()  == "true"
MCP_FETCH_ENABLED      = os.getenv("MCP_FETCH_ENABLED",      "true").lower()  == "true"
MCP_MEMORY_ENABLED     = os.getenv("MCP_MEMORY_ENABLED",     "true").lower()  == "true"
MCP_SQLITE_ENABLED     = os.getenv("MCP_SQLITE_ENABLED",     "false").lower() == "true"
MCP_PUPPETEER_ENABLED  = os.getenv("MCP_PUPPETEER_ENABLED",  "false").lower() == "true"
MCP_DOCKER_ENABLED     = os.getenv("MCP_DOCKER_ENABLED",     "false").lower() == "true"