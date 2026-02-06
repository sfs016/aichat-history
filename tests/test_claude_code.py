"""Tests for the Claude Code backend."""

from unittest.mock import patch

from aichat_history.backends.claude_code import ClaudeCodeProvider


class TestClaudeCodeProvider:
    """Tests for ClaudeCodeProvider."""

    def test_is_available_with_data(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            assert provider.is_available() is True

    def test_is_available_without_data(self, tmp_path):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_path / "nonexistent"):
            assert provider.is_available() is False

    def test_list_workspaces(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 1
            ws = workspaces[0]
            assert ws.display_path == "/Users/testuser/dev/myapp"
            assert ws.source == "claude_code"

    def test_list_sessions(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            sessions = provider.list_sessions()
            assert len(sessions) == 2

            s1 = next(s for s in sessions if "session-001" in s.id)
            assert s1.title == "Help me refactor the auth module"
            assert s1.message_count == 5
            assert s1.source == "claude_code"
            assert s1.project_path == "/Users/testuser/dev/myapp"
            assert s1.created is not None
            assert s1.updated is not None

            s2 = next(s for s in sessions if "session-002" in s.id)
            assert s2.title == "Write tests for the API"

    def test_list_sessions_by_workspace(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            sessions = provider.list_sessions(workspace_id="-Users-testuser-dev-myapp")
            assert len(sessions) == 2

    def test_get_session_messages(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            # 5 lines in JSONL, but file-history-snapshot is skipped
            assert len(messages) >= 3

            # First message should be user
            user_msgs = [m for m in messages if m.role == "user"]
            assert len(user_msgs) >= 2
            assert "refactor" in user_msgs[0].content.lower()

            # Should have assistant messages
            assistant_msgs = [m for m in messages if m.role == "assistant"]
            assert len(assistant_msgs) >= 1

    def test_get_session_messages_invalid_id(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages("invalid")
            assert messages == []

    def test_get_session_messages_nonexistent(self, tmp_claude_code_dir):
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages("claude:fake:nonexistent")
            assert messages == []

    def test_display_path_derivation(self, tmp_path):
        """Test that folder names are correctly derived to paths."""
        projects = tmp_path / "projects"
        project_dir = projects / "-Users-alice-projects-webapp"
        project_dir.mkdir(parents=True)

        # No sessions-index.json, so it should derive from folder name
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=projects):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 1
            assert workspaces[0].display_path == "/Users/alice/projects/webapp"
