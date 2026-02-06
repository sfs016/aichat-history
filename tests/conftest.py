"""Shared test fixtures for aichat-history."""

import json
import sqlite3
from datetime import datetime, timezone

import pytest


@pytest.fixture
def tmp_cursor_workspace(tmp_path):
    """Create a synthetic Cursor workspace with chat data."""
    ws_storage = tmp_path / "workspaceStorage"
    ws_dir = ws_storage / "abc123hash"
    ws_dir.mkdir(parents=True)

    workspace_json = {"folder": "file:///Users/testuser/dev/my-project"}
    (ws_dir / "workspace.json").write_text(json.dumps(workspace_json), encoding="utf-8")

    db_path = ws_dir / "state.vscdb"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute("CREATE TABLE cursorDiskKV (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")

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

    prompts = [
        {"text": "Fix the login authentication bug in auth.ts", "commandType": 4},
        {"text": "Now add error handling for expired tokens", "commandType": 4},
        {"text": "Add dark mode support to the app", "commandType": 4},
    ]

    generations = [
        {"unixMs": now_ms + 5000, "generationUUID": "gen-001", "type": "composer", "textDescription": "Fixed authentication bug by updating token validation"},
        {"unixMs": now_ms + 30000, "generationUUID": "gen-002", "type": "composer", "textDescription": "Added try-catch for expired token handling"},
        {"unixMs": later_ms + 60000, "generationUUID": "gen-003", "type": "composer", "textDescription": "Implemented dark mode toggle with CSS variables"},
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

    conn.execute("INSERT INTO ItemTable VALUES (?, ?)", ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chatdata)))
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def tmp_claude_code_dir(tmp_path):
    """Create a synthetic Claude Code projects directory with realistic JSONL.

    Includes:
    - User text messages
    - Assistant text + tool_use in same entry
    - User tool_result entries
    - Thinking blocks
    - file-history-snapshot (should be skipped)
    """
    projects = tmp_path / "projects"
    project_dir = projects / "-Users-testuser-dev-myapp"
    project_dir.mkdir(parents=True)

    index = [
        {
            "sessionId": "session-001",
            "firstPrompt": "Help me refactor the auth module",
            "summary": "Refactored auth module",
            "messageCount": 8,
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

    # Realistic JSONL with all entry types
    lines = [
        # 1. User prompt
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "Help me refactor the auth module"}]},
            "timestamp": "2025-01-20T10:00:00Z",
            "uuid": "uuid-001",
        }),
        # 2. Assistant text + tool_use in same entry
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "text", "text": "I'll help you refactor the auth module. Let me start by reading the current code."},
                {"type": "tool_use", "id": "toolu_001", "name": "Read", "input": {"file_path": "/src/auth.ts"}},
            ]},
            "timestamp": "2025-01-20T10:00:30Z",
            "uuid": "uuid-002",
        }),
        # 3. Tool result (appears as user type entry)
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_001", "content": "export function authenticate(token: string) {\n  return jwt.verify(token);\n}", "is_error": False},
            ]},
            "timestamp": "2025-01-20T10:00:31Z",
            "uuid": "uuid-003",
        }),
        # 4. Assistant with thinking block
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "I need to split this into separate functions for validation and token refresh."},
                {"type": "text", "text": "I can see the auth module. Let me refactor it into separate concerns."},
                {"type": "tool_use", "id": "toolu_002", "name": "Edit", "input": {"file_path": "/src/auth.ts", "new_content": "refactored code..."}},
            ]},
            "timestamp": "2025-01-20T10:01:00Z",
            "uuid": "uuid-004",
        }),
        # 5. Tool result for Edit
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_002", "content": "File edited successfully", "is_error": False},
            ]},
            "timestamp": "2025-01-20T10:01:01Z",
            "uuid": "uuid-005",
        }),
        # 6. file-history-snapshot (should be skipped)
        json.dumps({
            "type": "file-history-snapshot",
            "files": [{"path": "/src/auth.ts"}],
        }),
        # 7. User follow-up
        json.dumps({
            "type": "human",
            "message": {"role": "user", "content": [{"type": "text", "text": "Looks good, now split it into separate files"}]},
            "timestamp": "2025-01-20T10:05:00Z",
            "uuid": "uuid-006",
        }),
        # 8. Assistant with just tool_use (no text)
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_003", "name": "Bash", "input": {"command": "mkdir -p /src/auth/", "description": "Create auth directory"}},
            ]},
            "timestamp": "2025-01-20T10:05:30Z",
            "uuid": "uuid-007",
        }),
        # 9. Progress entry (should be skipped)
        json.dumps({
            "type": "progress",
            "data": {"type": "hook_progress"},
        }),
        # 10. Summary entry (should be skipped)
        json.dumps({
            "type": "summary",
            "summary": "Refactored auth module into separate files",
        }),
        # 11. Queue-operation entry (should be skipped)
        json.dumps({
            "type": "queue-operation",
            "operation": "enqueue",
        }),
        # 12. Tool result with image block
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_003", "content": [
                    {"type": "text", "text": "Command output:\nDirectory created"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}},
                ], "is_error": False},
            ]},
            "timestamp": "2025-01-20T10:05:31Z",
            "uuid": "uuid-008",
        }),
    ]
    (project_dir / "session-001.jsonl").write_text("\n".join(lines), encoding="utf-8")

    return projects


