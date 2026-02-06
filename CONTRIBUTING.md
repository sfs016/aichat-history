# Contributing to aichat-history

## Development setup

```bash
git clone https://github.com/sfs016/aichat-history.git
cd aichat-history
pip install -e ".[dev]"
pytest
```

## Running locally

```bash
aichat-history serve
# or
python -m aichat_history serve
```

## Project structure

```
src/aichat_history/
  core.py           # Dataclasses: Workspace, Session, Message
  provider.py       # ABC: ChatProvider
  config.py         # Platform path resolution
  server.py         # FastAPI app + API routes
  export.py         # Markdown + JSON export
  cli.py            # Click CLI entry point
  backends/
    __init__.py     # Provider registry + auto-detection
    cursor.py       # Cursor backend
    claude_code.py  # Claude Code backend
    opencode.py     # OpenCode backend
  static/
    index.html      # Single-file Vue 3 + Tailwind frontend
```

## Adding a new backend

1. Create `src/aichat_history/backends/your_ide.py`
2. Implement the `ChatProvider` ABC:

```python
from ..provider import ChatProvider
from ..core import Workspace, Session, Message

class YourIdeProvider(ChatProvider):
    name = "your_ide"

    def get_base_path(self) -> Path: ...
    def is_available(self) -> bool: ...
    def list_workspaces(self) -> list[Workspace]: ...
    def list_sessions(self, workspace_id=None) -> list[Session]: ...
    def get_session_messages(self, session_id) -> list[Message]: ...
```

3. Add to the registry in `backends/__init__.py`
4. Add path resolution in `config.py`
5. Write tests with synthetic fixtures in `tests/`

### Session ID format

Session IDs are namespaced: `{source}:{workspace}:{session}`. For example:
- `cursor:abc123:comp-uuid-001`
- `claude:project-name:session-uuid`
- `opencode:ses_001`

### Testing

Create synthetic test data in `tests/conftest.py` (never use real user data in tests).

```bash
pytest tests/ -v           # run all tests
pytest tests/test_cursor.py -v  # run one backend
```

## Frontend

The frontend is a single HTML file at `src/aichat_history/static/index.html`. It uses:
- Vue 3 (CDN, no build step)
- Tailwind CSS (CDN)
- marked.js for Markdown rendering
- highlight.js for syntax highlighting

Edit `index.html` and refresh the browser -- no build step required.

## Guidelines

- All file reads must be **read-only** (never write to IDE data files)
- Open SQLite databases with `?mode=ro`
- Handle corrupt/missing data gracefully (log warning, skip, continue)
- Use `pathlib.Path` for all file operations
- Write tests with synthetic fixtures, not real data
