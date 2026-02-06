"""Claude Code chat history backend.

Reads chat data from ~/.claude/projects/ directory structure.
Each project has a sessions-index.json and per-session .jsonl files.

JSONL entry types:
- "user" or "human": User messages. Content can be a string or array of blocks.
  May also contain tool_result blocks (responses from tool execution).
- "assistant": AI responses. Content is an array of text and/or tool_use blocks.
  A single JSONL line can produce multiple messages (text + tool calls).
- "file-history-snapshot": Skipped.
- "progress", "system": Skipped (metadata only).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_claude_code_path
from ..core import Message, Session, Workspace
from ..provider import ChatProvider

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(ChatProvider):
    """Provider for Claude Code chat history."""

    name = "claude_code"

    def get_base_path(self) -> Path:
        return get_claude_code_path()

    def is_available(self) -> bool:
        return self.get_base_path().is_dir()

    def list_workspaces(self) -> list[Workspace]:
        base = self.get_base_path()
        if not base.is_dir():
            return []

        workspaces = []
        for project_dir in base.iterdir():
            if not project_dir.is_dir():
                continue

            display_path = self._resolve_display_path(project_dir)
            workspaces.append(Workspace(
                id=project_dir.name,
                display_path=display_path,
                source="claude_code",
            ))

        return workspaces

    def list_sessions(self, workspace_id: str | None = None) -> list[Session]:
        base = self.get_base_path()
        if not base.is_dir():
            return []

        sessions = []

        if workspace_id:
            project_dirs = [base / workspace_id]
        else:
            project_dirs = [d for d in base.iterdir() if d.is_dir()]

        for project_dir in project_dirs:
            if not project_dir.is_dir():
                continue
            sessions.extend(self._read_project_sessions(project_dir))

        return sessions

    def get_session_messages(self, session_id: str) -> list[Message]:
        """Get messages for a session.

        Session IDs are formatted as: claude:{project_dir_name}:{session_uuid}
        """
        parts = session_id.split(":", 2)
        if len(parts) < 3 or parts[0] != "claude":
            return []

        project_name = parts[1]
        session_uuid = parts[2]

        jsonl_path = self.get_base_path() / project_name / f"{session_uuid}.jsonl"
        if not jsonl_path.exists():
            return []

        return self._parse_jsonl(jsonl_path)

    # ── Private helpers ──────────────────────────────────────────────

    def _resolve_display_path(self, project_dir: Path) -> str:
        """Resolve the display path for a project directory.

        First checks sessions-index.json for projectPath,
        then falls back to deriving from directory name.
        """
        index_path = project_dir / "sessions-index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    path = data[0].get("projectPath")
                    if path:
                        return path
            except (json.JSONDecodeError, OSError):
                pass

        # Derive from folder name: -Users-farhaj-dev-foo -> /Users/farhaj/dev/foo
        name = project_dir.name
        if name.startswith("-"):
            return name.replace("-", "/")
        return name

    def _read_project_sessions(self, project_dir: Path) -> list[Session]:
        """Read sessions from a project's sessions-index.json."""
        index_path = project_dir / "sessions-index.json"
        if not index_path.exists():
            return self._scan_jsonl_sessions(project_dir)

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read sessions-index.json in %s: %s", project_dir, e)
            return []

        if not isinstance(data, list):
            return []

        display_path = self._resolve_display_path(project_dir)
        sessions = []

        for entry in data:
            if not isinstance(entry, dict):
                continue

            session_id = entry.get("sessionId", "")
            if not session_id:
                continue

            title = entry.get("firstPrompt") or entry.get("summary") or "Untitled"
            title = title[:80]

            created = _parse_iso(entry.get("created"))
            modified = _parse_iso(entry.get("modified"))
            msg_count = entry.get("messageCount", 0)
            project_path = entry.get("projectPath", display_path)

            sessions.append(Session(
                id=f"claude:{project_dir.name}:{session_id}",
                workspace_id=project_dir.name,
                title=title,
                message_count=msg_count,
                created=created,
                updated=modified,
                source="claude_code",
                project_path=project_path,
            ))

        return sessions

    def _scan_jsonl_sessions(self, project_dir: Path) -> list[Session]:
        """Scan for .jsonl files when no index exists."""
        sessions = []
        display_path = self._resolve_display_path(project_dir)

        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            try:
                line_count = sum(1 for _ in jsonl_file.open(encoding="utf-8"))
            except OSError:
                line_count = 0

            title = "Untitled"
            try:
                with jsonl_file.open(encoding="utf-8") as f:
                    for raw_line in f:
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        entry = json.loads(raw_line)
                        if entry.get("type") in ("human", "user"):
                            text = self._extract_user_text(entry)
                            if text:
                                title = text[:80]
                                break
            except (json.JSONDecodeError, OSError):
                pass

            sessions.append(Session(
                id=f"claude:{project_dir.name}:{session_id}",
                workspace_id=project_dir.name,
                title=title,
                message_count=line_count,
                source="claude_code",
                project_path=display_path,
            ))

        return sessions

    def _parse_jsonl(self, path: Path) -> list[Message]:
        """Parse a session's JSONL file into messages.

        Each JSONL line can produce zero, one, or multiple Message objects.
        """
        messages = []

        try:
            with path.open(encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.debug("Bad JSON at %s:%d: %s", path, line_num, e)
                        continue

                    messages.extend(self._entry_to_messages(entry))
        except OSError as e:
            logger.warning("Failed to read JSONL %s: %s", path, e)

        return messages

    def _entry_to_messages(self, entry: dict) -> list[Message]:
        """Convert a JSONL entry to a list of Messages.

        Returns an empty list for entries that should be skipped.
        A single entry can produce multiple messages (e.g. assistant text + tool calls).
        """
        entry_type = entry.get("type", "")
        timestamp = _parse_iso(entry.get("timestamp"))

        # Skip non-message entry types
        if entry_type in (
            "file-history-snapshot", "progress", "system",
            "summary", "queue-operation",
        ):
            return []

        if entry_type in ("human", "user"):
            return self._parse_user_entry(entry, timestamp)

        if entry_type == "assistant":
            return self._parse_assistant_entry(entry, timestamp)

        return []

    def _parse_user_entry(self, entry: dict, timestamp: datetime | None) -> list[Message]:
        """Parse a user/human JSONL entry.

        User entries can contain:
        - Plain text (user prompts)
        - tool_result blocks (responses from tool execution)
        - A mix of both
        """
        msg_data = entry.get("message", {})
        content = msg_data.get("content", [])

        # Simple string content
        if isinstance(content, str):
            if content.strip():
                return [Message(
                    role="user",
                    content=content,
                    timestamp=timestamp,
                    message_type="text",
                )]
            return []

        messages = []
        text_parts = []

        for block in content:
            if not isinstance(block, dict):
                if isinstance(block, str) and block.strip():
                    text_parts.append(block)
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                if text.strip():
                    text_parts.append(text)

            elif block_type == "tool_result":
                # Tool execution result — show as tool message
                tool_content = block.get("content", "")
                if isinstance(tool_content, list):
                    # Content can be array of blocks (text, image, etc.)
                    parts = []
                    for sub in tool_content:
                        if isinstance(sub, dict):
                            sub_type = sub.get("type", "")
                            if sub_type == "text":
                                parts.append(sub.get("text", ""))
                            elif sub_type == "image":
                                parts.append("[Image]")
                            else:
                                # Unknown block type — try text field
                                text = sub.get("text", "")
                                if text:
                                    parts.append(text)
                        elif isinstance(sub, str):
                            parts.append(sub)
                    tool_content = "\n".join(parts)

                is_error = block.get("is_error", False)
                messages.append(Message(
                    role="tool" if not is_error else "error",
                    content=str(tool_content) if tool_content else "(empty result)",
                    timestamp=timestamp,
                    message_type="tool_result",
                    metadata={"tool_use_id": block.get("tool_use_id", "")},
                ))

        # Emit text parts as user message (if any non-tool-result text)
        if text_parts:
            messages.insert(0, Message(
                role="user",
                content="\n".join(text_parts),
                timestamp=timestamp,
                message_type="text",
            ))

        return messages

    def _parse_assistant_entry(self, entry: dict, timestamp: datetime | None) -> list[Message]:
        """Parse an assistant JSONL entry.

        Assistant entries have content arrays with text and/or tool_use blocks.
        All blocks from a single entry are returned as separate messages.
        """
        msg_data = entry.get("message", {})
        content_blocks = msg_data.get("content", [])

        if isinstance(content_blocks, str):
            if content_blocks.strip():
                return [Message(
                    role="assistant",
                    content=content_blocks,
                    timestamp=timestamp,
                    message_type="text",
                )]
            return []

        messages = []
        text_parts = []

        for block in content_blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                if text.strip():
                    text_parts.append(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                file_path = tool_input.get("file_path", tool_input.get("path", ""))
                command = tool_input.get("command", "")

                # Build a readable summary
                summary_parts = [tool_name]
                if file_path:
                    summary_parts.append(file_path)
                elif command:
                    cmd_short = command[:100] + ("..." if len(command) > 100 else "")
                    summary_parts.append(cmd_short)

                content = ": ".join(summary_parts)

                messages.append(Message(
                    role="tool",
                    content=content,
                    timestamp=timestamp,
                    message_type="tool_call",
                    metadata={
                        "tool_name": tool_name,
                        "file_path": file_path,
                        "tool_use_id": block.get("id", ""),
                    },
                ))

            elif block_type == "thinking":
                text = block.get("thinking", "")
                if text.strip():
                    messages.append(Message(
                        role="thinking",
                        content=text,
                        timestamp=timestamp,
                        message_type="thinking",
                    ))

        # Insert text message at the beginning (before tool calls)
        if text_parts:
            messages.insert(0, Message(
                role="assistant",
                content="\n".join(text_parts),
                timestamp=timestamp,
                message_type="text",
            ))

        return messages

    def _extract_user_text(self, entry: dict) -> str:
        """Extract plain text content from a user entry (ignoring tool_results)."""
        msg_data = entry.get("message", {})
        content = msg_data.get("content", [])
        if isinstance(content, str):
            return content

        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
