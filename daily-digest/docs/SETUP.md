# Notion Setup Guide

## 1. Create a Notion Integration

1. Go to [My Integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Name it **"Daily Digest"**
4. Select the workspace where you want the database
5. Under **Capabilities**, ensure these are checked:
   - ✅ Read content
   - ✅ Update content
   - ✅ Insert content
6. Click **Submit**
7. Copy the **Internal Integration Secret** (starts with `ntn_`)

Set it as an environment variable:
```bash
# Add to ~/.zshrc or ~/.bashrc
export NOTION_TOKEN='ntn_your_secret_here'
source ~/.zshrc
```

## 2. Create the Database

Create a new **full-page database** in your Notion workspace. You can place it
anywhere — a dedicated "Agent Logs" page works well.

### Required Properties

Add these properties (columns) to your database:

| Property Name | Type | Notes |
|---------------|------|-------|
| **Date** | Title | Auto-created, this is the row name |
| **Day** | Date | For date filtering and calendar views |
| **Conversations** | Number | Count of conversations that day |
| **Done** | Number | Completed work items |
| **Pending** | Number | Pending work items |
| **In Progress** | Number | In-progress work items |
| **Sources** | Multi-select | Add options: `grok`, `claude_code`, `cursor` |
| **Status** | Select | Add options: `synced`, `partial`, `error` |

### Recommended Views

1. **Table view** (default) — sorted by Day descending
2. **Calendar view** — to see activity distribution across the month
3. **Board view** — grouped by Status for quick error triage

## 3. Share the Database

1. Open your new database page
2. Click **"..."** (more menu) → **"Connections"**
3. Find and connect **"Daily Digest"** (your integration)
4. Confirm

## 4. Get the Database ID

The database ID is in the URL when you open it:

```
https://www.notion.so/your-workspace/abc123def456...?v=...
                                      ^^^^^^^^^^^^^^^^
                                      This is the database ID
```

It's the 32-character hex string after your workspace name and before `?v=`.

Set it as an environment variable:
```bash
# Add to ~/.zshrc or ~/.bashrc
export NOTION_DATABASE_ID='abc123def456...'
source ~/.zshrc
```

## 5. Verify Setup

Run the setup script to verify everything works:

```bash
bash ~/.grok/skills/daily-digest/scripts/setup.sh
```

You should see all green checkmarks. If anything fails, the script will
tell you exactly what to fix.

## 6. Install the Skill in Your Agent

The `daily-digest` skill works with any agent that supports SKILL.md-based
discovery — Grok, Claude Code, Cursor, or compatible tools. Pick the method
that matches your setup.

### Option A: Symlink (recommended for development)

Create a symlink from the agent's skill scan directory to your local copy:

```bash
# Grok (scans ~/.grok/skills/)
ln -s /path/to/daily-digest ~/.grok/skills/daily-digest

# Claude Code (scans ~/.claude/skills/)
ln -s /path/to/daily-digest ~/.claude/skills/daily-digest

# Cursor (scans ~/.cursor/skills/)
ln -s /path/to/daily-digest ~/.cursor/skills/daily-digest
```

Changes you make in the source directory are picked up immediately — no
reinstall or restart needed.

### Option B: Copy the directory

If you don't need live editing, copy the skill directly:

```bash
cp -r /path/to/daily-digest ~/.grok/skills/daily-digest
```

### Option C: Add a custom scan path

Instead of moving files, tell your agent to scan an extra directory.

**Grok** — add to `~/.grok/config.toml`:
```toml
[skills]
paths = ["/path/to/your/skills-repo"]
```

**Claude Code** — add to `~/.claude/settings.json` (or project `.claude/settings.json`):
```json
{
  "skills": {
    "paths": ["/path/to/your/skills-repo"]
  }
}
```

Every skill directory inside that path with a valid `SKILL.md` is
auto-discovered.

### Option D: Project-scoped install

To make the skill available only inside a specific repo:

```bash
mkdir -p <repo>/.grok/skills
ln -s /path/to/daily-digest <repo>/.grok/skills/daily-digest
```

Project-scoped skills take priority over user-level ones with the same name.

### Verify the skill is loaded

After installing, confirm the agent can see it:

- **Grok**: Run `/daily-digest` — if the skill triggers, it's loaded.
- **Claude Code**: Ask `"Do you have a daily-digest skill?"` — the agent
  will confirm if it found the SKILL.md.
- **Any agent**: Check that the `SKILL.md` file is reachable from one of the
  scanned directories:
  ```bash
  ls -la ~/.grok/skills/daily-digest/SKILL.md
  ```

### Skill discovery priority

When the same skill name exists in multiple locations, the agent uses the
highest-priority copy:

| Location | Scope | Priority |
|----------|-------|----------|
| `./.grok/skills/` | Current directory | Highest |
| `<repo-root>/.grok/skills/` | Repository | ↑ |
| `~/.grok/skills/` | User | ↓ |
| `~/.claude/skills/` | User (compat) | Lowest |

### Python dependencies

The skill's scripts require Python 3.9+ and the `notion-client` package.
Install before first use:

```bash
pip3 install notion-client>=2.2.1
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `notion_client.errors.APIResponseError: Could not find database` | Make sure you shared the database with the integration (Step 3) |
| `NOTION_TOKEN not set` | Add `export NOTION_TOKEN='...'` to your shell profile and reload |
| `notion-client not installed` | Run `pip3 install notion-client>=2.2.1` |
| `Property "Day" does not exist` | Add the Day (date type) property to your Notion database |
| Skill not triggering | Verify the `SKILL.md` is reachable: `ls ~/.grok/skills/daily-digest/SKILL.md` |
| Broken symlink after moving files | Re-create the symlink pointing to the new location |
| Skill loads but scripts fail | Ensure env vars (`NOTION_TOKEN`, `NOTION_DATABASE_ID`) are exported in the shell the agent uses, not just your interactive terminal |
