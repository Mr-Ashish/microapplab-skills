# AGENTS.md — microapplab-skills

## What This Repo Is

A collection of custom Grok/Claude Code skills. Each subdirectory is a self-contained skill with its own `SKILL.md`, optional scripts, and optional MCP server code.

## Repository Conventions

### Directory Layout

- **One skill per directory.** Directory name = skill name (lowercase, hyphenated).
- **`SKILL.md` is the entry point.** Every skill directory must have a `SKILL.md` at its root with YAML frontmatter (`name`, `description`).
- **Standalone scripts** (like `chrome-tabs`) live at the repo root without a wrapping directory.
- **MCP servers** go in `<skill>/mcp-server/` with their own `package.json`.
- **Setup scripts** go in `<skill>/scripts/`.

### Naming

- Skill directories: `kebab-case` (e.g., `publish-blog`, `fastapi-caching-fix`)
- SKILL.md `name` field must match the directory name exactly
- Scripts: `kebab-case` or `snake_case`, always with appropriate extension

### Writing SKILL.md Files

When creating or editing a `SKILL.md`:

1. **Frontmatter is mandatory.** Include `name` and `description` (with `Use when:` triggers).
2. **Be concrete.** Write step-by-step instructions the agent will follow. Avoid vague guidance.
3. **Include quality gates.** Add checklists or validation steps at the end.
4. **Banned phrases in skill output apply here too.** No "let's dive in", "game-changer", "in today's rapidly evolving landscape".
5. **Reference real tools.** If the skill uses MCP tools, specify the exact tool names and how to discover their schemas (via `search_tool`).

### Code Standards

- **JavaScript/TypeScript:** Use ESM (`import`/`export`), not CommonJS.
- **Shell scripts:** Include a shebang (`#!/bin/bash` or `#!/usr/bin/env bash`), use `set -euo pipefail`.
- **Python:** Follow PEP 8, use type hints.

## What NOT To Do

- **Do not commit `node_modules/`.** It is gitignored. Run `npm install` from the skill's `mcp-server/` directory.
- **Do not hardcode absolute paths** in SKILL.md files. Use `~/.grok/skills/<name>/` or relative references.
- **Do not modify another skill's directory** when working on a specific skill — each skill is independent.
- **Do not add secrets, API keys, or tokens** to any file. Use environment variables or `.env` files (which are gitignored).

## Build & Test

There is no global build system. Each skill is self-contained:

- **MCP servers:** `cd <skill>/mcp-server && npm install && node src/server.mjs`
- **Shell scripts:** Run directly (`bash <script>` or `chmod +x && ./<script>`)
- **Python scripts:** Use a venv if dependencies are needed

## Useful Context

- Skills are loaded by Grok at activation time by reading the `SKILL.md` file.
- The `description` field in frontmatter determines when the skill triggers — write clear, specific trigger phrases.
- Skills can reference other skills by name in a `## Related Skills` section.
- Analysis reports (like `fastapi-caching-fix/ANALYSIS_REPORT.md`) serve as reference material and don't need `SKILL.md` frontmatter.