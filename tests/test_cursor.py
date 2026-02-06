"""Tests for the Cursor backend."""

from unittest.mock import patch

from aichat_history.backends.cursor import CursorProvider


class TestCursorProvider:
    """Tests for CursorProvider."""

    def test_is_available_with_data(self, tmp_cursor_workspace):
        provider = CursorProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_cursor_workspace):
            assert provider.is_available() is True

    def test_is_available_without_data(self, tmp_path):
        provider = CursorProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_path / "nonexistent"):
            assert provider.is_available() is False

    def test_list_workspaces(self, tmp_cursor_workspace):
        provider = CursorProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_cursor_workspace):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 1
            ws = workspaces[0]
            assert ws.id == "abc123hash"
            assert ws.display_path == "/Users/testuser/dev/my-project"
            assert ws.source == "cursor"

    def test_list_sessions(self, tmp_cursor_workspace, tmp_cursor_global):
        provider = CursorProvider()
        with (
            patch.object(provider, "get_base_path", return_value=tmp_cursor_workspace),
            patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
        ):
            sessions = provider.list_sessions()
            # 2 workspace sessions + 1 global session
            assert len(sessions) == 3

            # Check workspace sessions
            ws_sessions = [s for s in sessions if s.workspace_id != "global"]
            assert len(ws_sessions) == 2

            session1 = next(s for s in ws_sessions if "comp-uuid-001" in s.id)
            assert session1.title == "Fix auth bug"
            assert session1.source == "cursor"
            assert session1.project_path == "/Users/testuser/dev/my-project"
            assert session1.created is not None

            session2 = next(s for s in ws_sessions if "comp-uuid-002" in s.id)
            assert session2.title == "Add dark mode"

            # Check global session
            global_sessions = [s for s in sessions if s.workspace_id == "global"]
            assert len(global_sessions) == 1
            assert global_sessions[0].title == "What is Python?"
            assert global_sessions[0].message_count == 4

    def test_list_sessions_by_workspace(self, tmp_cursor_workspace, tmp_cursor_global):
        provider = CursorProvider()
        with (
            patch.object(provider, "get_base_path", return_value=tmp_cursor_workspace),
            patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
        ):
            sessions = provider.list_sessions(workspace_id="abc123hash")
            # Only workspace sessions (global still included from _read_global_sessions)
            ws_sessions = [s for s in sessions if s.workspace_id == "abc123hash"]
            assert len(ws_sessions) == 2

    def test_get_session_messages_workspace(self, tmp_cursor_workspace):
        provider = CursorProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_cursor_workspace):
            messages = provider.get_session_messages("cursor:abc123hash:comp-uuid-001")
            assert len(messages) > 0
            # Should have user prompts
            user_msgs = [m for m in messages if m.role == "user"]
            assert len(user_msgs) > 0
            assert "auth" in user_msgs[0].content.lower() or "login" in user_msgs[0].content.lower()

    def test_get_session_messages_global(self, tmp_cursor_global):
        provider = CursorProvider()
        with patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global):
            messages = provider.get_session_messages("cursor:global:global-tab-001")
            assert len(messages) == 4
            assert messages[0].role == "user"
            assert messages[0].content == "What is Python?"
            assert messages[1].role == "assistant"

    def test_get_session_messages_invalid_id(self):
        provider = CursorProvider()
        messages = provider.get_session_messages("invalid-id")
        assert messages == []

    def test_empty_workspace_skipped(self, tmp_path):
        """Workspaces with no chat data should be silently skipped."""
        ws_storage = tmp_path / "workspaceStorage"
        ws_dir = ws_storage / "empty_workspace"
        ws_dir.mkdir(parents=True)
        (ws_dir / "workspace.json").write_text('{"folder": "file:///tmp/empty"}')

        # Create DB without composerData
        import sqlite3
        db_path = ws_dir / "state.vscdb"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        conn.execute("CREATE TABLE cursorDiskKV (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        conn.commit()
        conn.close()

        provider = CursorProvider()
        with patch.object(provider, "get_base_path", return_value=ws_storage):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 0
