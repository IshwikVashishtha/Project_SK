"""
Shared file utilities for all agents and interfaces.

__FILE__ protocol:
    Any agent that wants to send a file returns:
        __FILE__:/absolute/path/to/file
    The interface layer (Telegram / CLI) detects this and delivers it.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import tempfile
from pathlib import Path

FILE_PREFIX = "__FILE__:"

# Dirs to skip during recursive search
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".nuxt",
    "site-packages", ".cache", ".npm", ".idea", ".vscode",
    "AppData", "snap", "proc", "sys", "dev",
}

# Location keywords → actual directory paths
LOCATION_MAP = {
    "desktop":       os.path.expanduser("~/Desktop"),
    "documents":     os.path.expanduser("~/Documents"),
    "downloads":     os.path.expanduser("~/Downloads"),
    "pictures":      os.path.expanduser("~/Pictures"),
    "music":         os.path.expanduser("~/Music"),
    "videos":        os.path.expanduser("~/Videos"),
    "home":          os.path.expanduser("~"),
    "projects":      os.path.expanduser("~/Projects"),
    "project":       os.path.expanduser("~/Projects"),
    "code":          os.path.expanduser("~/code"),
    "tmp":           "/tmp",
    "temp":          tempfile.gettempdir(),
    "current":       os.getcwd(),
    "here":          os.getcwd(),
}

# Default search order when no location hint given
DEFAULT_ROOTS = [
    os.getcwd(),
    tempfile.gettempdir(),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Projects"),
    os.path.expanduser("~/projects"),
    os.path.expanduser("~/code"),
    os.path.expanduser("~/Code"),
    os.path.expanduser("~"),
]


# ── Protocol helpers ──────────────────────────────────────────────

def make_file_response(path: str) -> str:
    return f"{FILE_PREFIX}{path}"

def is_file_response(text: str) -> bool:
    return isinstance(text, str) and text.startswith(FILE_PREFIX)

def extract_path(response: str) -> str:
    return response[len(FILE_PREFIX):].strip()

def save_temp_file(content: str, filename: str) -> str:
    tmp_dir = Path(tempfile.gettempdir()) / "deepagent_files"
    tmp_dir.mkdir(exist_ok=True)
    path = tmp_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── Query parsing ─────────────────────────────────────────────────

def infer_filename(user_input: str) -> str | None:
    """
    Extract filename from natural language.
    Handles both extension-bearing and extensionless filenames.
    """
    patterns = [
        # explicit keywords + name with extension
        r'named\s+([\w\-\.\/]+\.\w+)',
        r'called\s+([\w\-\.\/]+\.\w+)',
        r'file\s+([\w\-\.\/]+\.\w+)',
        r'send\s+(?:me\s+)?([\w\-\.\/]+\.\w+)',
        r'get\s+(?:me\s+)?([\w\-\.\/]+\.\w+)',
        r'find\s+(?:the\s+)?(?:file\s+)?([\w\-\.\/]+\.\w+)',
        r'open\s+([\w\-\.\/]+\.\w+)',
        r'read\s+(?:the\s+)?([\w\-\.\/]+\.\w+)',
        r'give\s+me\s+(?:the\s+)?([\w\-\.\/]+\.\w+)',
        # bare extension match
        r'\b([\w\-]+\.(csv|txt|json|md|py|pdf|xlsx|docx|log|yaml|yml|html|xml|zip|png|jpg|jpeg|sh|env|toml|ini|cfg))\b',
        # extensionless: "file named myfile" or "file called myfile"
        r'file\s+named\s+([\w\-\.]+)',
        r'file\s+called\s+([\w\-\.]+)',
        # absolute path
        r'(/(?:[\w\-\.]+/)*[\w\-\.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, user_input, re.IGNORECASE)
        if m:
            result = m.group(1).strip()
            # Skip if it matched a location word like "desktop"
            if result.lower() not in LOCATION_MAP:
                return result
    return None


def infer_location(user_input: str) -> str | None:
    """
    Extract a specific directory hint from the message.
    e.g. "from Desktop" → ~/Desktop
         "in Downloads"  → ~/Downloads
         "on my desktop" → ~/Desktop
    """
    lower = user_input.lower()
    # Check location keywords
    for keyword, path in LOCATION_MAP.items():
        # Match "from <kw>", "in <kw>", "on <kw>", "at <kw>", or just "<kw>"
        if re.search(rf'\b(from|in|on|at|inside)?\s*{keyword}\b', lower):
            return path  # return even if dir doesn't exist; finder handles missing dir
    # Check for explicit path in message
    m = re.search(r'(/(?:[\w\-\.]+/)+)', user_input)
    if m and os.path.isdir(m.group(1)):
        return m.group(1)
    return None


def is_file_request(text: str) -> bool:
    keywords = [
        "send me", "send the file", "send a file",
        "give me the file", "get me", "find the file",
        "find file", "i want a file", "i need a file",
        "create a file", "make a file", "generate a file",
        "export", "save as", "write to file", "download",
        "open the file", "read the file", "from desktop",
        "from documents", "from downloads",
    ]
    lower = text.lower()
    return any(k in lower for k in keywords)


# ── File finder ───────────────────────────────────────────────────

def find_file_fast(
    name: str,
    location_hint: str = None,
    timeout_seconds: int = 10,
) -> str | None:
    """
    Find a file by name.

    If location_hint is given (e.g. ~/Desktop), searches ONLY there first.
    Falls back to DEFAULT_ROOTS if not found in the hint location.
    Skips SKIP_DIRS and stops after timeout_seconds.
    """
    import time
    deadline   = time.time() + timeout_seconds
    name_lower = name.lower()

    # 1. Absolute path handed directly
    if os.path.isabs(name) and os.path.exists(name):
        return name

    def _walk_root(root: str) -> str | None:
        if not os.path.exists(root):
            return None
        # Direct child first (fastest)
        direct = os.path.join(root, name)
        if os.path.exists(direct):
            return direct
        # Recursive
        try:
            for dirpath, dirs, files in os.walk(root):
                if time.time() > deadline:
                    return None
                dirs[:] = [
                    d for d in dirs
                    if d not in SKIP_DIRS and not d.startswith('.')
                ]
                for f in files:
                    if f.lower() == name_lower:
                        return os.path.join(dirpath, f)
        except PermissionError:
            pass
        return None

    # 2. Search location hint first (user said "from Desktop" etc.)
    if location_hint:
        found = _walk_root(location_hint)
        if found:
            return found
        # Hint given but not found there — don't fall through silently,
        # return None so FileAgent can give a specific error message
        return None

    # 3. No hint — search default roots in priority order
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