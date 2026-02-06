"""OpenCode chat history backend.

Reads chat data from ~/.local/share/opencode/storage/ directory.
Data is organized as: session/ -> message/ -> part/ hierarchy.

Supports two storage versions:
- v1.0 (older): Messages contain only metadata; no part/ directories.
  Content is limited to summary.title on user messages.
- v1.1+ (newer): Full content stored in part/ directories as prt_*.json files.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_opencode_path
from ..core import Message, Session, Workspace
from ..provider import ChatProvider

logger = logging.getLogger(__name__)


class OpenCodeProvider(ChatProvider):
    """Provider for OpenCode chat history."""

    name = "opencode"

    def get_base_path(self) -> Path:
        return get_opencode_path()

    def is_available(self) -> bool:
        return self.get_base_path().is_dir()

    def list_workspaces(self) -> list[Workspace]:
        base = self.get_base_path()
        session_dir = base / "session"
        if not session_dir.is_dir():
            return []

        workspaces = []
        seen_paths = set()

        for project_dir in session_dir.iterdir():
            if not project_dir.is_dir():
                continue

            display_path = self._get_project_display_path(project_dir)
            if display_path in seen_paths:
                continue
            seen_paths.add(display_path)

            workspaces.append(Workspace(
                id=project_dir.name,
                display_path=display_path,
                source="opencode",
            ))

        return workspaces

    def list_sessions(self, workspace_id: str | None = None) -> list[Session]:
        base = self.get_base_path()
        session_dir = base / "session"
        if not session_dir.is_dir():
            return []

        sessions = []

        if workspace_id:
            project_dirs = [session_dir / workspace_id]
        else:
            project_dirs = [d for d in session_dir.iterdir() if d.is_dir()]

        for project_dir in project_dirs:
            if not project_dir.is_dir():
                continue

            for ses_file in project_dir.glob("ses_*.json"):
                session = self._parse_session_file(ses_file, base)
                if session:
                    sessions.append(session)

        return sessions

    def get_session_messages(self, session_id: str) -> list[Message]:
        """Get messages for a session.

        Session IDs are formatted as: opencode:{session_id}
        """
        parts = session_id.split(":", 1)
        if len(parts) < 2 or parts[0] != "opencode":
            return []

        ses_id = parts[1]
        base = self.get_base_path()
        msg_dir = base / "message" / ses_id

        if not msg_dir.is_dir():
            return []

        messages = []
        for msg_file in sorted(msg_dir.glob("msg_*.json")):
            msg = self._parse_message_file(msg_file, base)
            if msg:
                messages.append(msg)

        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return messages

    # ── Private helpers ──────────────────────────────────────────────

    def _get_project_display_path(self, project_dir: Path) -> str:
        """Get display path from the first session file in a project dir."""
        for ses_file in project_dir.glob("ses_*.json"):
            try:
                data = json.loads(ses_file.read_text(encoding="utf-8"))
                directory = data.get("directory")
                if directory:
                    return directory
            except (json.JSONDecodeError, OSError):
                continue
        return project_dir.name

    def _parse_session_file(self, ses_file: Path, base: Path) -> Session | None:
        """Parse a session JSON file into a Session object."""
        try:
            data = json.loads(ses_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read session file %s: %s", ses_file, e)
            return None

        ses_id = data.get("id", ses_file.stem)
        title = data.get("title", "Untitled")
        directory = data.get("directory", "")

        time_data = data.get("time", {})
        created = _ms_to_datetime(time_data.get("created"))
        updated = _ms_to_datetime(time_data.get("updated"))

        # Count messages
        msg_dir = base / "message" / ses_id
        msg_count = 0
        if msg_dir.is_dir():
            msg_count = sum(1 for _ in msg_dir.glob("msg_*.json"))

        return Session(
            id=f"opencode:{ses_id}",
            workspace_id=ses_file.parent.name,
            title=title,
            message_count=msg_count,
            created=created,
            updated=updated,
            source="opencode",
            project_path=directory,
        )

    def _parse_message_file(self, msg_file: Path, base: Path) -> Message | None:
        """Parse a message JSON file and assemble its parts.

        Handles two storage versions:
        - v1.1+: Content in part/ directory (prt_*.json files)
        - v1.0: No parts; only summary.title available for user messages
        """
        try:
            data = json.loads(msg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read message file %s: %s", msg_file, e)
            return None

        msg_id = data.get("id", msg_file.stem)
        role = data.get("role", "user")
        time_data = data.get("time", {})
        timestamp = _ms_to_datetime(time_data.get("created"))

        # Try loading content from parts (v1.1+ format)
        content_parts = []
        message_type = "text"
        metadata = {}

        part_dir = base / "part" / msg_id
        if part_dir.is_dir():
            for part_file in sorted(part_dir.glob("prt_*.json")):
                try:
                    part = json.loads(part_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue

                part_type = part.get("type", "text")

                if part_type == "text":
                    text = part.get("text", "")
                    if text:
                        content_parts.append(text)
                elif part_type == "tool":
                    # v1.1 tool format: {"type":"tool", "tool":"grep", "state":{"input":{}, "output":"..."}}
                    tool_name = part.get("tool", "unknown")
                    state = part.get("state", {})
                    tool_input = state.get("input", {})
                    tool_output = state.get("output", "")
                    status = state.get("status", "")
                    summary = f"[Tool: {tool_name}]"
                    if tool_input:
                        # Show a compact input summary
                        input_summary = ", ".join(
                            f"{k}={v}" for k, v in tool_input.items()
                            if isinstance(v, (str, int, bool)) and str(v)
                        )
                        if input_summary:
                            summary = f"[Tool: {tool_name} ({input_summary})]"
                    content_parts.append(summary)
                    if tool_output:
                        content_parts.append(f"```\n{tool_output}\n```")
                    message_type = "tool_call"
                    metadata["tool_name"] = tool_name
                elif part_type == "patch":
                    content_parts.append("[Patch/Edit]")
                    message_type = "diff"
                elif part_type == "step-start":
                    # Lifecycle marker, skip
                    continue
                else:
                    # Unknown type — try to extract any text
                    text = part.get("text", "")
                    if text:
                        content_parts.append(text)

        content = "\n".join(content_parts) if content_parts else ""

        # Fallback for v1.0: use summary.title if no parts found
        if not content:
            summary = data.get("summary", {})
            if not isinstance(summary, dict):
                summary = {}
            title = summary.get("title", "")
            if title:
                content = title
            elif role == "assistant":
                # For assistant messages with no content, show mode/finish info
                mode = data.get("mode", "")
                finish = data.get("finish", "")
                if mode or finish:
                    parts_info = []
                    if mode:
                        parts_info.append(f"mode: {mode}")
                    if finish:
                        parts_info.append(f"finish: {finish}")
                    content = f"[{', '.join(parts_info)}]"

        return Message(
            role=role,
            content=content,
            timestamp=timestamp,
            message_type=message_type,
            metadata=metadata,
        )


def _ms_to_datetime(ms: int | None) -> datetime | None:
    """Convert millisecond timestamp to datetime, or None."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
