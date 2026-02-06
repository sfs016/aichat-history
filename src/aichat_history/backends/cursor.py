"""Cursor IDE chat history backend.

Reads chat data from Cursor's SQLite databases (state.vscdb) in both
workspace-level and global storage locations. All database access is read-only.
"""

import json
import logging
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_cursor_global_path, get_cursor_workspace_path
from ..core import Message, Session, Workspace
from ..provider import ChatProvider

logger = logging.getLogger(__name__)


class CursorProvider(ChatProvider):
    """Provider for Cursor IDE chat history."""

    name = "cursor"

    def get_base_path(self) -> Path:
        return get_cursor_workspace_path()

    def is_available(self) -> bool:
        return self.get_base_path().is_dir()

    def list_workspaces(self) -> list[Workspace]:
        base = self.get_base_path()
        if not base.is_dir():
            return []

        workspaces = []
        for ws_dir in base.iterdir():
            if not ws_dir.is_dir():
                continue

            db_path = ws_dir / "state.vscdb"
            if not db_path.exists():
                continue

            # Read workspace.json for the project path
            display_path = self._read_workspace_path(ws_dir)
            if not display_path:
                continue

            # Check if there's any chat data
            if not self._has_chat_data(db_path):
                continue

            workspaces.append(Workspace(
                id=ws_dir.name,
                display_path=display_path,
                source="cursor",
            ))

        return workspaces

    def list_sessions(self, workspace_id: str | None = None) -> list[Session]:
        base = self.get_base_path()
        if not base.is_dir():
            return []

        sessions = []

        if workspace_id:
            ws_dirs = [base / workspace_id]
        else:
            ws_dirs = [d for d in base.iterdir() if d.is_dir()]

        for ws_dir in ws_dirs:
            if not ws_dir.is_dir():
                continue
            db_path = ws_dir / "state.vscdb"
            if not db_path.exists():
                continue

            display_path = self._read_workspace_path(ws_dir)
            if not display_path:
                continue

            ws_sessions = self._read_sessions_from_db(db_path, ws_dir.name, display_path)
            sessions.extend(ws_sessions)

        # Also read global storage sessions
        sessions.extend(self._read_global_sessions())

        return sessions

    def get_session_messages(self, session_id: str) -> list[Message]:
        """Get messages for a session.

        Session IDs are formatted as:
        - cursor:{workspace_hash}:{composer_id} (workspace sessions)
        - cursor:global:{tab_id} (global sessions)
        """
        parts = session_id.split(":", 2)
        if len(parts) < 3 or parts[0] != "cursor":
            return []

        if parts[1] == "global":
            return self._get_global_messages(parts[2])
        else:
            workspace_hash = parts[1]
            composer_id = parts[2]
            return self._get_workspace_messages(workspace_hash, composer_id)

    # ── Private helpers ──────────────────────────────────────────────

    def _read_workspace_path(self, ws_dir: Path) -> str | None:
        """Extract the project path from workspace.json."""
        ws_json = ws_dir / "workspace.json"
        if not ws_json.exists():
            return None
        try:
            data = json.loads(ws_json.read_text(encoding="utf-8"))
            folder_uri = data.get("folder", "")
            if folder_uri.startswith("file://"):
                return urllib.parse.unquote(folder_uri[7:])
            return folder_uri or None
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read workspace.json in %s: %s", ws_dir, e)
            return None

    def _has_chat_data(self, db_path: Path) -> bool:
        """Check if a workspace database contains any chat data."""
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM ItemTable WHERE key = 'composer.composerData' LIMIT 1"
            )
            has_data = cur.fetchone() is not None
            conn.close()
            return has_data
        except (sqlite3.Error, OSError) as e:
            logger.debug("Cannot check chat data in %s: %s", db_path, e)
            return False

    def _query_item_table(self, db_path: Path, key: str) -> str | None:
        """Read a single key from the ItemTable."""
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT value FROM ItemTable WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            if row:
                val = row[0]
                return val if isinstance(val, str) else val.decode("utf-8", errors="replace")
            return None
        except (sqlite3.Error, OSError) as e:
            logger.warning("Failed to read key '%s' from %s: %s", key, db_path, e)
            return None

    def _read_sessions_from_db(
        self, db_path: Path, workspace_hash: str, display_path: str
    ) -> list[Session]:
        """Extract session metadata from a workspace database."""
        raw = self._query_item_table(db_path, "composer.composerData")
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Corrupt composerData in %s: %s", db_path, e)
            return []

        composers = data.get("allComposers", [])
        sessions = []

        # Also get prompts and generations counts for message estimation
        prompts = self._read_prompts(db_path)
        generations = self._read_generations(db_path)

        for comp in composers:
            composer_id = comp.get("composerId", "")
            if not composer_id:
                continue

            name = comp.get("name", "").strip()
            created_ms = comp.get("createdAt")
            updated_ms = comp.get("lastUpdatedAt")

            # Estimate message count from generations in this time range
            msg_count = self._count_messages_in_range(
                generations, created_ms, updated_ms
            )

            created = _ms_to_datetime(created_ms)
            updated = _ms_to_datetime(updated_ms)

            title = name or _truncate(prompts[0] if prompts else "Untitled", 80)

            sessions.append(Session(
                id=f"cursor:{workspace_hash}:{composer_id}",
                workspace_id=workspace_hash,
                title=title,
                message_count=msg_count,
                created=created,
                updated=updated,
                source="cursor",
                project_path=display_path,
            ))

        return sessions

    def _read_prompts(self, db_path: Path) -> list[str]:
        """Read user prompts from aiService.prompts."""
        raw = self._query_item_table(db_path, "aiService.prompts")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return [
                p.get("text", "") for p in data
                if isinstance(p, dict) and p.get("text")
            ]
        except json.JSONDecodeError:
            return []

    def _read_generations(self, db_path: Path) -> list[dict]:
        """Read generation metadata from aiService.generations."""
        raw = self._query_item_table(db_path, "aiService.generations")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return [g for g in data if isinstance(g, dict)]
        except json.JSONDecodeError:
            return []

    def _count_messages_in_range(
        self,
        generations: list[dict],
        start_ms: int | None,
        end_ms: int | None,
    ) -> int:
        """Count generations that fall within a session's time range."""
        if not generations:
            return 0
        if start_ms is None and end_ms is None:
            return len(generations)

        count = 0
        for gen in generations:
            ts = gen.get("unixMs")
            if ts is None:
                continue
            if start_ms is not None and ts < start_ms:
                continue
            if end_ms is not None and ts > end_ms:
                continue
            count += 1
        return count

    def _get_workspace_messages(
        self, workspace_hash: str, composer_id: str
    ) -> list[Message]:
        """Get messages for a workspace-level session."""
        db_path = self.get_base_path() / workspace_hash / "state.vscdb"
        if not db_path.exists():
            return []

        # Get composer time range
        raw = self._query_item_table(db_path, "composer.composerData")
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        # Find the target composer
        target = None
        for comp in data.get("allComposers", []):
            if comp.get("composerId") == composer_id:
                target = comp
                break
        if not target:
            return []

        start_ms = target.get("createdAt")
        end_ms = target.get("lastUpdatedAt")

        # Read prompts and generations
        prompts = self._read_prompts(db_path)
        generations = self._read_generations(db_path)

        # Correlate by chronological position:
        # Filter generations to this session's time range
        session_gens = []
        for gen in generations:
            ts = gen.get("unixMs")
            if ts is None:
                continue
            if start_ms is not None and ts < start_ms:
                continue
            if end_ms is not None and ts > end_ms:
                continue
            session_gens.append(gen)
        session_gens.sort(key=lambda g: g.get("unixMs", 0))

        # Match prompts to generations chronologically
        # Since prompts and generations aren't 1:1, we interleave them
        messages = []

        # Get the indices of generations that are "composer" type
        composer_gens = [g for g in session_gens if g.get("type") == "composer"]

        # Use generation timestamps to anchor the timeline
        # Interleave user prompts before assistant responses
        prompt_idx = 0
        for gen in composer_gens:
            ts = _ms_to_datetime(gen.get("unixMs"))

            # Add a user prompt if available
            if prompt_idx < len(prompts):
                messages.append(Message(
                    role="user",
                    content=prompts[prompt_idx],
                    timestamp=ts,
                    message_type="text",
                ))
                prompt_idx += 1

            # Add assistant response (we only have summaries)
            desc = gen.get("textDescription", "")
            if desc:
                messages.append(Message(
                    role="assistant",
                    content=desc,
                    timestamp=ts,
                    message_type="text",
                ))

        # Any remaining prompts
        while prompt_idx < len(prompts):
            messages.append(Message(
                role="user",
                content=prompts[prompt_idx],
                message_type="text",
            ))
            prompt_idx += 1

        return messages

    def _read_global_sessions(self) -> list[Session]:
        """Read sessions from global storage chatdata."""
        global_db = get_cursor_global_path()
        if not global_db.exists():
            return []

        raw = self._query_item_table(
            global_db, "workbench.panel.aichat.view.aichat.chatdata"
        )
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        sessions = []
        for tab in data.get("tabs", []):
            tab_id = tab.get("tabId", "")
            bubbles = tab.get("bubbles", [])
            if not tab_id or not bubbles:
                continue

            # Derive title from first user bubble
            title = "Chat"
            for b in bubbles:
                if b.get("type") == "user":
                    title = _truncate(b.get("text", "Chat"), 80)
                    break

            sessions.append(Session(
                id=f"cursor:global:{tab_id}",
                workspace_id="global",
                title=title,
                message_count=len(bubbles),
                source="cursor",
                project_path="(global)",
            ))

        return sessions

    def _get_global_messages(self, tab_id: str) -> list[Message]:
        """Get messages from a global storage chat tab."""
        global_db = get_cursor_global_path()
        if not global_db.exists():
            return []

        raw = self._query_item_table(
            global_db, "workbench.panel.aichat.view.aichat.chatdata"
        )
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        for tab in data.get("tabs", []):
            if tab.get("tabId") != tab_id:
                continue

            messages = []
            for bubble in tab.get("bubbles", []):
                bubble_type = bubble.get("type", "")
                text = bubble.get("text", "")
                role = "user" if bubble_type == "user" else "assistant"
                messages.append(Message(
                    role=role,
                    content=text,
                    message_type="text",
                ))
            return messages

        return []


def _ms_to_datetime(ms: int | None) -> datetime | None:
    """Convert millisecond timestamp to datetime, or None."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
