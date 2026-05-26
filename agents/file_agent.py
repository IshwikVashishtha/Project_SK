"""
agents/file_agent.py
═════════════════════
FileAgent — handles all FILE and FOLDER requests.

FILE flow:
  1. Absolute path given       → send directly
  2. MCP filesystem search     → fastest if MCP live
  3. Smart local search        → find_file_fast() with location hint
  4. Remote source             → MCPAgent (GitHub, Drive, etc.)
  5. Not found + wants existing → clear error message
  6. Generate new file         → LLM generates content → save → send

FOLDER flow:
  list    → return formatted listing as text
  zip     → zip folder → send as .zip file
  create  → make new folder → confirm
  copy    → copy folder → confirm
  move    → move folder → confirm
  info    → folder stats (size, file count, types)
  find    → locate folder on disk

Always returns either:
  - plain string  (listing, confirmation, error)
  - __FILE__:/path (file or zip to deliver via Telegram)
"""

from __future__ import annotations
import sys
import os
import asyncio
import logging
from typing import List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage
from universal_llm import UniversalLLM
from middleware.summarizer import SummarizationMiddleware
from config.settings import AGENT_LLM_CONFIG, MEMORY_DIR, BUFFER_WINDOW_SIZE, SUMMARY_THRESHOLD

from utility.file_handler import (
    save_temp_file, find_file_fast, infer_filename, infer_location,
    make_file_response, is_file_response, FILE_PREFIX, LOCATION_MAP,
)
from utility.folder_handler import (
    is_folder_request, infer_foldername, infer_folder_op, find_folder_fast,
    list_folder, zip_folder, create_folder, copy_folder, move_folder,
    folder_summary,
)

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

