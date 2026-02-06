<p align="center">
  <img src="banner.svg" alt="aichat-history" width="700" />
</p>

<p align="center">
  <strong>Browse your AI coding chat history from Cursor, Claude Code, and OpenCode in one place.</strong><br/>
  <sub>Read-only. Fully local. No data leaves your machine.</sub>
</p>

<p align="center">
  <a href="#install">Install</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;<a href="#usage">Usage</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;<a href="#features">Features</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;<a href="#contributing">Contributing</a>
</p>

---

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

Open [localhost:8080](http://localhost:8080) and start browsing.

| Option | Example |
|--------|---------|
| Custom port | `aichat-history serve --port 3000` |
| Expose on network | `aichat-history serve --host 0.0.0.0` |

## Supported IDEs

| IDE | Storage | Default path (macOS) |
|-----|---------|----------------------|
| **Cursor** | SQLite | `~/Library/Application Support/Cursor/User/workspaceStorage/` |
| **Claude Code** | JSONL | `~/.claude/projects/` |
| **OpenCode** | JSON | `~/.local/share/opencode/storage/` |

All paths are auto-detected on macOS, Linux, and Windows.

<details>
<summary>Override paths with environment variables</summary>

```bash
export AICHAT_CURSOR_PATH=/path/to/cursor/workspaceStorage
export AICHAT_CLAUDE_PATH=/path/to/claude/projects
export AICHAT_OPENCODE_PATH=/path/to/opencode/storage
```

</details>

## Features

- **Search & filter** -- find sessions by title, project, or source
- **Sort** -- by message count, date, or project name
- **Export** -- download any session as Markdown or JSON
- **Message navigation** -- jump between user and agent messages
- **Collapsible** -- tool calls, thinking blocks, and long responses collapse to summaries
- **Dark mode** -- follows system preference, toggleable
- **Syntax highlighting** -- code blocks with one-click copy
- **Smooth animations** -- subtle transitions on every interaction

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

**Quick start:**

```bash
git clone https://github.com/sfs016/aichat-history.git
cd aichat-history
pip install -e ".[dev]"
pytest
```

**Want to add support for another IDE?** Implement the `ChatProvider` interface, register it in `backends/__init__.py`, and add tests with synthetic fixtures. The [contributing guide](CONTRIBUTING.md) has a step-by-step walkthrough.

## License

[MIT](LICENSE)
