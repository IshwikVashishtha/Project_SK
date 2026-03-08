"""
pathfinder.py
─────────────
Adds the project root to sys.path exactly once.
Import this at the top of main.py and every interface entry point.
All internal modules then use clean absolute imports like:
    from agents.base_agent import BaseSubAgent
    from mcp.mcp_registry import MCP_SERVERS
"""
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)