"""
utils/folder_handler.py
════════════════════════
All folder operations for the agent.

Operations:
  - find_folder_fast()   : locate a folder by name
  - list_folder()        : list contents of a folder
  - zip_folder()         : zip a folder into /tmp/deepagent_files/
  - create_folder()      : create a new folder
  - copy_folder()        : copy a folder to a destination
  - move_folder()        : move a folder to a destination
  - folder_summary()     : stats — file count, size, types
  - infer_foldername()   : extract folder name from natural language
  - infer_folder_op()    : detect which operation the user wants
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional

# Reuse skip dirs and location map from file_handler
from utils.file_handler import SKIP_DIRS, LOCATION_MAP, DEFAULT_ROOTS, save_temp_file


# ── Folder name inference ─────────────────────────────────────────

def infer_foldername(user_input: str) -> Optional[str]:
    """Extract a folder name from natural language."""
    # Words that are never folder names
    NEVER = {
        "the", "a", "my", "our", "this", "that",
        "folder", "directory", "me", "it", "here",
    }

    patterns = [
        # Explicit keyword + name
        r'folder\s+named\s+([\w\-\.]+)',
        r'folder\s+called\s+([\w\-\.]+)',
        r'directory\s+named\s+([\w\-\.]+)',
        r'directory\s+called\s+([\w\-\.]+)',
        r'create\s+(?:a\s+)?(?:folder|directory)\s+([\w\-\.]+)',
        r'make\s+(?:a\s+)?(?:folder|directory)\s+([\w\-\.]+)',
        r'zip\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'send\s+(?:me\s+)?(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'show\s+(?:me\s+)?(?:contents?\s+of\s+)?(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'list\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'open\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'copy\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'move\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'delete\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)\s+folder',
        r'find\s+(?:the\s+)?(?:folder|directory)\s+([\w\-\.]+)',
        r'contents?\s+of\s+(?:the\s+)?(?:my\s+)?([\w\-\.]+)(?:\s+folder)?',
        r'(?:my|the)\s+([\w\-\.]+)\s+folder',
        # Absolute path
        r'(/(?:[\w\-\.]+/)+[\w\-\.]*)',
    ]

    lower = user_input.lower()
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            result = m.group(1).strip().rstrip('/')
            if result and result not in NEVER:
                # Preserve original casing from input
                try:
                    orig_m = re.search(
                        pat.replace('([\\w\\-\\.]+)', '([\\w\\-\\.]+)'),
                        user_input, re.IGNORECASE
                    )
                    if orig_m:
                        return orig_m.group(1).strip().rstrip('/')
                except Exception:
                    pass
                return result
    return None


def infer_folder_op(user_input: str) -> str:
    """
    Detect the folder operation from user text.
    Returns one of: list | zip | create | copy | move | delete | find | info
    Order matters — more specific checks before broader ones.
    """
    lower = user_input.lower()
    # Specific ops first
    if any(k in lower for k in ["how many", "total files", "size of", "stats", "details", "info about"]):
        return "info"
    if any(k in lower for k in ["create", "make a folder", "new folder", "mkdir"]):
        return "create"
    if any(k in lower for k in ["delete", "remove", "trash"]):
        return "delete"
    if any(k in lower for k in ["move", "transfer", "relocate"]):
        return "move"
    if any(k in lower for k in ["copy", "duplicate"]):
        return "copy"
    if any(k in lower for k in ["find", "locate", "where is", "search for folder"]):
        return "find"
    if any(k in lower for k in ["list", "show", "what's in", "whats in", "contents of", "open"]):
        return "list"
    if any(k in lower for k in ["zip", "compress", "archive", "send me", "give me", "download"]):
        return "zip"
    return "info"


# ── Folder finder ─────────────────────────────────────────────────

def find_folder_fast(
    name: str,
    location_hint: str = None,
    timeout_seconds: int = 10,
) -> Optional[str]:
    """
    Find a folder by name. Returns absolute path or None.
    Searches location_hint first if given, then DEFAULT_ROOTS.
    """
    import time
    deadline   = time.time() + timeout_seconds
    name_lower = name.lower()

    # Absolute path given directly
    if os.path.isabs(name) and os.path.isdir(name):
        return name

    def _walk_root(root: str) -> Optional[str]:
        if not os.path.exists(root):
            return None
        # Direct child check
        direct = os.path.join(root, name)
        if os.path.isdir(direct):
            return direct
        try:
            for dirpath, dirs, _ in os.walk(root):
                if time.time() > deadline:
                    return None
                dirs[:] = [
                    d for d in dirs
                    if d not in SKIP_DIRS and not d.startswith('.')
                ]
                for d in dirs:
                    if d.lower() == name_lower:
                        return os.path.join(dirpath, d)
        except PermissionError:
            pass
        return None

    if location_hint:
        return _walk_root(location_hint)

    seen = set()
    for root in DEFAULT_ROOTS:
        root = os.path.realpath(root)
        if root in seen or not os.path.exists(root):
            continue
        seen.add(root)
        found = _walk_root(root)
        if found:
            return found

    return None


# ── Folder operations ─────────────────────────────────────────────

def list_folder(path: str, max_items: int = 50) -> str:
    """
    Return a formatted string listing the contents of a folder.
    Shows files and subdirectories with sizes.
    """
    if not os.path.isdir(path):
        return f"'{path}' is not a valid folder."

    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return f"Permission denied: cannot read '{path}'"

    lines = [f"📁 {path}", f"{'─' * 40}"]
    dirs_count  = 0
    files_count = 0

    for i, entry in enumerate(entries):
        if i >= max_items:
            remaining = len(list(os.scandir(path))) - max_items
            lines.append(f"  ... and {remaining} more items")
            break
        if entry.is_dir():
            dirs_count += 1
            lines.append(f"  📁 {entry.name}/")
        else:
            files_count += 1
            try:
                size = entry.stat().st_size
                size_str = _human_size(size)
            except Exception:
                size_str = "?"
            lines.append(f"  📄 {entry.name}  ({size_str})")

    lines.append(f"{'─' * 40}")
    lines.append(f"  {dirs_count} folder(s),  {files_count} file(s)")
    return "\n".join(lines)


def zip_folder(path: str, output_name: str = None) -> str:
    """
    Zip a folder and save to /tmp/deepagent_files/.
    Returns the zip file path.
    """
    if not os.path.isdir(path):
        raise ValueError(f"'{path}' is not a valid folder.")

    folder_name  = os.path.basename(path.rstrip('/'))
    output_name  = output_name or f"{folder_name}.zip"
    tmp_dir      = Path(tempfile.gettempdir()) / "deepagent_files"
    tmp_dir.mkdir(exist_ok=True)
    zip_path     = str(tmp_dir / output_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            # Skip hidden and junk dirs inside the zip too
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            for file in files:
                abs_path  = os.path.join(root, file)
                arc_name  = os.path.relpath(abs_path, os.path.dirname(path))
                zf.write(abs_path, arc_name)

    return zip_path


def create_folder(name: str, parent: str = None) -> str:
    """
    Create a new folder. Returns the created path.
    parent defaults to cwd if not given.
    """
    parent = parent or os.getcwd()
    # Resolve location keywords
    parent_lower = parent.lower().strip()
    if parent_lower in LOCATION_MAP:
        parent = LOCATION_MAP[parent_lower]

    full_path = os.path.join(parent, name)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def copy_folder(src: str, dest_parent: str) -> str:
    """Copy src folder into dest_parent. Returns new path."""
    name     = os.path.basename(src.rstrip('/'))
    dest     = os.path.join(dest_parent, name)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return dest


def move_folder(src: str, dest_parent: str) -> str:
    """Move src folder into dest_parent. Returns new path."""
    name = os.path.basename(src.rstrip('/'))
    dest = os.path.join(dest_parent, name)
    shutil.move(src, dest)
    return dest


def folder_summary(path: str) -> str:
    """
    Return stats about a folder: total files, total size, file type breakdown.
    """
    if not os.path.isdir(path):
        return f"'{path}' is not a valid folder."

    total_files = 0
    total_size  = 0
    type_counts: dict[str, int] = {}

    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            for f in files:
                total_files += 1
                try:
                    s = os.path.getsize(os.path.join(root, f))
                    total_size += s
                except Exception:
                    pass
                ext = os.path.splitext(f)[1].lower() or "no extension"
                type_counts[ext] = type_counts.get(ext, 0) + 1
    except PermissionError:
        return f"Permission denied: cannot read '{path}'"

    top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]
    type_str  = ", ".join(f"{ext}×{n}" for ext, n in top_types)

    return (
        f"📁 {os.path.basename(path)}\n"
        f"  Path       : {path}\n"
        f"  Total files: {total_files}\n"
        f"  Total size : {_human_size(total_size)}\n"
        f"  Top types  : {type_str or 'none'}"
    )


# ── Helpers ───────────────────────────────────────────────────────

def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def is_folder_request(text: str) -> bool:
    keywords = [
        "folder", "directory", "mkdir", "zip the", "compress the",
        "archive the", "what's in", "whats in", "list the",
        "contents of", "send me the folder", "give me the folder",
    ]
    lower = text.lower()
    return any(k in lower for k in keywords)