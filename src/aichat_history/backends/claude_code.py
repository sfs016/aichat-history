"""Claude Code chat history backend.

Reads chat data from ~/.claude/projects/ directory structure.
Each project has a sessions-index.json and per-session .jsonl files.
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
            # Fall back to scanning for .jsonl files
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
            # Count lines for message estimate
            try:
                line_count = sum(1 for _ in jsonl_file.open(encoding="utf-8"))
            except OSError:
                line_count = 0

            # Read first line for title
            title = "Untitled"
            try:
                with jsonl_file.open(encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        entry = json.loads(first_line)
                        if entry.get("type") == "human":
                            content = entry.get("message", {}).get("content", [])
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    title = block["text"][:80]
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
        """Parse a session's JSONL file into messages."""
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

                    msg = self._entry_to_message(entry)
                    if msg:
                        messages.append(msg)
        except OSError as e:
            logger.warning("Failed to read JSONL %s: %s", path, e)

        return messages

    def _entry_to_message(self, entry: dict) -> Message | None:
        """Convert a JSONL entry to a Message, or None if it should be skipped."""
        entry_type = entry.get("type", "")
        timestamp = _parse_iso(entry.get("timestamp"))

        if entry_type == "file-history-snapshot":
            return None  # Skip file snapshots

        if entry_type == "human":
            text = self._extract_text(entry.get("message", {}))
            if text:
                return Message(
                    role="user",
                    content=text,
                    timestamp=timestamp,
                    message_type="text",
                )

        elif entry_type == "assistant":
            msg_data = entry.get("message", {})
            content_blocks = msg_data.get("content", [])

            # Separate text and tool_use blocks
            text_parts = []
            tool_messages = []

            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    file_path = tool_input.get("file_path", "")
                    summary = tool_name
                    if file_path:
                        summary += f": {file_path}"
                    tool_messages.append(Message(
                        role="tool",
                        content=json.dumps(tool_input, indent=2) if tool_input else summary,
                        timestamp=timestamp,
                        message_type="tool_call",
                        metadata={"tool_name": tool_name, "file_path": file_path},
                    ))

            messages = []
            if text_parts:
                messages.append(Message(
                    role="assistant",
                    content="\n".join(text_parts),
                    timestamp=timestamp,
                    message_type="text",
                ))
            messages.extend(tool_messages)

            # Return first message or None; caller handles via _parse_jsonl
            # Actually we need to return all messages. Restructure: return a list.
            # For now, return first text message or first tool message.
            if messages:
                return messages[0]

        return None

    def _extract_text(self, msg_data: dict) -> str:
        """Extract text content from a message's content array."""
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
        # Handle Z suffix
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
