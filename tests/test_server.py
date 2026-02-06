"""Tests for the FastAPI server."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from aichat_history.backends.cursor import CursorProvider
from aichat_history.server import app, _providers


@pytest.fixture(autouse=True)
def reset_provider_cache():
    """Reset the provider cache before each test."""
    import aichat_history.server as srv
    srv._providers = None
    yield
    srv._providers = None


@pytest.fixture
def cursor_provider(tmp_cursor_workspace, tmp_cursor_global):
    """Create a CursorProvider pointed at test fixtures."""
    provider = CursorProvider()
    original_base = provider.get_base_path
    original_global = None

    # Patch the base path
    provider.get_base_path = lambda: tmp_cursor_workspace
    provider.is_available = lambda: True
    return provider


@pytest.mark.asyncio
async def test_get_sources(cursor_provider):
    with patch("aichat_history.server.get_available_providers", return_value=[cursor_provider]):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/sources")
            assert resp.status_code == 200
            data = resp.json()
            assert "cursor" in data


@pytest.mark.asyncio
async def test_get_sessions(cursor_provider, tmp_cursor_global):
    with (
        patch("aichat_history.server.get_available_providers", return_value=[cursor_provider]),
        patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert "sessions" in data
            assert "total" in data
            assert data["total"] > 0
            # Each session should have expected fields
            for session in data["sessions"]:
                assert "id" in session
                assert "title" in session
                assert "source" in session


@pytest.mark.asyncio
async def test_get_sessions_with_search(cursor_provider, tmp_cursor_global):
    with (
        patch("aichat_history.server.get_available_providers", return_value=[cursor_provider]),
        patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/sessions?search=auth")
            assert resp.status_code == 200
            data = resp.json()
            # Should find "Fix auth bug" session
            assert data["total"] >= 1
            titles = [s["title"] for s in data["sessions"]]
            assert any("auth" in t.lower() for t in titles)


@pytest.mark.asyncio
async def test_get_session_messages(cursor_provider, tmp_cursor_global):
    with (
        patch("aichat_history.server.get_available_providers", return_value=[cursor_provider]),
        patch("aichat_history.backends.cursor.get_cursor_global_path", return_value=tmp_cursor_global),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Get a session first
            resp = await client.get("/api/sessions")
            sessions = resp.json()["sessions"]
            assert len(sessions) > 0

            # Get messages for the first session
            session_id = sessions[0]["id"]
            resp = await client.get(f"/api/session/{session_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert "messages" in data
            assert "session_id" in data


@pytest.mark.asyncio
async def test_get_session_not_found():
    with patch("aichat_history.server.get_available_providers", return_value=[]):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/session/cursor:nonexistent:fake")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_index_page():
    with patch("aichat_history.server.get_available_providers", return_value=[]):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "aichat-history" in resp.text
