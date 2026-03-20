"""
FileAgent — handles all "find / send / create a file" requests.

Decision flow:
  1. MCP FAST PATH  — if filesystem MCP server is live, use its search_files
                      tool (fastest, most accurate)
  2. SMART SEARCH   — if MCP not available, use find_file_fast() with
                      priority dirs + skip-list + timeout
  3. LLM GENERATE   — file doesn't exist → generate content with LLM and
                      save to /tmp/deepagent_files/<name>

Always returns __FILE__:/path so the interface can deliver it.
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent, _extract_text
from utils.file_handler import (
    save_temp_file, find_file_fast, infer_filename, infer_location,
    make_file_response, is_file_response, FILE_PREFIX, LOCATION_MAP
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a File Creation Agent.

When asked to create a file, generate ONLY the raw file content.
Rules:
- CSV  : valid CSV with header row
- JSON : valid, well-formatted JSON  
- TXT/MD : clean readable text
- Python : valid, runnable Python code
- HTML : valid HTML with basic structure
- Any other type : sensible, complete content

Output ONLY the file content — no explanation, no markdown fences (no ```),
no preamble. Start directly with the content.
"""


def _extract_text(result) -> str:
    """
    Safely extract string content from an LLM result.
    Handles all return types:
      - plain string
      - AIMessage with .content as string
      - AIMessage with .content as list of blocks  ← the bug case
    """
    content = getattr(result, "content", result)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # {"type": "text", "text": "..."} format
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)

    return str(content)


class FileAgent(BaseSubAgent):
    agent_name    = "file"
    system_prompt = SYSTEM_PROMPT

    def _load_tools(self):
        return []

    # ── MCP fast path ─────────────────────────────────────────────

    def _mcp_find_file(self, filename: str) -> str | None:
        """Use the MCP filesystem server's search_files tool."""
        try:
            from mcp_servers.proxy import get_registry
            registry = get_registry()
            tools = registry.get_all_tools()

            search_tool = next(
                (t for t in tools if "search" in t.name.lower() and "file" in t.name.lower()),
                None
            )
            if not search_tool:
                return None

            result = search_tool.func(filename)

            import re
            match = re.search(r'(/[\w/\.\-\_]+)', result)
            if match:
                path = match.group(1)
                if os.path.exists(path):
                    return path
        except Exception as e:
            logger.debug(f"[FileAgent] MCP search failed: {e}")
        return None

    def _mcp_read_file(self, path: str) -> str | None:
        """Use MCP read_file tool to get file contents."""
        try:
            from mcp_servers.proxy import get_registry
            registry = get_registry()
            tools = registry.get_all_tools()

            read_tool = next(
                (t for t in tools if "read" in t.name.lower() and "file" in t.name.lower()),
                None
            )
            if read_tool:
                return read_tool.func(path)
        except Exception as e:
            logger.debug(f"[FileAgent] MCP read failed: {e}")
        return None

    # ── Main invoke ───────────────────────────────────────────────

    def invoke(self, user_input: str) -> str:
        filename      = infer_filename(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent] filename={filename!r} location={location_hint!r}")

        # ── Step 1: User gave an absolute path ────────────────────
        if filename and os.path.isabs(filename) and os.path.exists(filename):
            logger.info(f"[FileAgent] Absolute path provided: {filename}")
            return self._return_file(user_input, filename)

        # ── Step 2: Try MCP filesystem search (fastest) ───────────
        if filename:
            mcp_path = self._mcp_find_file(filename)
            if mcp_path:
                logger.info(f"[FileAgent] MCP found: {mcp_path}")
                return self._return_file(user_input, mcp_path)

        # ── Step 3: Smart local search with optional location hint ─
        if filename:
            found = find_file_fast(filename, location_hint=location_hint, timeout_seconds=10)
            if found:
                logger.info(f"[FileAgent] Local search found: {found}")
                return self._return_file(user_input, found)
            if location_hint:
                location_name = next(
                    (k.capitalize() for k, v in LOCATION_MAP.items() if v == location_hint),
                    location_hint
                )
                response = (
                    f"I couldn't find '{filename}' in your {location_name} folder.\n"
                    f"Make sure the file name is correct or try:\n"
                    f"  - A different location (e.g. 'from Documents')\n"
                    f"  - The full path (e.g. '/home/you/{filename}')"
                )
                self.memory.add_turn("user", user_input)
                self.memory.add_turn("assistant", response)
                return response

        # ── Step 4: Remote source (GitHub, Drive, etc.) ───────────
        remote_keywords = ["github", "drive", "repo", "notion", "gmail", "slack", "remote"]
        if any(k in lower for k in remote_keywords):
            try:
                from agents.mcp_agent import MCPAgent
                mcp_response = MCPAgent().invoke(
                    f"{user_input}\n\n"
                    f"Fetch the file content, then save it locally and return "
                    f"only: {FILE_PREFIX}<full_absolute_path>"
                )
                if is_file_response(mcp_response):
                    return self._return(user_input, mcp_response)
                if filename:
                    path = save_temp_file(mcp_response, filename)
                    return self._return_file(user_input, path)
            except Exception as e:
                logger.warning(f"[FileAgent] Remote MCP fetch failed: {e}")

        # ── Step 5: File not found — tell user clearly ────────────
        explicitly_wants_existing = any(k in lower for k in [
            "find", "get me", "send me the", "give me the", "read", "open"
        ])
        if filename and explicitly_wants_existing:
            response = (
                f"I couldn't find '{filename}' on your system.\n"
                f"Searched in: Desktop, Documents, Downloads, Projects, and home directory.\n\n"
                f"Try:\n"
                f"  - Giving me the full path (e.g. '/home/you/projects/{filename}')\n"
                f"  - Saying 'create a file named {filename}' if you want a new one"
            )
            self.memory.add_turn("user", user_input)
            self.memory.add_turn("assistant", response)
            return response

        # ── Step 6: Generate new file with LLM ───────────────────
        if not filename:
            filename = "output.txt"
        ext = os.path.splitext(filename)[1].lower()

        generation_prompt = (
            f"The user wants a file named '{filename}'.\n"
            f"Request: {user_input}\n\n"
            f"Generate the complete {ext or '.txt'} file content."
        )
        try:
            result  = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=generation_prompt),
            ])

            # ← THE FIX: use _extract_text() instead of result.content.strip()
            content = _extract_text(result).strip()

            # Strip accidental markdown fences
            if content.startswith("```"):
                lines   = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            path = save_temp_file(content, filename)
            logger.info(f"[FileAgent] Generated: {path}")
            return self._return_file(user_input, path)

        except Exception as e:
            response = f"I couldn't create the file: {e}"
            self.memory.add_turn("user", user_input)
            self.memory.add_turn("assistant", response)
            return response

    # ── Helpers ───────────────────────────────────────────────────

    def _return_file(self, user_input: str, path: str) -> str:
        return self._return(user_input, make_file_response(path))

    def _return(self, user_input: str, response: str) -> str:
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response