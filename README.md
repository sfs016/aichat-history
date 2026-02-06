# aichat-history

A local web app to browse your AI coding chat history from **Cursor**, **Claude Code**, and **OpenCode** -- all in one place.

Read-only. Fully local. No data leaves your machine. Simple but effective UI/UX to quickly scroll through your chat history, filter or even search.

## Install

```bash
pip install aichat-history
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install aichat-history
```

## Usage

```bash
aichat-history serve
```

Open [localhost:8080](http://localhost:8080) and browse your conversations.

```bash
aichat-history serve --port 3000        # custom port
aichat-history serve --host 0.0.0.0     # expose on network
```

## Supported IDEs

| IDE | Format | Default path (macOS) |
|-----|--------|----------------------|
| Cursor | SQLite | `~/Library/Application Support/Cursor/User/workspaceStorage/` |
| Claude Code | JSONL | `~/.claude/projects/` |
| OpenCode | JSON | `~/.local/share/opencode/storage/` |

Paths are auto-detected on macOS, Linux, and Windows. Override with environment variables:

```bash
export AICHAT_CURSOR_PATH=/path/to/cursor/workspaceStorage
export AICHAT_CLAUDE_PATH=/path/to/claude/projects
export AICHAT_OPENCODE_PATH=/path/to/opencode/storage
```

## Features

- Search, filter, and sort across all your AI chat sessions
- Export any session as Markdown or JSON
- Collapsible tool calls, thinking blocks, and long responses
- Message navigation to jump between user/agent turns
- Dark mode with system preference detection
- Syntax-highlighted code blocks with copy button

## License

[MIT](LICENSE)
