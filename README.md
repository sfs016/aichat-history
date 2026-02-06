# aichat-history

Browse AI coding chat history from **Cursor**, **Claude Code**, and **OpenCode** in one unified interface.

<!-- TODO: Add screenshot -->

## Why this tool?

Every AI-powered coding IDE stores conversations differently -- Cursor uses SQLite databases, Claude Code uses JSONL files, OpenCode uses a nested JSON hierarchy. There's no unified way to search, browse, or export your chat history across these tools.

**aichat-history** gives you a single local web app to browse all of them. It's read-only, runs entirely on your machine, and sends no data anywhere.

## Install

```bash
pip install aichat-history
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install aichat-history
```

Or with [pipx](https://github.com/pypa/pipx):

```bash
pipx install aichat-history
```

## Usage

```bash
aichat-history serve
```

Then open [http://localhost:8080](http://localhost:8080) in your browser.

### Options

```
aichat-history serve --port 8081     # custom port
aichat-history serve --host 0.0.0.0  # bind to all interfaces
```

## What it reads

| IDE | Storage format | Default location (macOS) |
|-----|---------------|--------------------------|
| **Cursor** | SQLite (`state.vscdb`) | `~/Library/Application Support/Cursor/User/workspaceStorage/` |
| **Claude Code** | JSONL + JSON index | `~/.claude/projects/` |
| **OpenCode** | JSON file hierarchy | `~/.local/share/opencode/storage/` |

All paths are auto-detected per platform (macOS, Linux, Windows).

## Configuration

Override storage paths via environment variables:

```bash
export AICHAT_CURSOR_PATH=/custom/path/to/cursor/workspaceStorage
export AICHAT_CLAUDE_PATH=/custom/path/to/claude/projects
export AICHAT_OPENCODE_PATH=/custom/path/to/opencode/storage
```

## Features

- **Unified view** -- browse all IDE chat histories in one place
- **Search** -- full-text search across session titles and project names
- **Filter** -- by source (Cursor/Claude Code/OpenCode) and project
- **Sort** -- by date, message count, or project name
- **Export** -- download any session as Markdown or JSON
- **Dark mode** -- respects system preference, toggleable
- **Collapsible** -- tool calls and thinking blocks collapse to one-line summaries
- **Syntax highlighting** -- code blocks with copy button
- **Read-only** -- never writes to IDE data files

## Privacy

- **100% local** -- runs entirely on your machine
- **No telemetry** -- no analytics, no tracking, no phone-home
- **Read-only** -- only reads existing chat data files, never modifies them
- **No network** -- the server only listens on localhost by default

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and how to add new backends.

## License

[MIT](LICENSE)
