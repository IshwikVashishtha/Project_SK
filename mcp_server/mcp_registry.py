"""
Central definition of every MCP server DeepAgent can connect to.
Each entry is a plain dict — no imports from the mcp pip package here.

To add a new server: add one entry to MCP_SERVERS.
To enable/disable: set the env var or flip "enabled".
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
from typing import TypedDict, List, Literal, Optional


class ServerConfig(TypedDict, total=False):
    transport:    Literal["stdio", "sse"]   # how to connect
    command:      str                        # executable (stdio only)
    args:         List[str]                  # args        (stdio only)
    env:          dict                       # extra env   (stdio only)
    url:          str                        # endpoint    (sse only)
    description:  str                        # shown in /status
    required_env: List[str]                  # must all be set to auto-enable
    enabled:      bool                       # runtime toggle


MCP_SERVERS: dict[str, ServerConfig] = {

    # ── No-credential servers (on by default) ────────────────────

    "filesystem": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-filesystem",
                         os.getenv("MCP_FS_ROOT", os.path.expanduser("~"))],
        "env":          {},
        "description":  "Read, write, list, search local files and directories.",
        "required_env": [],
        "enabled":      os.getenv("MCP_FILESYSTEM_ENABLED", "true").lower() == "true",
    },

    "git": {
        "transport":    "stdio",
        "command":      "uvx",
        "args":         ["mcp-server-git", "--repository",
                         os.getenv("MCP_GIT_REPO", ".")],
        "env":          {},
        "description":  "Git: status, diff, log, commit, branch, stash.",
        "required_env": [],
        "enabled":      os.getenv("MCP_GIT_ENABLED", "true").lower() == "true",
    },

    "fetch": {
        "transport":    "stdio",
        "command":      "uvx",
        "args":         ["mcp-server-fetch"],
        "env":          {},
        "description":  "Fetch any URL and return its content as clean markdown.",
        "required_env": [],
        "enabled":      os.getenv("MCP_FETCH_ENABLED", "true").lower() == "true",
    },

    "memory": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-memory"],
        "env":          {},
        "description":  "Persistent key-value memory store across sessions.",
        "required_env": [],
        "enabled":      os.getenv("MCP_MEMORY_ENABLED", "true").lower() == "true",
    },

    "sqlite": {
        "transport":    "stdio",
        "command":      "uvx",
        "args":         ["mcp-server-sqlite",
                         "--db-path", os.getenv("SQLITE_DB_PATH", "./agent_data.db")],
        "env":          {},
        "description":  "SQLite: run queries, inspect schema, manage a local database.",
        "required_env": [],
        "enabled":      os.getenv("MCP_SQLITE_ENABLED", "false").lower() == "true",
    },

    # ── Credential-gated servers (auto-enabled when keys present) ─

    "github": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-github"],
        "env":          {"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", "")},
        "description":  "GitHub: issues, PRs, repos, code search, file contents.",
        "required_env": ["GITHUB_TOKEN"],
        "enabled":      bool(os.getenv("GITHUB_TOKEN")),
    },

    "gmail": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
        "env":          {
            "GMAIL_CLIENT_ID":     os.getenv("GMAIL_CLIENT_ID", ""),
            "GMAIL_CLIENT_SECRET": os.getenv("GMAIL_CLIENT_SECRET", ""),
            "GMAIL_REFRESH_TOKEN": os.getenv("GMAIL_REFRESH_TOKEN", ""),
        },
        "description":  "Gmail: read, send, search, and manage emails.",
        "required_env": ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"],
        "enabled":      bool(os.getenv("GMAIL_CLIENT_ID")),
    },

    "slack": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-slack"],
        "env":          {
            "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
            "SLACK_TEAM_ID":   os.getenv("SLACK_TEAM_ID", ""),
        },
        "description":  "Slack: post messages, read channels, list users.",
        "required_env": ["SLACK_BOT_TOKEN"],
        "enabled":      bool(os.getenv("SLACK_BOT_TOKEN")),
    },

    "notion": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-notion"],
        "env":          {"NOTION_API_KEY": os.getenv("NOTION_API_KEY", "")},
        "description":  "Notion: read/write pages, databases, and blocks.",
        "required_env": ["NOTION_API_KEY"],
        "enabled":      bool(os.getenv("NOTION_API_KEY")),
    },

    "gdrive": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-gdrive"],
        "env":          {
            "GDRIVE_CLIENT_ID":     os.getenv("GDRIVE_CLIENT_ID", ""),
            "GDRIVE_CLIENT_SECRET": os.getenv("GDRIVE_CLIENT_SECRET", ""),
            "GDRIVE_REFRESH_TOKEN": os.getenv("GDRIVE_REFRESH_TOKEN", ""),
        },
        "description":  "Google Drive: list, read, create, and update files/docs.",
        "required_env": ["GDRIVE_CLIENT_ID", "GDRIVE_CLIENT_SECRET", "GDRIVE_REFRESH_TOKEN"],
        "enabled":      bool(os.getenv("GDRIVE_CLIENT_ID")),
    },

    "postgres": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-postgres",
                         os.getenv("POSTGRES_URL", "")],
        "env":          {},
        "description":  "PostgreSQL: run queries, inspect schema, manage data.",
        "required_env": ["POSTGRES_URL"],
        "enabled":      bool(os.getenv("POSTGRES_URL")),
    },

    "brave_search": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-brave-search"],
        "env":          {"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", "")},
        "description":  "Brave Search: privacy-focused web and news search.",
        "required_env": ["BRAVE_API_KEY"],
        "enabled":      bool(os.getenv("BRAVE_API_KEY")),
    },

    "puppeteer": {
        "transport":    "stdio",
        "command":      "npx",
        "args":         ["-y", "@modelcontextprotocol/server-puppeteer"],
        "env":          {},
        "description":  "Browser automation: navigate, click, screenshot, fill forms.",
        "required_env": [],
        "enabled":      os.getenv("MCP_PUPPETEER_ENABLED", "false").lower() == "true",
    },

    "docker": {
        "transport":    "stdio",
        "command":      "uvx",
        "args":         ["mcp-server-docker"],
        "env":          {},
        "description":  "Docker: list/start/stop containers and images.",
        "required_env": [],
        "enabled":      os.getenv("MCP_DOCKER_ENABLED", "false").lower() == "true",
    },
}


def get_enabled_servers() -> dict[str, ServerConfig]:
    """Return servers that are enabled AND have all required env vars set."""
    out = {}
    for name, cfg in MCP_SERVERS.items():
        if not cfg.get("enabled", False):
            continue
        missing = [k for k in cfg.get("required_env", []) if not os.getenv(k)]
        if missing:
            continue
        out[name] = cfg
    return out


def status_table() -> str:
    lines = ["MCP Server Registry", "═" * 44]
    for name, cfg in MCP_SERVERS.items():
        missing = [k for k in cfg.get("required_env", []) if not os.getenv(k)]
        if not cfg.get("enabled", False):
            icon = "⬜ disabled"
        elif missing:
            icon = f"🔴 missing: {', '.join(missing)}"
        else:
            icon = "✅ ready"
        lines.append(f"  {name:<15} {icon}")
        lines.append(f"               {cfg.get('description', '')}")
    return "\n".join(lines)