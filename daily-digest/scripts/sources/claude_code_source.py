"""Claude Code CLI session source adapter.

Reads sessions from ~/.claude/projects/<encoded-path>/<session-id>.jsonl
Each JSONL file contains the full conversation: permission events, hook
outputs, user/assistant messages, and tool calls with results.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from .base import SessionContext, SessionMeta, SourceAdapter

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_USER_MESSAGES = 8
MAX_EXCERPT_CHARS = 3000


class ClaudeCodeSource(SourceAdapter):
    name = "claude_code"

    def discover_sessions(self, target_date: date) -> list[SessionMeta]:
        if not CLAUDE_PROJECTS_DIR.exists():
            return []

        sessions: list[SessionMeta] = []

        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            for session_file in project_dir.iterdir():
                if not session_file.name.endswith(".jsonl") or not session_file.is_file():
                    continue

                # Quick date check via file modification time (local timezone)
                mtime = datetime.fromtimestamp(os.path.getmtime(session_file))
                file_date = mtime.date()

                # Also check creation time for sessions started on target date
                # but not modified since
                try:
                    ctime = datetime.fromtimestamp(os.path.getctime(session_file))
                    create_date = ctime.date()
                except OSError:
                    create_date = file_date

                if file_date != target_date and create_date != target_date:
                    continue

                # Parse the session to verify and extract metadata
                meta = self._parse_session_file(session_file, project_dir, target_date)
                if meta:
                    sessions.append(meta)

        return sessions

    def extract_context(self, session: SessionMeta) -> SessionContext:
        session_file = Path(session.extra.get("session_file", ""))
        user_messages: list[str] = []
        assistant_responses: list[str] = []

        if session_file.exists():
            user_messages, assistant_responses = self._read_messages(session_file)

        # Build excerpt
        excerpt_parts: list[str] = []
        for msg in user_messages[:MAX_USER_MESSAGES]:
            excerpt_parts.append(f"User: {msg}")
        for resp in assistant_responses[:3]:
            excerpt_parts.append(f"Assistant: {resp}")

        excerpt = "\n\n".join(excerpt_parts)
        if len(excerpt) > MAX_EXCERPT_CHARS:
            excerpt = excerpt[:MAX_EXCERPT_CHARS] + "\n[...truncated]"

        return SessionContext(
            meta=session,
            user_messages=user_messages,
            assistant_responses=assistant_responses,
            conversation_excerpt=excerpt,
        )

    def _parse_session_file(
        self, session_file: Path, project_dir: Path, target_date: date
    ) -> SessionMeta | None:
        """Parse a .jsonl session file for metadata."""
        session_id = session_file.stem
        workspace = _decode_project_path(project_dir.name)

        first_timestamp: str = ""
        last_timestamp: str = ""
        user_msg_count = 0
        assistant_msg_count = 0
        tool_call_count = 0
        first_user_msg = ""
        files_touched: set[str] = set()
        has_target_date = False

        try:
            with open(session_file) as f:
                for line_num, line in enumerate(f):
                    if line_num > 500:  # Safety cap
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Track timestamps
                    ts = entry.get("timestamp", "")
                    if ts:
                        if not first_timestamp:
                            first_timestamp = ts
                        last_timestamp = ts

                        # Check if this entry is on target date
                        try:
                            entry_dt = datetime.fromisoformat(
                                ts.replace("Z", "+00:00")
                            )
                            if entry_dt.date() == target_date:
                                has_target_date = True
                        except ValueError:
                            pass

                    entry_type = entry.get("type", "")

                    if entry_type == "user":
                        user_msg_count += 1
                        msg = entry.get("message", {})
                        content = msg.get("content", "") if isinstance(msg, dict) else ""
                        if isinstance(content, str) and content and not first_user_msg:
                            first_user_msg = content[:200]

                    elif entry_type == "assistant":
                        assistant_msg_count += 1

                    elif entry_type == "tool_use":
                        tool_call_count += 1

                    elif entry_type == "tool_result":
                        # Extract file paths from tool results
                        content = entry.get("content", "")
                        if isinstance(content, str):
                            for word in content.split():
                                if "/" in word and any(
                                    word.endswith(ext)
                                    for ext in (".py", ".ts", ".js", ".tsx", ".jsx",
                                                ".md", ".json", ".yaml", ".yml",
                                                ".css", ".html", ".sh", ".rs", ".go")
                                ):
                                    files_touched.add(word.strip("'\"`,;:()"))

        except OSError:
            return None

        if not has_target_date:
            return None

        title = first_user_msg or f"Session {session_id[:8]}"

        return SessionMeta(
            session_id=session_id,
            source="claude_code",
            title=title,
            created_at=first_timestamp,
            updated_at=last_timestamp,
            workspace=workspace,
            message_count=user_msg_count + assistant_msg_count,
            turn_count=user_msg_count,
            tool_call_count=tool_call_count,
            files_changed=sorted(files_touched)[:20],
            extra={"session_file": str(session_file)},
        )

    def _read_messages(self, session_file: Path) -> tuple[list[str], list[str]]:
        """Read user and assistant messages from a session JSONL."""
        user_msgs: list[str] = []
        assistant_msgs: list[str] = []

        try:
            with open(session_file) as f:
                for line_num, line in enumerate(f):
                    if line_num > 500:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    entry_type = entry.get("type", "")

                    if entry_type == "user":
                        msg = entry.get("message", {})
                        content = ""
                        if isinstance(msg, dict):
                            content = self.extract_text(msg.get("content", ""))
                        if content:
                            if len(content) > 500:
                                content = content[:500] + "..."
                            user_msgs.append(content)

                    elif entry_type == "assistant":
                        msg = entry.get("message", {})
                        content = ""
                        if isinstance(msg, dict):
                            content = self.extract_text(msg.get("content", ""))
                        if content:
                            if len(content) > 500:
                                content = content[:500] + "..."
                            assistant_msgs.append(content)

        except OSError:
            pass

        return user_msgs, assistant_msgs


def _decode_project_path(encoded: str) -> str:
    """Decode Claude Code's project path encoding.

    Claude Code uses dashes for path separators:
    -Users-ashishmishra-Documents-project → /Users/ashishmishra/Documents/project

    Since real directories can also contain hyphens, we resolve against the
    filesystem to find the actual path. Falls back to naive replacement if
    the path can't be resolved.
    """
    if not encoded.startswith("-"):
        return encoded

    # Try to resolve the path by walking the filesystem
    parts = encoded.split("-")
    # First element is empty (leading dash), so parts[0] == ""
    resolved = "/"
    for part in parts[1:]:
        candidate = os.path.join(resolved, part)
        if os.path.exists(candidate):
            resolved = candidate
        else:
            # Try merging with previous segment (handles hyphenated dir names)
            merged = resolved.rstrip("/") + "-" + part
            if os.path.exists(merged):
                resolved = merged
            else:
                # Can't resolve — use the part as-is
                resolved = candidate

    return resolved
