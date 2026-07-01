# daily-digest

Collects all AI agent conversations from a day, summarizes each one, extracts
work items, and syncs everything to a Notion database. Open Notion each morning
to see what was done yesterday, what's pending, and what you might have missed.

## Sources

| Source | Data Extracted | Richness |
|--------|---------------|----------|
| **Grok** | Title, messages, model, branch, tools used, lines changed, duration | Full |
| **Claude Code** | Messages, tool calls, file paths, timestamps | Full |
| **Cursor** | Composer name, mode, lines changed, files count | Metadata |

Adding new sources (Windsurf, Copilot, Aider) requires one Python file.
See [Adding Sources](docs/ADDING_SOURCES.md).

## Setup

```bash
# 1. Run setup (installs deps, checks env vars)
bash scripts/setup.sh

# 2. Set Notion credentials (see docs/SETUP.md for details)
export NOTION_TOKEN='ntn_...'
export NOTION_DATABASE_ID='abc123...'
```

## Usage

In Grok:
```
/daily-digest              # Digest today's conversations
/daily-digest 2026-06-30   # Digest a specific date
/daily-digest yesterday    # Digest yesterday
```

## What You Get in Notion

Each day becomes a database row with:
- **Quick-scan columns**: date, conversation count, done/pending/in-progress counts
- **Detail page**: work items (done ✅, in progress 🔄, pending ⏳, priority 🔥)
  and per-conversation summaries with decisions and files changed

## Architecture

```
daily-digest/
├── SKILL.md                  # Agent instructions
├── scripts/
│   ├── setup.sh              # Environment setup
│   ├── collect_sessions.py   # Session collector (all sources)
│   ├── notion_sync.py        # Notion API sync
│   └── sources/
│       ├── base.py           # SourceAdapter interface
│       ├── grok_source.py    # Grok reader
│       ├── claude_code_source.py  # Claude Code reader
│       └── cursor_source.py  # Cursor reader
└── docs/
    ├── SETUP.md              # Notion setup guide
    ├── ADDING_SOURCES.md     # How to add sources
    └── NOTION_SCHEMA.md      # Database schema
```

## How It Works

1. **Collect**: Python scripts read session data from each tool's storage
2. **Summarize**: The LLM generates per-conversation summaries and extracts work items
3. **Sync**: A Python script pushes the structured digest to Notion via their API
4. **Idempotent**: Running twice for the same date updates the existing row
