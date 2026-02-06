"""Shared test fixtures for aichat-history."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def tmp_cursor_workspace(tmp_path):
    """Create a synthetic Cursor workspace with chat data.

    Returns the workspaceStorage directory path containing one workspace
    with known composerData, prompts, and generations.
    """
    ws_storage = tmp_path / "workspaceStorage"
    ws_dir = ws_storage / "abc123hash"
    ws_dir.mkdir(parents=True)

    # Write workspace.json
    workspace_json = {"folder": "file:///Users/testuser/dev/my-project"}
    (ws_dir / "workspace.json").write_text(json.dumps(workspace_json), encoding="utf-8")

    # Create state.vscdb with test data
    db_path = ws_dir / "state.vscdb"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute("CREATE TABLE cursorDiskKV (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")

    # Composer data with 2 sessions
    now_ms = int(datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    later_ms = int(datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    much_later_ms = int(datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

    composer_data = {
        "allComposers": [
            {
                "composerId": "comp-uuid-001",
                "name": "Fix auth bug",
                "createdAt": now_ms,
                "lastUpdatedAt": later_ms,
                "unifiedMode": "agent",
                "isArchived": False,
            },
            {
                "composerId": "comp-uuid-002",
                "name": "Add dark mode",
                "createdAt": later_ms + 1000,
                "lastUpdatedAt": much_later_ms,
                "unifiedMode": "chat",
                "isArchived": False,
            },
        ],
        "selectedComposerIds": ["comp-uuid-001"],
    }

    # 3 user prompts
    prompts = [
        {"text": "Fix the login authentication bug in auth.ts", "commandType": 4},
        {"text": "Now add error handling for expired tokens", "commandType": 4},
        {"text": "Add dark mode support to the app", "commandType": 4},
    ]

    # 3 generations with timestamps
    generations = [
        {
            "unixMs": now_ms + 5000,
            "generationUUID": "gen-001",
            "type": "composer",
            "textDescription": "Fixed authentication bug by updating token validation",
        },
        {
            "unixMs": now_ms + 30000,
            "generationUUID": "gen-002",
            "type": "composer",
            "textDescription": "Added try-catch for expired token handling",
        },
        {
            "unixMs": later_ms + 60000,
            "generationUUID": "gen-003",
            "type": "composer",
            "textDescription": "Implemented dark mode toggle with CSS variables",
        },
    ]

    conn.execute("INSERT INTO ItemTable VALUES (?, ?)", ("composer.composerData", json.dumps(composer_data)))
    conn.execute("INSERT INTO ItemTable VALUES (?, ?)", ("aiService.prompts", json.dumps(prompts)))
    conn.execute("INSERT INTO ItemTable VALUES (?, ?)", ("aiService.generations", json.dumps(generations)))
    conn.commit()
    conn.close()

    return ws_storage


@pytest.fixture
def tmp_cursor_global(tmp_path):
    """Create a synthetic Cursor global storage with chat data."""
    global_dir = tmp_path / "globalStorage"
    global_dir.mkdir(parents=True)
    db_path = global_dir / "state.vscdb"

    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute("CREATE TABLE cursorDiskKV (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")

    chatdata = {
        "tabs": [
            {
                "tabId": "global-tab-001",
                "bubbles": [
                    {"type": "user", "text": "What is Python?"},
                    {"type": "ai", "text": "Python is a high-level programming language."},
                    {"type": "user", "text": "Show me an example"},
                    {"type": "ai", "text": "Here is a hello world example:\n```python\nprint('hello')\n```"},
                ],
            }
        ]
    }

    conn.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chatdata)),
    )
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def tmp_claude_code_dir(tmp_path):
    """Create a synthetic Claude Code projects directory.

    Structure:
      projects/
        -Users-testuser-dev-myapp/
          sessions-index.json
          session-001.jsonl
    """
    projects = tmp_path / "projects"
    project_dir = projects / "-Users-testuser-dev-myapp"
    project_dir.mkdir(parents=True)

    # sessions-index.json
    index = [
        {
            "sessionId": "session-001",
            "firstPrompt": "Help me refactor the auth module",
            "summary": "Refactored auth module",
            "messageCount": 5,
            "created": "2025-01-20T10:00:00Z",
            "modified": "2025-01-20T11:30:00Z",
            "projectPath": "/Users/testuser/dev/myapp",
        },
        {
            "sessionId": "session-002",
            "firstPrompt": "Write tests for the API",
            "summary": "API test suite",
            "messageCount": 3,
            "created": "2025-01-21T09:00:00Z",
            "modified": "2025-01-21T09:45:00Z",
            "projectPath": "/Users/testuser/dev/myapp",
        },
    ]
    (project_dir / "sessions-index.json").write_text(json.dumps(index), encoding="utf-8")

    # session-001.jsonl
    lines = [
        json.dumps({
            "type": "human",
            "message": {"content": [{"type": "text", "text": "Help me refactor the auth module"}]},
            "timestamp": "2025-01-20T10:00:00Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "I'll help you refactor the auth module. Let me start by reading the current code."}]},
            "timestamp": "2025-01-20T10:00:30Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/src/auth.ts"}}]},
            "timestamp": "2025-01-20T10:00:35Z",
        }),
        json.dumps({
            "type": "file-history-snapshot",
            "files": [{"path": "/src/auth.ts"}],
        }),
        json.dumps({
            "type": "human",
            "message": {"content": [{"type": "text", "text": "Looks good, now split it into separate files"}]},
            "timestamp": "2025-01-20T10:05:00Z",
        }),
    ]
    (project_dir / "session-001.jsonl").write_text("\n".join(lines), encoding="utf-8")

    return projects


@pytest.fixture
def tmp_opencode_dir(tmp_path):
    """Create a synthetic OpenCode storage directory.

    Structure:
      storage/
        session/
          proj1/
            ses_001.json
        message/
          ses_001/
            msg_001.json
            msg_002.json
        part/
          msg_001/
            prt_001.json
          msg_002/
            prt_001.json
    """
    storage = tmp_path / "storage"

    # Session
    ses_dir = storage / "session" / "proj1"
    ses_dir.mkdir(parents=True)
    ses_data = {
        "id": "ses_001",
        "title": "Debug API endpoint",
        "directory": "/Users/testuser/dev/api-server",
        "time": {
            "created": int(datetime(2025, 1, 22, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
            "updated": int(datetime(2025, 1, 22, 8, 30, 0, tzinfo=timezone.utc).timestamp() * 1000),
        },
    }
    (ses_dir / "ses_001.json").write_text(json.dumps(ses_data), encoding="utf-8")

    # Messages
    msg_dir = storage / "message" / "ses_001"
    msg_dir.mkdir(parents=True)

    msg1 = {
        "id": "msg_001",
        "role": "user",
        "time": {"created": int(datetime(2025, 1, 22, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)},
    }
    msg2 = {
        "id": "msg_002",
        "role": "assistant",
        "time": {"created": int(datetime(2025, 1, 22, 8, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)},
    }
    (msg_dir / "msg_001.json").write_text(json.dumps(msg1), encoding="utf-8")
    (msg_dir / "msg_002.json").write_text(json.dumps(msg2), encoding="utf-8")

    # Parts
    prt_dir_1 = storage / "part" / "msg_001"
    prt_dir_1.mkdir(parents=True)
    prt1 = {"type": "text", "text": "Why is the /api/users endpoint returning 500?"}
    (prt_dir_1 / "prt_001.json").write_text(json.dumps(prt1), encoding="utf-8")

    prt_dir_2 = storage / "part" / "msg_002"
    prt_dir_2.mkdir(parents=True)
    prt2 = {"type": "text", "text": "The error is in the database query. Let me check the logs."}
    (prt_dir_2 / "prt_001.json").write_text(json.dumps(prt2), encoding="utf-8")

    return storage
