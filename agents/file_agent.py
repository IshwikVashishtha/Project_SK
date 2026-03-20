"""
agents/file_agent.py
═════════════════════
FileAgent — handles all file AND folder requests.

File operations:
  find → MCP fast path → smart local search → not-found message
  create → LLM generates content → saves to temp → sends

Folder operations:
  list    → show contents
  zip     → zip it → send as document
  create  → os.makedirs
  copy    → shutil.copytree
  move    → shutil.move
  delete  → confirm first, then remove
  find    → locate folder by name
  info    → stats (size, file count, types)
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseSubAgent, _extract_text
from utility.file_handler import (
    save_temp_file, find_file_fast, infer_filename, infer_location,
    make_file_response, is_file_response, FILE_PREFIX, LOCATION_MAP,
)
from utility.folder_handler import (
    infer_foldername, infer_folder_op, is_folder_request,
    find_folder_fast, list_folder, zip_folder,
    create_folder, copy_folder, move_folder, folder_summary,
)

logger = logging.getLogger(__name__)

FILE_SYSTEM_PROMPT = """You are a File Creation Agent.
Generate ONLY the raw file content — no explanation, no markdown fences, no preamble.
Rules:
- CSV  : valid CSV with header row
- JSON : valid well-formatted JSON
- TXT/MD : clean readable text
- Python : valid runnable Python code
- HTML : valid HTML with basic structure
- Any other type : sensible complete content
Start directly with the content.
"""


class FileAgent(BaseSubAgent):
    agent_name    = "file"
    system_prompt = FILE_SYSTEM_PROMPT

    def _load_tools(self):
        return []

    # ════════════════════════════════════════
    # Main entry point
    # ════════════════════════════════════════

    def invoke(self, user_input: str) -> str:
        # Route to folder or file handler
        if is_folder_request(user_input):
            return self._handle_folder(user_input)
        return self._handle_file(user_input)

    # ════════════════════════════════════════
    # Folder handler
    # ════════════════════════════════════════

    def _handle_folder(self, user_input: str) -> str:
        op            = infer_folder_op(user_input)
        folder_name   = infer_foldername(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent/folder] op={op!r} name={folder_name!r} loc={location_hint!r}")

        # ── CREATE ────────────────────────────────────────────────
        if op == "create":
            if not folder_name:
                return self._reply(user_input,
                    "What should I name the new folder? "
                    "Say something like 'create a folder named my_project on Desktop'."
                )
            parent = location_hint or os.getcwd()
            try:
                created = create_folder(folder_name, parent)
                return self._reply(user_input,
                    f"Done! Created folder: {created}"
                )
            except Exception as e:
                return self._reply(user_input, f"Couldn't create folder: {e}")

        # ── Need to find the folder for all other ops ─────────────
        if not folder_name:
            return self._reply(user_input,
                "Which folder? Tell me the folder name, e.g. "
                "'list the Downloads folder' or 'zip my_project'."
            )

        folder_path = find_folder_fast(
            folder_name,
            location_hint=location_hint,
            timeout_seconds=10,
        )

        if not folder_path:
            loc_str = f" in {os.path.basename(location_hint)}" if location_hint else ""
            return self._reply(user_input,
                f"I couldn't find a folder named '{folder_name}'{loc_str}.\n"
                f"Try giving me the full path, e.g. '/home/you/{folder_name}'."
            )

        # ── LIST ─────────────────────────────────────────────────
        if op == "list":
            return self._reply(user_input, list_folder(folder_path))

        # ── INFO / STATS ──────────────────────────────────────────
        if op == "info":
            return self._reply(user_input, folder_summary(folder_path))

        # ── FIND ─────────────────────────────────────────────────
        if op == "find":
            return self._reply(user_input,
                f"Found '{folder_name}' at:\n  {folder_path}"
            )

        # ── ZIP & SEND ────────────────────────────────────────────
        if op == "zip":
            try:
                zip_path = zip_folder(folder_path)
                size     = os.path.getsize(zip_path)
                logger.info(f"[FileAgent] Zipped: {zip_path} ({size} bytes)")
                return self._reply_file(user_input, zip_path)
            except Exception as e:
                return self._reply(user_input, f"Couldn't zip folder: {e}")

        # ── COPY ─────────────────────────────────────────────────
        if op == "copy":
            dest = location_hint or os.getcwd()
            # Try to extract destination from message
            dest_match = self._parse_destination(user_input)
            if dest_match:
                dest = dest_match
            try:
                new_path = copy_folder(folder_path, dest)
                return self._reply(user_input,
                    f"Copied '{folder_name}' to:\n  {new_path}"
                )
            except Exception as e:
                return self._reply(user_input, f"Couldn't copy folder: {e}")

        # ── MOVE ─────────────────────────────────────────────────
        if op == "move":
            dest = self._parse_destination(user_input) or location_hint
            if not dest:
                return self._reply(user_input,
                    f"Where should I move '{folder_name}'? "
                    f"Say something like 'move {folder_name} to Desktop'."
                )
            try:
                new_path = move_folder(folder_path, dest)
                return self._reply(user_input,
                    f"Moved '{folder_name}' to:\n  {new_path}"
                )
            except Exception as e:
                return self._reply(user_input, f"Couldn't move folder: {e}")

        # ── DELETE (ask for confirmation) ─────────────────────────
        if op == "delete":
            # Never delete silently — return a confirmation request
            return self._reply(user_input,
                f"⚠️  Are you sure you want to delete '{folder_path}'?\n"
                f"This cannot be undone. Reply:\n"
                f"  'yes delete {folder_name}' to confirm\n"
                f"  'no' to cancel"
            )

        # Confirmed delete (user said "yes delete ...")
        if "yes delete" in lower or "yes, delete" in lower:
            try:
                import shutil
                shutil.rmtree(folder_path)
                return self._reply(user_input,
                    f"Deleted '{folder_path}'."
                )
            except Exception as e:
                return self._reply(user_input, f"Couldn't delete folder: {e}")

        return self._reply(user_input, folder_summary(folder_path))

    # ════════════════════════════════════════
    # File handler
    # ════════════════════════════════════════

    def _handle_file(self, user_input: str) -> str:
        filename      = infer_filename(user_input)
        location_hint = infer_location(user_input)
        lower         = user_input.lower()

        logger.info(f"[FileAgent/file] filename={filename!r} location={location_hint!r}")

        # ── Absolute path ─────────────────────────────────────────
        if filename and os.path.isabs(filename) and os.path.exists(filename):
            return self._reply_file(user_input, filename)

        # ── MCP fast path ─────────────────────────────────────────
        if filename:
            mcp_path = self._mcp_find_file(filename)
            if mcp_path:
                return self._reply_file(user_input, mcp_path)

        # ── Smart local search ────────────────────────────────────
        if filename:
            found = find_file_fast(filename, location_hint=location_hint, timeout_seconds=10)
            if found:
                return self._reply_file(user_input, found)
            if location_hint:
                loc_name = next(
                    (k.capitalize() for k, v in LOCATION_MAP.items() if v == location_hint),
                    location_hint
                )
                return self._reply(user_input,
                    f"I couldn't find '{filename}' in your {loc_name} folder.\n"
                    f"Try a different location or give me the full path."
                )

        # ── Remote source ─────────────────────────────────────────
        remote_kws = ["github", "drive", "repo", "notion", "gmail", "slack", "remote"]
        if any(k in lower for k in remote_kws):
            try:
                from agents.mcp_agent import MCPAgent
                mcp_response = MCPAgent().invoke(
                    f"{user_input}\n\nFetch the file content, save it locally, "
                    f"and return only: {FILE_PREFIX}<full_absolute_path>"
                )
                if is_file_response(mcp_response):
                    return self._return(user_input, mcp_response)
                if filename:
                    path = save_temp_file(mcp_response, filename)
                    return self._reply_file(user_input, path)
            except Exception as e:
                logger.warning(f"[FileAgent] Remote MCP fetch failed: {e}")

        # ── Not found — tell clearly ──────────────────────────────
        explicitly_existing = any(k in lower for k in [
            "find", "get me", "send me the", "give me the", "read", "open"
        ])
        if filename and explicitly_existing:
            return self._reply(user_input,
                f"I couldn't find '{filename}' on your system.\n"
                f"Searched: Desktop, Documents, Downloads, Projects, home.\n\n"
                f"Try:\n"
                f"  - Full path: '/home/you/projects/{filename}'\n"
                f"  - Or say 'create a file named {filename}' for a new one"
            )

        # ── Generate new file ─────────────────────────────────────
        if not filename:
            filename = "output.txt"
        ext = os.path.splitext(filename)[1].lower()

        try:
            result  = self.llm.invoke([
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
            return self._reply_file(user_input, path)
        except Exception as e:
            return self._reply(user_input, f"I couldn't create the file: {e}")

    # ════════════════════════════════════════
    # MCP helpers
    # ════════════════════════════════════════

    def _mcp_find_file(self, filename: str) -> Optional[str]:
        try:
            from mcp_server.proxy import get_registry
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
            if m and os.path.exists(m.group(1)):
                return m.group(1)
        except Exception as e:
            logger.debug(f"[FileAgent] MCP search failed: {e}")
        return None

    # ════════════════════════════════════════
    # Destination parsing
    # ════════════════════════════════════════

    def _parse_destination(self, text: str) -> Optional[str]:
        """Extract a destination directory from 'move X to Desktop' etc."""
        import re
        m = re.search(r'(?:to|into|→)\s+([\w\-\/\.]+)', text, re.IGNORECASE)
        if m:
            dest = m.group(1).strip()
            if dest.lower() in LOCATION_MAP:
                return LOCATION_MAP[dest.lower()]
            if os.path.isdir(dest):
                return dest
        return None

    # ════════════════════════════════════════
    # Return helpers
    # ════════════════════════════════════════

    def _reply_file(self, user_input: str, path: str) -> str:
        return self._return(user_input, make_file_response(path))

    def _reply(self, user_input: str, text: str) -> str:
        return self._return(user_input, text)

    def _return(self, user_input: str, response: str) -> str:
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", response)
        return response


# Fix missing Optional import at module level
from typing import Optional