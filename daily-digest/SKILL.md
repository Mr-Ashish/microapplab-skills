---
name: daily-digest
description: >
  Collect all AI agent conversations from a day (Grok, Claude Code, Cursor),
  summarize each one, extract work items (done/pending/in-progress/priority),
  and sync everything to a Notion database as a daily row with detail pages.
  Use when: the user says "daily digest", "daily summary", "sync today to notion",
  "what did I do today", "/daily-digest", or wants a daily work recap pushed to Notion.
---

# Daily Digest — AI Conversation → Notion Sync

Collects conversations from Grok, Claude Code, and Cursor, generates summaries
and work-item lists, then syncs to a Notion database. Each day gets one row
with a detail page containing per-conversation breakdowns and actionable items.

## Prerequisites

Before first use, run setup:
```bash
bash ~/.grok/skills/daily-digest/scripts/setup.sh
```

Required environment variables:
- `NOTION_TOKEN` — Notion integration secret
- `NOTION_DATABASE_ID` — Target Notion database ID

See `docs/SETUP.md` for step-by-step Notion setup instructions.

---

## Execution Steps

### Step 1: Determine Target Date

Parse the user's input for a date. Default to today.

- `/daily-digest` → use today's date
- `/daily-digest 2026-06-30` → use the specified date
- `/daily-digest yesterday` → use yesterday's date

Store the date as `TARGET_DATE` in YYYY-MM-DD format.

### Step 2: Verify Setup

Check that the required environment variables are set:
```bash
echo "NOTION_TOKEN: ${NOTION_TOKEN:+set}" && echo "NOTION_DATABASE_ID: ${NOTION_DATABASE_ID:+set}"
```

If either is missing, tell the user to run setup and stop.

### Step 3: Collect Raw Sessions

Run the collector script to gather all sessions from the target date:

```bash
python3 ~/.grok/skills/daily-digest/scripts/collect_sessions.py --date TARGET_DATE --output /tmp/daily-digest-raw.json
```

Read the output file. It contains a JSON object with:
- `total_sessions` — number of conversations found
- `sources_succeeded` — which sources returned data
- `sources_failed` — which sources had errors (report these to user)
- `sessions` — array of session contexts with metadata and conversation excerpts

If `total_sessions` is 0, tell the user no sessions were found for that date and stop.

### Step 4: Summarize Each Conversation

For each session in the `sessions` array, generate a structured summary using the
conversation excerpt and metadata. Produce this exact JSON structure per conversation:

```json
{
  "title": "Short descriptive title",
  "source": "grok",
  "project": "Blockr",
  "summary": "One paragraph describing what was done in this conversation.",
  "decisions": ["Decision 1", "Decision 2"],
  "files_changed": ["path/to/file.py", "other/file.ts"],
  "work_items": {
    "done": ["Completed item 1", "Completed item 2"],
    "in_progress": ["Item still being worked on"],
    "pending": ["Item not yet started"],
    "priority": ["Urgent or important item"]
  },
  "model": "claude-sonnet-4",
  "branch": "feature/auth",
  "message_count": 42,
  "duration_seconds": 1500
}
```

**Deriving `project`:**
The session metadata contains a `workspace` field (the filesystem path or working directory
where the conversation ran). Derive the `project` name from it using these rules, in order:

1. If the workspace path contains a recognizable project/repo folder name, use it
   (e.g., `/Users/alice/Documents/personal/Blockr/Blockr-latest` → `Blockr`).
2. Otherwise, use the last meaningful directory segment of the workspace path
   (e.g., `/Users/alice/projects/my-saas-app` → `my-saas-app`).
3. If the workspace is an opaque identifier (e.g., `cursor-workspace:abc123`), set
   project to `"unknown"`.
4. Normalize the name: capitalize the first letter, keep hyphens/camelCase as-is.
   Strip suffixes like `-latest`, `-main`, `-dev` if a cleaner name exists upstream
   in the path.

**Summarization guidelines:**
- Keep summaries to 2-3 sentences. Focus on what was accomplished, not process.
- Decisions are choices made (e.g., "Chose PostgreSQL over MongoDB").
- Work items: categorize based on conversation context.
  - **done**: things explicitly completed and verified in the conversation
  - **in_progress**: things started but not finished
  - **pending**: things mentioned as next steps or TODO
  - **priority**: anything flagged as urgent, blocking, or high-priority
- If a conversation is too short or trivial (< 3 messages), mark as done with a brief note.
- Use the `title` from metadata if good, otherwise generate a better one.

### Step 5: Compile the Digest

Assemble all conversation summaries into a single digest JSON:

```json
{
  "date": "2026-07-01",
  "projects": ["Blockr", "skills"],
  "conversations": [ ...array of conversation summaries from Step 4... ],
  "work_items": {
    "done": [ ...merged from all conversations... ],
    "in_progress": [ ...merged from all conversations... ],
    "pending": [ ...merged from all conversations... ],
    "priority": [ ...merged from all conversations... ]
  }
}
```

The `projects` array is the de-duplicated, sorted list of all unique `project` values
from the conversation summaries.

Write this to `/tmp/daily-digest-final.json`.

### Step 6: Sync to Notion

Push the digest to Notion:

```bash
python3 ~/.grok/skills/daily-digest/scripts/notion_sync.py --input /tmp/daily-digest-final.json
```

The script:
- Checks if a page for this date already exists (idempotent — updates, not duplicates)
- Creates/updates the database row with properties (Date, Conversations count, Done/Pending/In Progress counts, Sources used, Projects)
- Populates the page body in a **project-first layout**: each project gets its own section with aggregated work items (done/in-progress/pending/priority) and conversation details nested underneath

### Step 7: Report Results

Tell the user:
- How many conversations were collected and from which sources
- Quick summary of work items (X done, Y in progress, Z pending)
- Any source errors that occurred
- Confirmation that Notion was updated

Example output:
```
✅ Daily digest synced for 2026-07-01

📁 Projects: Blockr, skills

📊 7 conversations collected:
   • Grok: 4 sessions
   • Claude Code: 2 sessions
   • Cursor: 1 session

💬 By project:
   • Blockr: 5 sessions
   • skills: 2 sessions

📋 Work items:
   • ✅ Done: 5 items
   • 🔄 In Progress: 2 items
   • ⏳ Pending: 3 items
   • 🔥 Priority: 1 item

🔗 Notion page updated successfully
```

### Step 8: Cleanup

Remove temporary files:
```bash
rm -f /tmp/daily-digest-raw.json /tmp/daily-digest-final.json
```

---

## Quality Gate

Before marking complete, verify:
- [ ] All available sources were queried
- [ ] Each conversation has a meaningful summary (not just metadata)
- [ ] Work items are properly categorized
- [ ] Notion sync succeeded (check script output)
- [ ] No duplicate rows created for the same date

---

## Adding New Sources

See `docs/ADDING_SOURCES.md`. The architecture is pluggable — add a new
`*_source.py` file implementing the `SourceAdapter` interface and it will
be auto-discovered by the collector.
