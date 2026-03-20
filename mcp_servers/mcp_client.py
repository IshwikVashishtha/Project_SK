from __future__ import annotations
import os, sys, asyncio, logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Lazy import guard — MCP is optional
# ─────────────────────────────────────────────

def _mcp_available() -> bool:
    try:
        import mcp_servers                          # noqa: F401
        import langchain_mcp_adapters       # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────
# Single-server connection
# ─────────────────────────────────────────────

class MCPServerConnection:
    """
    Manages the lifecycle of one MCP server and exposes its tools
    as LangChain-compatible Tool objects.
    """

    def __init__(self, name: str, config: dict):
        self.name   = name
        self.config = config
        self._tools: List[Any] = []
        self._connected = False

    def connect(self) -> List[Any]:
        """
        Synchronously spin up the server, fetch its tool list,
        and return them as LangChain Tools.
        """
        if self._connected:
            return self._tools

        if not _mcp_available():
            logger.warning(
                "MCP packages not installed. "
                "Run: pip install mcp langchain-mcp-adapters"
            )
            return []

        try:
            tools = asyncio.run(self._async_connect())
            self._tools = tools
            self._connected = True
            logger.info(f"[MCP] Connected to '{self.name}' — {len(tools)} tools loaded")
        except Exception as e:
            logger.error(f"[MCP] Failed to connect to '{self.name}': {e}")
            self._tools = []

        return self._tools

    async def _async_connect(self) -> List[Any]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.sse import sse_client
        from langchain_mcp_adapters.tools import load_mcp_tools

        transport = self.config.get("transport", "stdio")

        if transport == "stdio":
            # Inject required env vars
            env = {**os.environ, **self.config.get("env", {})}
            server_params = StdioServerParameters(
                command=self.config["command"],
                args=self.config.get("args", []),
                env=env,
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    return tools

        elif transport == "sse":
            url = self.config["url"]
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    return tools

        else:
            raise ValueError(f"Unknown transport: {transport}")

    @property
    def tools(self) -> List[Any]:
        return self._tools

    @property
    def is_connected(self) -> bool:
        return self._connected


# ─────────────────────────────────────────────
# Multi-server manager
# ─────────────────────────────────────────────

class MCPClientManager:
    """
    Manages connections to ALL enabled MCP servers.
    Provides a flat list of all tools, or tools filtered by capability.
    """

    def __init__(self):
        self._connections: Dict[str, MCPServerConnection] = {}
        self._initialized = False

    def initialize(self) -> "MCPClientManager":
        """Connect to all enabled servers. Call once at startup."""
        if self._initialized:
            return self

        from mcp_servers.mcp_registry import get_enabled_servers
        enabled = get_enabled_servers()

        if not enabled:
            logger.info("[MCP] No MCP servers enabled.")
            self._initialized = True
            return self

        for name, cfg in enabled.items():
            conn = MCPServerConnection(name, cfg)
            conn.connect()
            self._connections[name] = conn

        total = sum(len(c.tools) for c in self._connections.values())
        logger.info(f"[MCP] Initialized {len(self._connections)} server(s), {total} tools total.")
        self._initialized = True
        return self

    def get_all_tools(self) -> List[Any]:
        """Return every tool from every connected server."""
        tools = []
        for conn in self._connections.values():
            tools.extend(conn.tools)
        return tools

    def get_tools_by_capability(self, capability: str) -> List[Any]:
        """Return tools from servers matching a capability tag."""
        from mcp_servers.mcp_registry import MCP_SERVERS
        tools = []
        for name, conn in self._connections.items():
            if MCP_SERVERS.get(name, {}).get("capability") == capability:
                tools.extend(conn.tools)
        return tools

    def get_tools_for_servers(self, server_names: List[str]) -> List[Any]:
        """Return tools from a specific list of server names."""
        tools = []
        for name in server_names:
            if name in self._connections:
                tools.extend(self._connections[name].tools)
        return tools

    def list_connected(self) -> str:
        lines = ["Connected MCP Servers", "─" * 30]
        if not self._connections:
            lines.append("  (none)")
        for name, conn in self._connections.items():
            status = f"✅ {len(conn.tools)} tools" if conn.is_connected else "❌ failed"
            lines.append(f"  {name:<15} {status}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
# Singleton — shared across all agents
# ─────────────────────────────────────────────

_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    """Get (or lazily create) the global MCP manager singleton."""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
        _manager.initialize()
    return _manager