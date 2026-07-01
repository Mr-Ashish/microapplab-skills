# Notion Database Schema Reference

## Database Properties

These are the columns in the "Daily Digest" database. The `notion_sync.py`
script creates/updates these automatically.

| Property | Notion Type | API Key | Example Value |
|----------|------------|---------|---------------|
| Date | Title | `Date` | "2026-07-01 (Tuesday)" |
| Day | Date | `Day` | 2026-07-01 |
| Conversations | Number | `Conversations` | 7 |
| Done | Number | `Done` | 5 |
| Pending | Number | `Pending` | 3 |
| In Progress | Number | `In Progress` | 2 |
| Sources | Multi-select | `Sources` | grok, claude_code, cursor |
| Status | Select | `Status` | synced / partial / error |

## Page Body Structure

Each database row is also a Notion page. The page body is populated with:

```
## 📋 Work Items
  ### ✅ Done
    • item 1
    • item 2
  ### 🔄 In Progress
    • item 1
  ### ⏳ Pending
    • item 1
  ### 🔥 Priority
    • item 1

  ---

## 💬 Conversations
  ### 1. [Title] (source)
    **Duration: X min | Messages: Y | Model: Z**
    Summary paragraph...
    **Key Decisions:**
    • decision 1
    **Files:** `path1.py`, `path2.ts`

    ---

  ### 2. [Title] (source)
    ...
```

## Notion Block Types Used

| Block Type | API Type | Usage |
|-----------|----------|-------|
| Heading 2 | `heading_2` | Section headers (Work Items, Conversations) |
| Heading 3 | `heading_3` | Category headers (Done, In Progress) and conversation titles |
| Paragraph | `paragraph` | Summaries, metadata lines |
| Bullet List | `bulleted_list_item` | Work items, decisions, file lists |
| Divider | `divider` | Between conversations |

## Idempotency

The sync script is idempotent:
- It queries the database for an existing page with the same `Day` date
- If found: updates properties and replaces all body blocks
- If not found: creates a new page

Running `/daily-digest` multiple times for the same date is safe — it
updates the existing page with the latest data.

## Multi-select Options

The `Sources` multi-select accepts any value. Current built-in sources:

| Value | Description |
|-------|-------------|
| `grok` | Grok/Build sessions |
| `claude_code` | Claude Code CLI sessions |
| `cursor` | Cursor composer sessions |

New sources are added automatically when they appear in digest data.
