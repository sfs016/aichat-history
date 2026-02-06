"""Platform-aware path resolution for IDE data directories."""

import os
import sys
from pathlib import Path


def get_cursor_workspace_path() -> Path:
    """Return the path to Cursor's workspaceStorage directory."""
    env = os.environ.get("AICHAT_CURSOR_PATH")
    if env:
        return Path(env)

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    elif sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Cursor" / "User" / "workspaceStorage"
    else:  # Linux
        return Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage"


def get_cursor_global_path() -> Path:
    """Return the path to Cursor's globalStorage state.vscdb."""
    env = os.environ.get("AICHAT_CURSOR_PATH")
    if env:
        # If custom path set, assume it's the parent and globalStorage is alongside workspaceStorage
        return Path(env).parent / "globalStorage" / "state.vscdb"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    elif sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    else:  # Linux
        return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def get_claude_code_path() -> Path:
    """Return the path to Claude Code's projects directory."""
    env = os.environ.get("AICHAT_CLAUDE_PATH")
    if env:
        return Path(env)

    return Path.home() / ".claude" / "projects"


def get_opencode_path() -> Path:
    """Return the path to OpenCode's storage directory."""
    env = os.environ.get("AICHAT_OPENCODE_PATH")
    if env:
        return Path(env)

    if sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", "")) / ".local" / "share" / "opencode" / "storage"
    else:  # macOS and Linux
        return Path.home() / ".local" / "share" / "opencode" / "storage"
