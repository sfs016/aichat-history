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
            assert s1.message_count == 8
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

    def test_get_session_messages_returns_all_types(self, tmp_claude_code_dir):
        """Verify all message types are returned: user, assistant, tool, thinking."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            roles = [m.role for m in messages]

            # Should have user messages
            assert "user" in roles
            # Should have assistant text messages
            assert "assistant" in roles
            # Should have tool call messages
            assert "tool" in roles
            # Should have thinking blocks
            assert "thinking" in roles

    def test_user_prompts_have_content(self, tmp_claude_code_dir):
        """User text messages should have actual content."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            user_msgs = [m for m in messages if m.role == "user"]
            assert len(user_msgs) >= 2
            assert "refactor" in user_msgs[0].content.lower()
            assert "split" in user_msgs[1].content.lower()

    def test_assistant_text_has_content(self, tmp_claude_code_dir):
        """Assistant text messages should have full content."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            assistant_msgs = [m for m in messages if m.role == "assistant"]
            assert len(assistant_msgs) >= 2
            assert "refactor" in assistant_msgs[0].content.lower()

    def test_tool_use_has_metadata(self, tmp_claude_code_dir):
        """Tool call messages should have tool_name in metadata."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            tool_msgs = [m for m in messages if m.role == "tool"]
            assert len(tool_msgs) >= 2  # Read + Edit + Bash

            tool_names = [m.metadata.get("tool_name") for m in tool_msgs]
            assert "Read" in tool_names
            assert "Edit" in tool_names

    def test_tool_results_are_separate(self, tmp_claude_code_dir):
        """Tool results from 'user' entries should be separate tool messages."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            tool_results = [m for m in messages if m.message_type == "tool_result"]
            assert len(tool_results) >= 2
            # First tool result should contain the auth code
            assert "authenticate" in tool_results[0].content or "File edited" in tool_results[1].content

    def test_thinking_blocks_extracted(self, tmp_claude_code_dir):
        """Thinking blocks should be extracted as separate messages."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            thinking_msgs = [m for m in messages if m.role == "thinking"]
            assert len(thinking_msgs) >= 1
            assert "split" in thinking_msgs[0].content.lower() or "validation" in thinking_msgs[0].content.lower()

    def test_skipped_entries(self, tmp_claude_code_dir):
        """file-history-snapshot and progress entries should be skipped."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            # No message should contain snapshot or progress data
            for m in messages:
                assert m.message_type != "file-history-snapshot"
                assert "progress" not in m.content.lower() or m.role != "system"

    def test_message_count_is_comprehensive(self, tmp_claude_code_dir):
        """The total number of messages should reflect all content blocks."""
        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=tmp_claude_code_dir):
            messages = provider.get_session_messages(
                "claude:-Users-testuser-dev-myapp:session-001"
            )
            # From our fixture:
            # Line 1: user text -> 1 msg
            # Line 2: assistant text + tool_use -> 2 msgs
            # Line 3: tool_result -> 1 msg
            # Line 4: thinking + text + tool_use -> 3 msgs
            # Line 5: tool_result -> 1 msg
            # Line 6: file-history-snapshot -> skipped
            # Line 7: user text -> 1 msg
            # Line 8: tool_use only -> 1 msg
            # Line 9: progress -> skipped
            # Total: 10 messages
            assert len(messages) == 10

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

        provider = ClaudeCodeProvider()
        with patch.object(provider, "get_base_path", return_value=projects):
            workspaces = provider.list_workspaces()
            assert len(workspaces) == 1
            assert workspaces[0].display_path == "/Users/alice/projects/webapp"
