"""
mcp_servers/proxy.py
═════════════════════
ToolProxyRegistry
─────────────────
• Launches all enabled MCP server subprocesses once at startup
• Each server runs in its own asyncio event loop in a background thread
• Exposes a synchronous call(tool, args) interface to the rest of the app
• Watchdog thread pings every server every 30s and auto-reconnects if dead
• get_all_tools() always returns the current live LangChain Tool list

NO MCP-specific code leaks outside this file.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import asyncio
import threading
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = int(os.getenv("MCP_WATCHDOG_INTERVAL", "30"))   # seconds
CONNECT_TIMEOUT   = int(os.getenv("MCP_CONNECT_TIMEOUT",   "15"))   # seconds


# ─────────────────────────────────────────────
# Per-server proxy
# ─────────────────────────────────────────────

@dataclass
class ServerProxy:
    name:        str
    config:      dict
    healthy:     bool               = False
    tools:       List[Tool]         = field(default_factory=list)
    _loop:       Optional[Any]      = field(default=None, repr=False)
    _thread:     Optional[Any]      = field(default=None, repr=False)
    _session:    Optional[Any]      = field(default=None, repr=False)
    _lock:       threading.Lock     = field(default_factory=threading.Lock, repr=False)

    # ── Lifecycle ─────────────────────────────

    def start(self) -> bool:
        """Launch the background event loop thread and connect."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name=f"mcp-{self.name}",
            daemon=True,
        )
        self._thread.start()
        return self._connect_sync()

    def stop(self):
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _connect_sync(self) -> bool:
        """Block until connected (or timeout)."""
        future = asyncio.run_coroutine_threadsafe(
            self._connect_async(), self._loop
        )
        try:
            future.result(timeout=CONNECT_TIMEOUT)
            return True
        except Exception as e:
            logger.warning(f"[{self.name}] connect failed: {e}")
            self.healthy = False
            return False

    async def _connect_async(self):
        """Open the MCP session and load tools."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.sse  import sse_client
            from langchain_mcp_adapters.tools import load_mcp_tools
        except ImportError as e:
            raise RuntimeError(
                f"MCP packages missing. Run: pip install mcp langchain-mcp-adapters\n{e}"
            )

        transport = self.config.get("transport", "stdio")

        if transport == "stdio":
            env = {**os.environ, **self.config.get("env", {})}
            params = StdioServerParameters(
                command=self.config["command"],
                args=self.config.get("args", []),
                env=env,
            )
            self._cm = stdio_client(params)
        else:
            self._cm = sse_client(self.config["url"])

        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

        raw_tools = await load_mcp_tools(self._session)

        # Wrap each MCP tool so calls are routed through this loop
        wrapped = []
        for t in raw_tools:
            wrapped.append(self._wrap_tool(t))

        with self._lock:
            self.tools   = wrapped
            self.healthy = True

        logger.info(f"[{self.name}] connected — {len(wrapped)} tools")

    def _wrap_tool(self, mcp_tool) -> Tool:
        """
        Wrap an MCP tool so its async call runs on this proxy's event loop.
        Handles the 'config' kwarg required by newer langchain-mcp-adapters.
        """
        proxy = self

        def sync_call(input_str: str, **kwargs) -> str:
            if not proxy.healthy:
                return f"[{proxy.name}] server is currently unavailable."
            try:
                # Use invoke() which handles both sync and async internally
                # and accepts the config kwarg that newer LangChain passes
                if hasattr(mcp_tool, 'invoke'):
                    future = asyncio.run_coroutine_threadsafe(
                        mcp_tool.ainvoke(input_str), proxy._loop
                    )
                    return str(future.result(timeout=30))
                elif asyncio.iscoroutinefunction(getattr(mcp_tool, '_arun', None)):
                    future = asyncio.run_coroutine_threadsafe(
                        mcp_tool._arun(input_str, **kwargs), proxy._loop
                    )
                    return str(future.result(timeout=30))
                else:
                    return str(mcp_tool._run(input_str))
            except Exception as e:
                return f"[{proxy.name}] tool error: {e}"

        return Tool(
            name=mcp_tool.name,
            func=sync_call,
            description=f"[{self.name}] {mcp_tool.description}",
        )

    # ── Health / reconnect ────────────────────

    def ping(self) -> bool:
        if not self._loop or not self._loop.is_running():
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._ping_async(), self._loop
            )
            future.result(timeout=5)
            return True
        except Exception:
            return False

    async def _ping_async(self):
        if self._session is None:
            raise RuntimeError("no session")
        await self._session.send_ping()

    def reconnect(self) -> bool:
        logger.info(f"[{self.name}] reconnecting...")
        with self._lock:
            self.healthy = False
            self.tools   = []
        # Try async reconnect on existing loop
        return self._connect_sync()


# ─────────────────────────────────────────────
# Registry — manages all proxies
# ─────────────────────────────────────────────

class ToolProxyRegistry:
    """
    Singleton. Start once at app startup.
    All agents call get_all_tools() to get the current live tool list.
    """

    def __init__(self):
        self._proxies:  Dict[str, ServerProxy] = {}
        self._started   = False
        self._watchdog  = None

    def start(self):
        """Connect to all enabled MCP servers and start the watchdog."""
        if self._started:
            return
        self._started = True

        from mcp_servers.mcp_registry import get_enabled_servers
        enabled = get_enabled_servers()

        if not enabled:
            logger.info("[ToolProxyRegistry] No MCP servers enabled.")
            return

        for name, cfg in enabled.items():
            proxy = ServerProxy(name=name, config=cfg)
            ok = proxy.start()
            self._proxies[name] = proxy
            status = "✅" if ok else "❌"
            logger.info(f"  {status} {name}")

        self._start_watchdog()
        total = sum(len(p.tools) for p in self._proxies.values())
        logger.info(f"[ToolProxyRegistry] Ready — {len(self._proxies)} servers, {total} tools")

    def _start_watchdog(self):
        def watch():
            while True:
                time.sleep(WATCHDOG_INTERVAL)
                for name, proxy in list(self._proxies.items()):
                    if not proxy.ping():
                        logger.warning(f"[watchdog] {name} is down — reconnecting")
                        ok = proxy.reconnect()
                        if ok:
                            logger.info(f"[watchdog] {name} reconnected ✅")
                        else:
                            logger.error(f"[watchdog] {name} still down ❌")

        self._watchdog = threading.Thread(
            target=watch, name="mcp-watchdog", daemon=True
        )
        self._watchdog.start()

    # ── Public API ────────────────────────────

    def get_all_tools(self) -> List[Tool]:
        """Return flat list of all tools from all healthy servers."""
        tools = []
        for proxy in self._proxies.values():
            if proxy.healthy:
                with proxy._lock:
                    tools.extend(proxy.tools)
        return tools

    def get_available_capabilities(self) -> List[str]:
        """Return list of server names that are currently healthy."""
        return [name for name, p in self._proxies.items() if p.healthy]

    def reconnect_all(self):
        """Force reconnect every server. Useful from CLI /reconnect command."""
        for proxy in self._proxies.values():
            proxy.reconnect()

    def reconnect_server(self, name: str) -> str:
        if name not in self._proxies:
            return f"Unknown server: {name}"
        ok = self._proxies[name].reconnect()
        return f"{name}: {'reconnected ✅' if ok else 'still down ❌'}"

    def status(self) -> str:
        if not self._proxies:
            return "No MCP servers configured."
        lines = ["MCP Servers", "─" * 34]
        for name, proxy in self._proxies.items():
            state = f"✅ {len(proxy.tools)} tools" if proxy.healthy else "❌ down"
            lines.append(f"  {name:<15} {state}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────

_registry: Optional[ToolProxyRegistry] = None


def get_registry() -> ToolProxyRegistry:
    """Get (or create) the global ToolProxyRegistry. Safe to call multiple times."""
    global _registry
    if _registry is None:
        _registry = ToolProxyRegistry()
        _registry.start()
    return _registry