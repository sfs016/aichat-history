"""Abstract base class for chat history providers."""

from abc import ABC, abstractmethod
from pathlib import Path

from .core import Message, Session, Workspace


class ChatProvider(ABC):
    """Base class for IDE chat history backends.

    Each backend (Cursor, Claude Code, OpenCode) implements this interface
    to provide unified access to chat history data.
    """

    name: str  # "cursor", "claude_code", "opencode"

    @abstractmethod
    def get_base_path(self) -> Path:
        """Return the root directory where this IDE stores chat data."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this IDE's data exists on this machine."""
        ...

    @abstractmethod
    def list_workspaces(self) -> list[Workspace]:
        """Return all workspaces/projects with chat history."""
        ...

    @abstractmethod
    def list_sessions(self, workspace_id: str | None = None) -> list[Session]:
        """Return chat sessions, optionally filtered by workspace."""
        ...

    @abstractmethod
    def get_session_messages(self, session_id: str) -> list[Message]:
        """Return all messages for a given session ID."""
        ...
