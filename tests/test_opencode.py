"""Tests for the OpenCode backend."""

from unittest.mock import patch

from aichat_history.backends.opencode import OpenCodeProvider


class TestOpenCodeProvider:
    """Tests for OpenCodeProvider with v1.1+ data (parts exist)."""

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
            assert s.message_count == 3
            assert s.source == "opencode"
            assert s.project_path == "/Users/testuser/dev/api-server"
            assert s.created is not None

    def test_list_sessions_by_workspace(self, tmp_opencode_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            sessions = provider.list_sessions(workspace_id="proj1")
            assert len(sessions) == 1

    def test_get_session_messages_text_parts(self, tmp_opencode_dir):
        """Messages with text parts should have content from part files."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("opencode:ses_001")
            assert len(messages) == 3

            # User message with text part
            assert messages[0].role == "user"
            assert "500" in messages[0].content
            assert messages[0].timestamp is not None

            # Assistant message with text part
            assert messages[1].role == "assistant"
            assert "database" in messages[1].content.lower()

    def test_get_session_messages_tool_parts(self, tmp_opencode_dir):
        """Messages with tool parts should show tool name and output."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("opencode:ses_001")
            # msg_003 has a step-start (skipped) and a tool part
            tool_msg = messages[2]
            assert tool_msg.role == "assistant"
            assert "grep" in tool_msg.content.lower()
            assert "SELECT" in tool_msg.content  # tool output should be included
            assert tool_msg.message_type == "tool_call"
            assert tool_msg.metadata.get("tool_name") == "grep"

    def test_step_start_parts_skipped(self, tmp_opencode_dir):
        """step-start parts should be silently skipped."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_dir):
            messages = provider.get_session_messages("opencode:ses_001")
            for msg in messages:
                assert "step-start" not in msg.content
                assert "snapshot" not in msg.content.lower()

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


class TestOpenCodeV1Provider:
    """Tests for OpenCode v1.0 data (no parts, summary-only fallback)."""

    def test_list_sessions_v1(self, tmp_opencode_v1_dir):
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_v1_dir):
            sessions = provider.list_sessions()
            assert len(sessions) == 1
            s = sessions[0]
            assert s.title == "Build login page"
            assert s.message_count == 2

    def test_v1_user_message_shows_summary(self, tmp_opencode_v1_dir):
        """v1.0 user messages should fall back to summary.title."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_v1_dir):
            messages = provider.get_session_messages("opencode:ses_old_001")
            assert len(messages) == 2

            user_msg = messages[0]
            assert user_msg.role == "user"
            assert "login page" in user_msg.content.lower()

    def test_v1_assistant_message_shows_unavailable_notice(self, tmp_opencode_v1_dir):
        """v1.0 assistant messages should show a clear 'content unavailable' notice."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_v1_dir):
            messages = provider.get_session_messages("opencode:ses_old_001")
            asst_msg = messages[1]
            assert asst_msg.role == "assistant"
            # Should show clear notice about v1.0 limitation
            assert "not available" in asst_msg.content.lower()
            assert "v1.0" in asst_msg.content

    def test_v1_messages_not_empty(self, tmp_opencode_v1_dir):
        """No message should have empty content in v1.0 format."""
        provider = OpenCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_opencode_v1_dir):
            messages = provider.get_session_messages("opencode:ses_old_001")
            for msg in messages:
                assert msg.content.strip(), f"Message with role={msg.role} has empty content"