FILE_SYSTEM_PROMPT = """You are a File Creation Agent.

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


class FileAgent:
    """
    FileAgent — handles all FILE and FOLDER requests independently.
    No longer depends on BaseSubAgent.
    """
    agent_name    = "file"
    system_prompt = FILE_SYSTEM_PROMPT

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

    async def invoke(self, user_input: str) -> str:
        """
        Main entry point (Async).
        Routes to folder handler or file handler.
        """
        if is_folder_request(user_input):
            return await self._handle_folder(user_input)
        return await self._handle_file(user_input)

    # ═══════════════════════════════════════════════════════════════
    # FOLDER handling
    # ═══════════════════════════════════════════════════════════════

    async def _handle_folder(self, user_input: str) -> str:
        """Handles folder operations like create, list, zip, etc."""
        op            = infer_folder_op(user_input)
        folder_name   = infer_foldername(user_input)
        location_hint = infer_location(user_input)

        logger.info(f"[FileAgent] folder op={op!r} name={folder_name!r} location={location_hint!r}")
        log(f"[FileAgent] folder op={op!r} name={folder_name!r} location={location_hint!r}")

        # ── CREATE ────────────────────────────────────────────────
        if op == "create":
            if not folder_name:
                return await self._ret(user_input, "Please tell me the name of the folder to create.")
            parent = location_hint or os.getcwd()
            log(f"Create folder: {folder_name} in {parent}")
            try:
                path = create_folder(folder_name, parent)
                return await self._ret(user_input, f"✅ Folder created: {path}")
            except Exception as e:
                return await self._ret(user_input, f"Could not create folder: {e}")

        # ── Need a folder path for remaining ops ──────────────────
        folder_path = await self._resolve_folder(folder_name, location_hint)

        if not folder_path:
            where = ""
            if location_hint:
                loc_name = next(
                    (k.capitalize() for k, v in LOCATION_MAP.items() if v == location_hint),
                    location_hint
                )
                where = f" in your {loc_name} folder"
            name_str = f"'{folder_name}'" if folder_name else "that folder"
            return await self._ret(
                user_input,
                f"I couldn't find {name_str}{where}.\n"
                f"Try giving me the full path (e.g. '/home/you/projects/myfolder')"
            )

        # ── LIST ──────────────────────────────────────────────────
        if op == "list":
            listing = list_folder(folder_path)
            return await self._ret(user_input, listing)

        # ── ZIP / SEND ────────────────────────────────────────────
        if op == "zip":
            try:
                zip_path = zip_folder(folder_path)
                return await self._ret(user_input, make_file_response(zip_path))
            except Exception as e:
                return await self._ret(user_input, f"Could not zip folder: {e}")

        # ── INFO / STATS ──────────────────────────────────────────
        if op == "info":
            return await self._ret(user_input, folder_summary(folder_path))

        # ── COPY / MOVE ───────────────────────────────────────────
        if op in ["copy", "move"]:
            dest = self._extract_dest(user_input) or os.getcwd()
            try:
                func = copy_folder if op == "copy" else move_folder
                new_path = func(folder_path, dest)
                return await self._ret(user_input, f"✅ Folder {op}ed to: {new_path}")
            except Exception as e:
                return await self._ret(user_input, f"Could not {op} folder: {e}")

        # ── FIND ──────────────────────────────────────────────────
        if op == "find":
            return await self._ret(user_input, f"Found folder at: {folder_path}")

        return await self._ret(user_input, list_folder(folder_path))

    async def _resolve_folder(self, name: str, location_hint: str) -> str | None:
        """Resolve folder path from name and location hint."""
        if not name:
            if location_hint and os.path.isdir(location_hint):
                return location_hint
            return None

        if os.path.isabs(name) and os.path.isdir(name):
            return name

        name_lower = name.lower()
        if name_lower in LOCATION_MAP:
            p = LOCATION_MAP[name_lower]
            if os.path.isdir(p):
                return p

        if location_hint:
            direct = os.path.join(location_hint, name)
            if os.path.isdir(direct):
                return direct

        mcp_path = await self._mcp_find_folder(name)
        if mcp_path:
            return mcp_path

        return find_folder_fast(name, location_hint=location_hint, timeout_seconds=10)

    def _extract_dest(self, user_input: str) -> str | None:
        """Extract destination path."""
        import re
        m = re.search(r'\bto\s+([\w\-\.\/~]+)', user_input, re.IGNORECASE)
        if m:
            dest = m.group(1)
            dest_lower = dest.lower()
            if dest_lower in LOCATION_MAP:
                return LOCATION_MAP[dest_lower]
            if os.path.isdir(dest):
                return dest
            expanded = os.path.expanduser(f"~/{dest}")
            if os.path.isdir(expanded):
                return expanded
        return None

    # ═══════════════════════════════════════════════════════════════
    # FILE handling
    # ═══════════════════════════════════════════════════════════════

    async def _handle_file(self, user_input: str) -> str:
        """Handles file operations like find, read, create, etc."""
        filename      = infer_filename(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent] file: filename={filename!r} location={location_hint!r}")

        if filename and os.path.isabs(filename) and os.path.exists(filename):
            return await self._ret_file(user_input, filename)

        if filename:
            mcp_path = await self._mcp_find_file(filename)
            if mcp_path:
                return await self._ret_file(user_input, mcp_path)

        if filename:
            found = find_file_fast(filename, location_hint=location_hint, timeout_seconds=10)
            if found:
                return await self._ret_file(user_input, found)

        # Remote fetch via MCPAgent if requested
        remote_keywords = ["github", "drive", "repo", "notion", "gmail", "slack", "remote"]
        if any(k in lower for k in remote_keywords):
            try:
                from agents.mcp_agent import MCPAgent
                mcp_agent = MCPAgent()
                mcp_response = await mcp_agent.invoke(
                    f"{user_input}\n\n"
                    f"Fetch the file content, save it locally, and return "
                    f"only: {FILE_PREFIX}<full_absolute_path>"
                )
                if is_file_response(mcp_response):
                    return await self._ret(user_input, mcp_response)
                if filename:
                    path = save_temp_file(mcp_response, filename)
                    return await self._ret_file(user_input, path)
            except Exception as e:
                logger.warning(f"[FileAgent] Remote MCP fetch failed: {e}")

        # Explicitly wants existing but not found
        explicitly_wants_existing = any(k in lower for k in ["find", "get me", "send me the", "give me the", "read", "open"])
        if filename and explicitly_wants_existing:
            return await self._ret(
                user_input,
                f"I couldn't find '{filename}' on your system.\n"
                f"Try giving me the full path or say 'create a file named {filename}'."
            )

        # Generate new file
        if not filename:
            filename = "output.txt"
        ext = os.path.splitext(filename)[1].lower()

        try:
            result = await self.llm.ainvoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=(
                    f"The user wants a file named '{filename}'.\n"
                    f"Request: {user_input}\n\n"
                    f"Generate the complete {ext or '.txt'} file content."
                )),
            ])
            content = _extract_text(result).strip()

            if content.startswith("```"):
                lines   = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            path = save_temp_file(content, filename)
            return await self._ret_file(user_input, path)

        except Exception as e:
            return await self._ret(user_input, f"I couldn't create the file: {e}")

    async def _mcp_find_file(self, filename: str) -> str | None:
        """Async MCP file search."""
        try:
            from mcp_server.proxy import get_registry
            tools = get_registry().get_all_tools()
            search_tool = next((t for t in tools if "search" in t.name.lower() and "file" in t.name.lower()), None)
            if not search_tool:
                return None
            
            if hasattr(search_tool, "coroutine") and search_tool.coroutine:
                result = await search_tool.coroutine(filename)
            else:
                result = search_tool.func(filename)

            import re
            m = re.search(r'(/[\w/\.\-\_]+)', result)
            if m:
                path = m.group(1)
                if os.path.exists(path):
                    return path
        except Exception as e:
            logger.debug(f"[FileAgent] MCP file search failed: {e}")
        return None

    # shared helpers
    async def _ret_file(self, user_input: str, path: str) -> str:
        return await self._ret(user_input, make_file_response(path))

    async def _ret(self, user_input: str, response: str) -> str:
        await self.memory.add_turn("user", user_input)
        await self.memory.add_turn("assistant", response)
        return response