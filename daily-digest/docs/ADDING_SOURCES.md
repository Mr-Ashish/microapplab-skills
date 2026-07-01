# Adding a New Conversation Source

The daily-digest skill uses a pluggable source architecture. Each source is a
Python module that knows how to find and read conversations from a specific AI
coding tool.

## Quick Start

1. Create `scripts/sources/<name>_source.py`
2. Implement a class that inherits from `SourceAdapter`
3. Set `name` and implement `discover_sessions()` and `extract_context()`
4. Done — the registry auto-discovers `*_source.py` files

## Source Adapter Interface

```python
from datetime import date
from sources.base import SourceAdapter, SessionMeta, SessionContext

class MyToolSource(SourceAdapter):
    name = "my_tool"  # Used in output JSON and Notion "Sources" column

    def discover_sessions(self, target_date: date) -> list[SessionMeta]:
        """Find all sessions active on target_date.

        Return a SessionMeta for each conversation found. Include enough
        info in the `extra` dict for extract_context() to locate the
        full data later.
        """
        sessions = []
        # ... find sessions ...
        return sessions

    def extract_context(self, session: SessionMeta) -> SessionContext:
        """Read conversation content for LLM summarization.

        Return user_messages and/or a conversation_excerpt. Cap total
        text to ~3000 chars to keep LLM context manageable.
        """
        # ... read conversation data ...
        return SessionContext(
            meta=session,
            user_messages=["..."],
            assistant_responses=["..."],
            conversation_excerpt="...",
        )
```

## Data Classes

### SessionMeta

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | str | Yes | Unique identifier |
| `source` | str | Yes | Your adapter name |
| `title` | str | Yes | Conversation title/topic |
| `created_at` | str | Yes | ISO 8601 timestamp |
| `updated_at` | str | Yes | ISO 8601 timestamp |
| `workspace` | str | Yes | Project/directory path |
| `model` | str | No | AI model used |
| `branch` | str | No | Git branch |
| `message_count` | int | No | Total messages |
| `turn_count` | int | No | User turns |
| `tool_call_count` | int | No | Tool invocations |
| `tools_used` | list[str] | No | Tool names |
| `duration_seconds` | int | No | Session length |
| `lines_added` | int | No | Code lines added |
| `lines_removed` | int | No | Code lines removed |
| `files_changed` | list[str] | No | File paths changed |
| `extra` | dict | No | Source-specific data |

### SessionContext

| Field | Type | Description |
|-------|------|-------------|
| `meta` | SessionMeta | The session metadata |
| `user_messages` | list[str] | Key user prompts (capped) |
| `assistant_responses` | list[str] | Key responses (capped) |
| `conversation_excerpt` | str | Combined text for summarization |

## Testing Your Source

```bash
# Test discovery
python3 scripts/collect_sessions.py --date 2026-07-01 --source my_tool

# List all registered sources
python3 scripts/collect_sessions.py --list-sources
```

## Example: Windsurf Source

```python
# scripts/sources/windsurf_source.py

from datetime import date
from pathlib import Path
from sources.base import SourceAdapter, SessionMeta, SessionContext

WINDSURF_DIR = Path.home() / ".windsurf" / "sessions"

class WindsurfSource(SourceAdapter):
    name = "windsurf"

    def discover_sessions(self, target_date: date) -> list[SessionMeta]:
        if not WINDSURF_DIR.exists():
            return []
        # ... read Windsurf session files ...
        return []

    def extract_context(self, session: SessionMeta) -> SessionContext:
        # ... extract conversation content ...
        return SessionContext(meta=session)
```

## Guidelines

- **Error handling:** Wrap I/O in try/except. Return empty lists on failure,
  don't crash the whole collector.
- **Text caps:** Limit extracted text to ~3000 chars per conversation. The LLM
  needs enough context to summarize but shouldn't be overwhelmed.
- **Platform paths:** Use `platform.system()` to handle macOS/Linux/Windows
  differences (see `cursor_source.py` for an example).
- **Read-only:** Never modify the source tool's data files.
