"""FastAPI web server for aichat-history."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from .backends import get_available_providers
from .export import session_to_json, session_to_markdown
from .provider import ChatProvider

logger = logging.getLogger(__name__)

app = FastAPI(title="aichat-history", version="0.1.0")

# Provider cache (populated on first request)
_providers: list[ChatProvider] | None = None


def _get_providers() -> list[ChatProvider]:
    """Lazily initialize and cache providers."""
    global _providers
    if _providers is None:
        _providers = get_available_providers()
        logger.info("Detected providers: %s", [p.name for p in _providers])
    return _providers


def _find_provider(source: str) -> ChatProvider | None:
    """Find a provider by name."""
    for p in _get_providers():
        if p.name == source:
            return p
    return None


def _session_to_dict(session) -> dict:
    """Convert a Session dataclass to a JSON-serializable dict."""
    return {
        "id": session.id,
        "workspace_id": session.workspace_id,
        "title": session.title,
        "message_count": session.message_count,
        "created": session.created.isoformat() if session.created else None,
        "updated": session.updated.isoformat() if session.updated else None,
        "source": session.source,
        "project_path": session.project_path,
    }


def _message_to_dict(msg) -> dict:
    """Convert a Message dataclass to a JSON-serializable dict."""
    return {
        "role": msg.role,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
        "message_type": msg.message_type,
        "metadata": msg.metadata,
    }


# ── Routes ───────────────────────────────────────────────────────


@app.get("/")
async def index():
    """Serve the frontend."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/sources")
async def get_sources():
    """Return list of available chat history sources."""
    return [p.name for p in _get_providers()]


@app.get("/api/sessions")
async def get_sessions(
    source: str | None = Query(None, description="Filter by source"),
    search: str | None = Query(None, description="Search in titles"),
    sort: str = Query("newest", description="Sort: newest, messages, project"),
    project: str | None = Query(None, description="Filter by project path"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Return all sessions across all providers."""
    providers = _get_providers()

    if source:
        providers = [p for p in providers if p.name == source]

    all_sessions = []
    for provider in providers:
        try:
            sessions = provider.list_sessions()
            all_sessions.extend(sessions)
        except Exception as e:
            logger.error("Failed to list sessions for %s: %s", provider.name, e)

    # Filter by search
    if search:
        search_lower = search.lower()
        all_sessions = [
            s for s in all_sessions
            if search_lower in s.title.lower()
            or search_lower in s.project_path.lower()
        ]

    # Filter by project
    if project:
        all_sessions = [s for s in all_sessions if s.project_path == project]

    # Sort
    if sort == "newest":
        all_sessions.sort(key=lambda s: s.updated or s.created or _epoch(), reverse=True)
    elif sort == "messages":
        all_sessions.sort(key=lambda s: s.message_count, reverse=True)
    elif sort == "project":
        all_sessions.sort(key=lambda s: s.project_path)

    total = len(all_sessions)
    all_sessions = all_sessions[offset: offset + limit]

    return {
        "total": total,
        "sessions": [_session_to_dict(s) for s in all_sessions],
    }


@app.get("/api/session/{session_id:path}")
async def get_session(session_id: str):
    """Return full messages for a session."""
    # Determine which provider owns this session
    source = session_id.split(":")[0] if ":" in session_id else ""
    source_map = {"cursor": "cursor", "claude": "claude_code", "opencode": "opencode"}
    provider_name = source_map.get(source)

    if not provider_name:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")

    provider = _find_provider(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not available: {provider_name}")

    try:
        messages = provider.get_session_messages(session_id)
    except Exception as e:
        logger.error("Failed to get messages for %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Failed to load messages")

    return {
        "session_id": session_id,
        "messages": [_message_to_dict(m) for m in messages],
    }


@app.get("/api/export/{session_id:path}")
async def export_session(
    session_id: str,
    format: str = Query("md", description="Export format: md or json"),
):
    """Export a session as Markdown or JSON."""
    source = session_id.split(":")[0] if ":" in session_id else ""
    source_map = {"cursor": "cursor", "claude": "claude_code", "opencode": "opencode"}
    provider_name = source_map.get(source)

    if not provider_name:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")

    provider = _find_provider(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not available: {provider_name}")

    # Find session metadata
    try:
        sessions = provider.list_sessions()
        session = next((s for s in sessions if s.id == session_id), None)
    except Exception as e:
        logger.error("Failed to find session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Failed to find session")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        messages = provider.get_session_messages(session_id)
    except Exception as e:
        logger.error("Failed to get messages for export %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Failed to load messages")

    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in session.title)[:50]

    if format == "json":
        content = session_to_json(session, messages)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.json"'},
        )
    else:
        content = session_to_markdown(session, messages)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
        )


def _epoch():
    """Return a datetime at epoch for sorting fallback."""
    from datetime import datetime, timezone
    return datetime(1970, 1, 1, tzinfo=timezone.utc)