@pytest.fixture
def tmp_opencode_dir(tmp_path):
    """Create a synthetic OpenCode v1.1+ storage directory with parts."""
    storage = tmp_path / "storage"

    # Session
    ses_dir = storage / "session" / "proj1"
    ses_dir.mkdir(parents=True)
    ses_data = {
        "id": "ses_001",
        "version": "1.1.34",
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
        "sessionID": "ses_001",
        "role": "user",
        "time": {"created": int(datetime(2025, 1, 22, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)},
        "summary": {"title": "API 500 error investigation", "diffs": []},
    }
    msg2 = {
        "id": "msg_002",
        "sessionID": "ses_001",
        "role": "assistant",
        "time": {"created": int(datetime(2025, 1, 22, 8, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)},
    }
    msg3 = {
        "id": "msg_003",
        "sessionID": "ses_001",
        "role": "assistant",
        "time": {"created": int(datetime(2025, 1, 22, 8, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)},
    }
    (msg_dir / "msg_001.json").write_text(json.dumps(msg1), encoding="utf-8")
    (msg_dir / "msg_002.json").write_text(json.dumps(msg2), encoding="utf-8")
    (msg_dir / "msg_003.json").write_text(json.dumps(msg3), encoding="utf-8")

    # Parts for msg_001 (user text)
    prt_dir_1 = storage / "part" / "msg_001"
    prt_dir_1.mkdir(parents=True)
    prt1 = {"id": "prt_001", "messageID": "msg_001", "type": "text", "text": "Why is the /api/users endpoint returning 500?"}
    (prt_dir_1 / "prt_001.json").write_text(json.dumps(prt1), encoding="utf-8")

    # Parts for msg_002 (assistant text)
    prt_dir_2 = storage / "part" / "msg_002"
    prt_dir_2.mkdir(parents=True)
    prt2_text = {"id": "prt_002", "messageID": "msg_002", "type": "text", "text": "The error is in the database query. Let me check the logs."}
    (prt_dir_2 / "prt_001.json").write_text(json.dumps(prt2_text), encoding="utf-8")

    # Parts for msg_003 (assistant with tool call - v1.1 format)
    prt_dir_3 = storage / "part" / "msg_003"
    prt_dir_3.mkdir(parents=True)
    prt3_step = {"id": "prt_003a", "messageID": "msg_003", "type": "step-start", "snapshot": "abc123"}
    prt3_tool = {
        "id": "prt_003b",
        "messageID": "msg_003",
        "type": "tool",
        "tool": "grep",
        "state": {
            "status": "completed",
            "input": {"pattern": "SELECT.*FROM users", "include": "*.ts"},
            "output": "Found 3 matches\nsrc/db.ts:15: SELECT * FROM users WHERE id = $1",
            "metadata": {"matches": 3},
        },
    }
    (prt_dir_3 / "prt_001.json").write_text(json.dumps(prt3_step), encoding="utf-8")
    (prt_dir_3 / "prt_002.json").write_text(json.dumps(prt3_tool), encoding="utf-8")

    return storage


@pytest.fixture
def tmp_opencode_v1_dir(tmp_path):
    """Create a synthetic OpenCode v1.0 storage directory (no parts, summary only)."""
    storage = tmp_path / "storage"

    ses_dir = storage / "session" / "proj_old"
    ses_dir.mkdir(parents=True)
    ses_data = {
        "id": "ses_old_001",
        "version": "1.0.218",
        "title": "Build login page",
        "directory": "/Users/testuser/dev/webapp",
        "time": {
            "created": int(datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
            "updated": int(datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
        },
    }
    (ses_dir / "ses_old_001.json").write_text(json.dumps(ses_data), encoding="utf-8")

    # Messages with summary but NO part directories
    msg_dir = storage / "message" / "ses_old_001"
    msg_dir.mkdir(parents=True)

    msg1 = {
        "id": "msg_old_001",
        "sessionID": "ses_old_001",
        "role": "user",
        "time": {"created": int(datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)},
        "summary": {"title": "Build a login page with email and password", "diffs": []},
        "agent": "code",
        "model": {"providerID": "opencode", "modelID": "big-pickle"},
    }
    msg2 = {
        "id": "msg_old_002",
        "sessionID": "ses_old_001",
        "role": "assistant",
        "time": {"created": int(datetime(2025, 1, 10, 9, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)},
        "mode": "code",
        "finish": "stop",
    }
    (msg_dir / "msg_old_001.json").write_text(json.dumps(msg1), encoding="utf-8")
    (msg_dir / "msg_old_002.json").write_text(json.dumps(msg2), encoding="utf-8")

    # Ensure part/ dir exists but has NO subdirs for these messages
    (storage / "part").mkdir(parents=True)

    return storage
