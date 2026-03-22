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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent, _extract_text
from utils.file_handler import (
    save_temp_file, find_file_fast, infer_filename, infer_location,
    make_file_response, is_file_response, FILE_PREFIX, LOCATION_MAP,
)
from utils.folder_handler import (
    is_folder_request, infer_foldername, infer_folder_op, find_folder_fast,
    list_folder, zip_folder, create_folder, copy_folder, move_folder,
    folder_summary,
)

logger = logging.getLogger(__name__)

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


class FileAgent(BaseSubAgent):
    agent_name    = "file"
    system_prompt = FILE_SYSTEM_PROMPT

    def _load_tools(self):
        return []

    # ═══════════════════════════════════════════════════════════════
    # Main entry point
    # ═══════════════════════════════════════════════════════════════

    def invoke(self, user_input: str) -> str:
        # Route to folder handler first if it looks like a folder request
        if is_folder_request(user_input):
            return self._handle_folder(user_input)
        return self._handle_file(user_input)

    # ═══════════════════════════════════════════════════════════════
    # FOLDER handling
    # ═══════════════════════════════════════════════════════════════

    def _handle_folder(self, user_input: str) -> str:
        op            = infer_folder_op(user_input)
        folder_name   = infer_foldername(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent] folder op={op!r} name={folder_name!r} location={location_hint!r}")

        # ── CREATE ────────────────────────────────────────────────
        if op == "create":
            if not folder_name:
                return self._ret(user_input, "Please tell me the name of the folder to create.")
            parent = location_hint or os.getcwd()
            try:
                path = create_folder(folder_name, parent)
                return self._ret(user_input, f"✅ Folder created: {path}")
            except Exception as e:
                return self._ret(user_input, f"Could not create folder: {e}")

        # ── Need a folder path for remaining ops ──────────────────
        folder_path = self._resolve_folder(folder_name, location_hint)

        if not folder_path:
            # Give a helpful error
            where = ""
            if location_hint:
                loc_name = next(
                    (k.capitalize() for k, v in LOCATION_MAP.items() if v == location_hint),
                    location_hint
                )
                where = f" in your {loc_name} folder"
            name_str = f"'{folder_name}'" if folder_name else "that folder"
            return self._ret(
                user_input,
                f"I couldn't find {name_str}{where}.\n"
                f"Try giving me the full path (e.g. '/home/you/projects/myfolder')"
            )

        # ── LIST ──────────────────────────────────────────────────
        if op == "list":
            listing = list_folder(folder_path)
            return self._ret(user_input, listing)

        # ── ZIP / SEND ────────────────────────────────────────────
        if op == "zip":
            try:
                zip_path = zip_folder(folder_path)
                logger.info(f"[FileAgent] Zipped folder to: {zip_path}")
                return self._ret(user_input, make_file_response(zip_path))
            except Exception as e:
                return self._ret(user_input, f"Could not zip folder: {e}")

        # ── INFO / STATS ──────────────────────────────────────────
        if op == "info":
            return self._ret(user_input, folder_summary(folder_path))

        # ── COPY ──────────────────────────────────────────────────
        if op == "copy":
            dest = self._extract_dest(user_input) or os.getcwd()
            try:
                new_path = copy_folder(folder_path, dest)
                return self._ret(user_input, f"✅ Folder copied to: {new_path}")
            except Exception as e:
                return self._ret(user_input, f"Could not copy folder: {e}")

        # ── MOVE ──────────────────────────────────────────────────
        if op == "move":
            dest = self._extract_dest(user_input) or os.getcwd()
            try:
                new_path = move_folder(folder_path, dest)
                return self._ret(user_input, f"✅ Folder moved to: {new_path}")
            except Exception as e:
                return self._ret(user_input, f"Could not move folder: {e}")

        # ── FIND ──────────────────────────────────────────────────
        if op == "find":
            return self._ret(user_input, f"Found folder at: {folder_path}")

        # Default fallback — list
        return self._ret(user_input, list_folder(folder_path))

    def _resolve_folder(self, name: str, location_hint: str) -> str | None:
        """
        Try to resolve a folder path from name + optional location hint.
        Priority:
          1. Absolute path given directly
          2. Known location keyword (desktop, downloads, etc.)
          3. MCP list_directory if available
          4. find_folder_fast()
        """
        if not name:
            # No name but a location hint — the hint IS the folder
            if location_hint and os.path.isdir(location_hint):
                return location_hint
            return None

        # Absolute path
        if os.path.isabs(name) and os.path.isdir(name):
            return name

        # Location keyword match (e.g. "desktop" → ~/Desktop)
        name_lower = name.lower()
        if name_lower in LOCATION_MAP:
            p = LOCATION_MAP[name_lower]
            if os.path.isdir(p):
                return p

        # If location_hint given, look there first
        if location_hint:
            direct = os.path.join(location_hint, name)
            if os.path.isdir(direct):
                return direct

        # MCP fast path
        mcp_path = self._mcp_find_folder(name)
        if mcp_path:
            return mcp_path

        # Local search
        return find_folder_fast(name, location_hint=location_hint, timeout_seconds=10)

    def _mcp_find_folder(self, name: str) -> str | None:
        """Use MCP filesystem list_directory or search to find a folder."""
        try:
            from mcp_servers.proxy import get_registry
            tools = get_registry().get_all_tools()
            # Look for a list_directory or search tool
            tool = next(
                (t for t in tools if any(
                    k in t.name.lower()
                    for k in ["list_dir", "list_directory", "search_dir"]
                )),
                None
            )
            if not tool:
                return None
            result = tool.func(name)
            import re
            m = re.search(r'(/[\w/\.\-\_]+)', result)
            if m:
                p = m.group(1)
                if os.path.isdir(p):
                    return p
        except Exception as e:
            logger.debug(f"[FileAgent] MCP folder search failed: {e}")
        return None

    def _extract_dest(self, user_input: str) -> str | None:
        """Extract destination path from 'copy/move X to Y' phrasing."""
        import re
        m = re.search(r'\bto\s+([\w\-\.\/~]+)', user_input, re.IGNORECASE)
        if m:
            dest = m.group(1)
            # Resolve location keywords
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
    # FILE handling (unchanged from before)
    # ═══════════════════════════════════════════════════════════════

    def _handle_file(self, user_input: str) -> str:
        filename      = infer_filename(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent] file: filename={filename!r} location={location_hint!r}")

        # Step 1: Absolute path
        if filename and os.path.isabs(filename) and os.path.exists(filename):
            return self._ret_file(user_input, filename)

        # Step 2: MCP filesystem search
        if filename:
            mcp_path = self._mcp_find_file(filename)
            if mcp_path:
                return self._ret_file(user_input, mcp_path)

        # Step 3: Smart local search with location hint
        if filename:
            found = find_file_fast(filename, location_hint=location_hint, timeout_seconds=10)
            if found:
                return self._ret_file(user_input, found)
            if location_hint:
                loc_name = next(
                    (k.capitalize() for k, v in LOCATION_MAP.items() if v == location_hint),
                    location_hint
                )
                return self._ret(
                    user_input,
                    f"I couldn't find '{filename}' in your {loc_name} folder.\n"
                    f"Try a different location or give me the full path."
                )

        # Step 4: Remote source (GitHub, Drive, etc.)
        remote_keywords = ["github", "drive", "repo", "notion", "gmail", "slack", "remote"]
        if any(k in lower for k in remote_keywords):
            try:
                from agents.mcp_agent import MCPAgent
                mcp_response = MCPAgent().invoke(
                    f"{user_input}\n\n"
                    f"Fetch the file content, save it locally, and return "
                    f"only: {FILE_PREFIX}<full_absolute_path>"
                )
                if is_file_response(mcp_response):
                    return self._ret(user_input, mcp_response)
                if filename:
                    path = save_temp_file(mcp_response, filename)
                    return self._ret_file(user_input, path)
            except Exception as e:
                logger.warning(f"[FileAgent] Remote MCP fetch failed: {e}")

        # Step 5: Clearly wants existing file but not found
        explicitly_wants_existing = any(k in lower for k in [
            "find", "get me", "send me the", "give me the", "read", "open"
        ])
        if filename and explicitly_wants_existing:
            return self._ret(
                user_input,
                f"I couldn't find '{filename}' on your system.\n"
                f"Searched in: Desktop, Documents, Downloads, Projects, and home directory.\n\n"
                f"Try:\n"
                f"  - Full path: '/home/you/projects/{filename}'\n"
                f"  - Or say 'create a file named {filename}' for a new one"
            )

        # Step 6: Generate new file with LLM
        if not filename:
            filename = "output.txt"
        ext = os.path.splitext(filename)[1].lower()

        try:
            result = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=(
                    f"The user wants a file named '{filename}'.\n"
                    f"Request: {user_input}\n\n"
                    f"Generate the complete {ext or '.txt'} file content."
                )),
            ])
            content = _extract_text(result).strip()

            # Strip accidental markdown fences
            if content.startswith("```"):
                lines   = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            path = save_temp_file(content, filename)
            logger.info(f"[FileAgent] Generated: {path}")
            return self._ret_file(user_input, path)

        except Exception as e:
            return self._ret(user_input, f"I couldn't create the file: {e}")

    def _mcp_find_file(self, filename: str) -> str | None:
        try:
            from mcp_servers.proxy import get_registry
            tools = get_registry().get_all_tools()
            search_tool = next(
                (t for t in tools if "search" in t.name.lower() and "file" in t.name.lower()),
                None
            )
            if not search_tool:
                return None
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

    # ═══════════════════════════════════════════════════════════════
    # Shared helpers
    # ═══════════════════════════════════════════════════════════════

    def _ret_file(self, user_input: str, path: str) -> str:
        return self._ret(user_input, make_file_response(path))

    def _ret(self, user_input: str, response: str) -> str:
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response