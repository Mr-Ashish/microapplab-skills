# microapplab-skills

Custom skills and tools for [Grok](https://github.com/xAI/grok) (Claude Code). Each subdirectory is a self-contained skill that can be installed into `~/.grok/skills/` or referenced directly.

## Skills

| Skill | Type | Description |
|---|---|---|
| **publish-blog** | Skill + MCP server | Turns any agent conversation into a polished Hashnode blog post. Auto-detects format (problem→solution, tutorial, TIL), enforces clear writing, publishes via Hashnode MCP. |
| **fastapi-caching-fix** | Analysis / Reference | Deep-dive into FastAPI `Depends()` + `lru_cache` interaction — documents a critical cross-user data leak under concurrent load. |
| **chrome-tabs** | Shell script | Browser tab management utility. |

## Repository Structure

```
skills/
├── AGENTS.md              # Guidance for AI agents working in this repo
├── README.md              # This file
├── .gitignore
├── <skill-name>/          # One directory per skill
│   ├── SKILL.md           # Skill definition (required for Grok skills)
│   ├── scripts/           # Setup scripts, helpers
│   ├── mcp-server/        # MCP server source (if the skill ships one)
│   └── ...
└── <script-name>          # Standalone scripts (no SKILL.md needed)
```

## Adding a New Skill

1. Create a directory named after your skill (lowercase, hyphenated):
   ```
   mkdir my-new-skill
   ```

2. Add a `SKILL.md` at the root of that directory. This file defines when the skill activates, what it does, and how it works. See `publish-blog/SKILL.md` for a full example.

3. (Optional) Add supporting files:
   - `scripts/setup.sh` — one-time setup (install deps, configure MCP, etc.)
   - `mcp-server/` — if the skill needs its own MCP server
   - Reference docs, templates, or analysis reports

4. Commit and push.

## Installing a Skill

Symlink or copy the skill directory into your Grok skills folder:

```bash
# Symlink (recommended — stays in sync with git pulls)
ln -s "$(pwd)/my-new-skill" ~/.grok/skills/my-new-skill

# Or copy
cp -r my-new-skill ~/.grok/skills/
```

## SKILL.md Format

Every skill needs a `SKILL.md` with YAML frontmatter:

```yaml
---
name: my-skill-name
description: >
  One-paragraph description of what the skill does.
  Use when: trigger phrases or conditions.
---
```

Below the frontmatter, write the full skill instructions — steps, rules, templates, quality gates. The agent reads this at activation time, so be precise and concrete.

## License

Private — personal use only.