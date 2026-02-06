"""Tests for the OpenCode backend."""

from unittest.mock import patch

from aichat_history.backends.opencode import OpenCodeProvider


class TestOpenCodeProvider:
    """Tests for OpenCodeProvider."""

    def test_is_available_with_data(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            assert provider.is_available() is True

    def test_is_available_without_data(self, tmp_path):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_path / "nonexistent"):
            assert provider.is_available() is False

    def test_list_workspaces(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 1
            ws = workspaces[0]
            assert ws.display_path == "/Users/testuser/dev/api-server"
            assert ws.source == "opencode"

    def test_list_sessions(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            sessions = provider.list_sessions()
            assert len(sessions) == 1
            s = sessions[0]
            assert s.id == "opencode:ses_001"
            assert s.title == "Debug API endpoint"
            assert s.message_count == 2
            assert s.source == "opencode"
            assert s.project_path == "/Users/testuser/dev/api-server"
            assert s.created is not None

    def test_list_sessions_by_workspace(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            sessions = provider.list_sessions(workspace_id="proj1")
            assert len(sessions) == 1

    def test_get_session_messages(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("opencode:ses_001")
            assert len(messages) == 2

            assert messages[0].role == "user"
            assert "500" in messages[0].content
            assert messages[0].timestamp is not None

            assert messages[1].role == "assistant"
            assert "database" in messages[1].content.lower()

    def test_get_session_messages_invalid_id(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("invalid")
            assert messages == []

    def test_get_session_messages_nonexistent(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("opencode:nonexistent_session")
            assert messages == []
