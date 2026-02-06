"""Tests for export functionality."""

import json
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from aichat_history.core import Message, Session
from aichat_history.export import session_to_json, session_to_markdown
from aichat_history.server import app


@pytest.fixture
def sample_session():
    return Session(
        id="cursor:abc:123",
        workspace_id="abc",
        title="Fix authentication bug",
        message_count=3,
        created=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        updated=datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
        source="cursor",
        project_path="/Users/test/dev/myapp",
    )


@pytest.fixture
def sample_messages():
    return [
        Message(
            role="user",
            content="Fix the login bug in auth.ts",
            timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            message_type="text",
        ),
        Message(
            role="assistant",
            content="I'll fix the authentication bug. Here's the change:\n\n```typescript\nconst token = await validateToken(input);\n```",
            timestamp=datetime(2025, 1, 15, 10, 0, 30, tzinfo=timezone.utc),
            message_type="text",
        ),
        Message(
            role="user",
            content="Looks good, thanks!",
            timestamp=datetime(2025, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
            message_type="text",
        ),
    ]


class TestMarkdownExport:
    def test_produces_valid_markdown(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_session_title(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert "# Fix authentication bug" in result

    def test_includes_metadata(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert "**Project:** /Users/test/dev/myapp" in result
        assert "**Source:** cursor" in result
        assert "**Messages:** 3" in result

    def test_includes_messages_with_roles(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert "## User" in result
        assert "## Assistant" in result
        assert "Fix the login bug" in result
        assert "validateToken" in result

    def test_includes_timestamps(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert "2025-01-15" in result

    def test_preserves_code_fences(self, sample_session, sample_messages):
        result = session_to_markdown(sample_session, sample_messages)
        assert "```typescript" in result

    def test_empty_messages(self, sample_session):
        result = session_to_markdown(sample_session, [])
        assert "# Fix authentication bug" in result
        assert "**Messages:** 3" in result


class TestJsonExport:
    def test_produces_valid_json(self, sample_session, sample_messages):
        result = session_to_json(sample_session, sample_messages)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_includes_session_metadata(self, sample_session, sample_messages):
        result = session_to_json(sample_session, sample_messages)
        data = json.loads(result)
        assert data["session"]["id"] == "cursor:abc:123"
        assert data["session"]["title"] == "Fix authentication bug"
        assert data["session"]["source"] == "cursor"
        assert data["session"]["project_path"] == "/Users/test/dev/myapp"
        assert data["session"]["message_count"] == 3

    def test_includes_messages(self, sample_session, sample_messages):
        result = session_to_json(sample_session, sample_messages)
        data = json.loads(result)
        assert len(data["messages"]) == 3
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"
        assert "Fix the login bug" in data["messages"][0]["content"]

    def test_message_fields(self, sample_session, sample_messages):
        result = session_to_json(sample_session, sample_messages)
        data = json.loads(result)
        msg = data["messages"][0]
        assert "role" in msg
        assert "content" in msg
        assert "timestamp" in msg
        assert "message_type" in msg
        assert "metadata" in msg

    def test_timestamps_are_iso(self, sample_session, sample_messages):
        result = session_to_json(sample_session, sample_messages)
        data = json.loads(result)
        assert data["session"]["created"] == "2025-01-15T10:00:00+00:00"
        assert data["messages"][0]["timestamp"] == "2025-01-15T10:00:00+00:00"

    def test_empty_messages(self, sample_session):
        result = session_to_json(sample_session, [])
        data = json.loads(result)
        assert len(data["messages"]) == 0
        assert data["session"]["title"] == "Fix authentication bug"


@pytest.fixture(autouse=True)
def reset_provider_cache():
    import aichat_history.server as srv
    srv._providers = None
    yield
    srv._providers = None


@pytest.mark.asyncio
async def test_export_md_endpoint(tmp_cursor_workspace, tmp_cursor_global):
    """Test the /api/export endpoint returns markdown."""
    from unittest.mock import patch
    from aichat_history.backends.cursor import CursorProvider

    provider = CursorProvider()
    provider.get_base_path = lambda: tmp_cursor_workspace
    provider.is_available = lambda: True

    with (
        patch("aichat_history.server.get_available_providers", return_value=[provider]),
        patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Get a session ID first
            resp = await client.get("/api/sessions")
            sessions = resp.json()["sessions"]
            assert len(sessions) > 0
            session_id = sessions[0]["id"]

            # Export as markdown
            resp = await client.get(f"/api/export/{session_id}?format=md")
            assert resp.status_code == 200
            assert "text/markdown" in resp.headers.get("content-type", "")
            assert "Content-Disposition" in resp.headers
            assert len(resp.text) > 0


@pytest.mark.asyncio
async def test_export_json_endpoint(tmp_cursor_workspace, tmp_cursor_global):
    """Test the /api/export endpoint returns JSON."""
    from unittest.mock import patch
    from aichat_history.backends.cursor import CursorProvider

    provider = CursorProvider()
    provider.get_base_path = lambda: tmp_cursor_workspace
    provider.is_available = lambda: True

    with (
        patch("aichat_history.server.get_available_providers", return_value=[provider]),
        patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/sessions")
            sessions = resp.json()["sessions"]
            session_id = sessions[0]["id"]

            resp = await client.get(f"/api/export/{session_id}?format=json")
            assert resp.status_code == 200
            assert "application/json" in resp.headers.get("content-type", "")
            data = json.loads(resp.text)
            assert "session" in data
            assert "messages" in data
