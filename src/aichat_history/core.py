"""Core data models for aichat-history."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Workspace:
    """A project/folder that contains chat sessions."""

    id: str
    display_path: str  # e.g. "/Users/farhaj/dev/travel-agency"
    source: str  # "cursor" | "claude_code" | "opencode"


@dataclass
class Session:
    """A single chat conversation."""

    id: str  # namespaced: "cursor:hash:uuid", "claude:uuid", "opencode:ses_xxx"
    workspace_id: str
    title: str  # first prompt or name
    message_count: int
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    source: str = ""
    project_path: str = ""


@dataclass
class Message:
    """A single message within a chat session."""

    role: str  # "user" | "assistant" | "tool" | "thinking" | "error" | "system"
    content: str
    timestamp: Optional[datetime] = None
    message_type: str = "text"  # "text" | "code" | "tool_call" | "tool_result" | "diff" | "thinking"
    metadata: dict = field(default_factory=dict)  # tool name, file path, etc.
