"""Grok session source adapter.

Reads sessions from ~/.grok/sessions/<url-encoded-cwd>/<session-uuid>/
Each session directory contains:
  - summary.json: metadata (title, timestamps, model, message counts)
  - signals.json: stats (turns, tool calls, duration, lines changed)
  - chat_history.jsonl: raw messages (system/user/assistant)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from urllib.parse import unquote

from .base import SessionContext, SessionMeta, SourceAdapter

# Cap per-conversation excerpt to keep LLM context manageable
MAX_USER_MESSAGES = 8
MAX_EXCERPT_CHARS = 3000
GROK_SESSIONS_DIR = Path.home() / ".grok" / "sessions"


class GrokSource(SourceAdapter):
    name = "grok"

    def discover_sessions(self, target_date: date) -> list[SessionMeta]:
        if not GROK_SESSIONS_DIR.exists():
            return []

        sessions: list[SessionMeta] = []

        # Walk all workspace directories (URL-encoded paths)
        for workspace_dir in GROK_SESSIONS_DIR.iterdir():
            if not workspace_dir.is_dir():
                continue
            # Skip non-session dirs (e.g., sqlite files)
            if workspace_dir.suffix in (".sqlite", ".json", ".jsonl"):
                continue

            for session_dir in workspace_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                summary_file = session_dir / "summary.json"
                if not summary_file.exists():
                    continue

                try:
                    summary = json.loads(summary_file.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                # Check if session was active on target date
                if not self._is_on_date(summary, target_date):
                    continue

                meta = self._parse_summary(summary, session_dir)
                sessions.append(meta)

        return sessions

    def extract_context(self, session: SessionMeta) -> SessionContext:
        session_dir = Path(session.extra.get("session_dir", ""))
        user_messages: list[str] = []
        assistant_responses: list[str] = []

        # Read chat history for conversation content
        chat_file = session_dir / "chat_history.jsonl"
        if chat_file.exists():
            user_messages, assistant_responses = self._read_chat_history(chat_file)

        # Build excerpt from user messages
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

    def _is_on_date(self, summary: dict, target_date: date) -> bool:
        """Check if session was active on the target date."""
        for field in ("last_active_at", "created_at", "updated_at"):
            ts = summary.get(field)
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.date() == target_date:
                    return True
            except (ValueError, AttributeError):
                continue
        return False

    def _parse_summary(self, summary: dict, session_dir: Path) -> SessionMeta:
        """Parse summary.json into SessionMeta."""
        info = summary.get("info", {})
        session_id = info.get("id", session_dir.name)
        cwd = info.get("cwd", "")

        # Read signals for stats
        signals = self._read_signals(session_dir / "signals.json")

        # Decode workspace path from URL-encoded directory name
        workspace = cwd or _url_decode(session_dir.parent.name)

        return SessionMeta(
            session_id=session_id,
            source="grok",
            title=summary.get("generated_title", summary.get("session_summary", "Untitled")),
            created_at=summary.get("created_at", ""),
            updated_at=summary.get("updated_at", summary.get("last_active_at", "")),
            workspace=workspace,
            model=summary.get("current_model_id", ""),
            branch=summary.get("head_branch", ""),
            message_count=summary.get("num_messages", 0),
            turn_count=signals.get("turnCount", 0),
            tool_call_count=signals.get("toolCallCount", 0),
            tools_used=signals.get("toolsUsed", []),
            duration_seconds=signals.get("sessionDurationSeconds", 0),
            lines_added=signals.get("linesAdded", 0),
            lines_removed=signals.get("linesRemoved", 0),
            extra={
                "session_dir": str(session_dir),
                "agent_name": summary.get("agent_name", ""),
                "num_chat_messages": summary.get("num_chat_messages", 0),
            },
        )

    def _read_signals(self, signals_file: Path) -> dict:
        """Read signals.json for session stats."""
        if not signals_file.exists():
            return {}
        try:
            data = json.loads(signals_file.read_text())
            # Flatten nested stats
            result = {}
            for key in ("turnCount", "toolCallCount", "toolsUsed", "modelsUsed",
                         "sessionDurationSeconds", "contextTokensUsed"):
                if key in data:
                    result[key] = data[key]
            # Lines added/removed may be nested
            lines = data.get("linesChanged", {})
            result["linesAdded"] = lines.get("added", 0)
            result["linesRemoved"] = lines.get("removed", 0)
            return result
        except (json.JSONDecodeError, OSError):
            return {}

    def _read_chat_history(self, chat_file: Path) -> tuple[list[str], list[str]]:
        """Read user and assistant messages from chat_history.jsonl."""
        user_msgs: list[str] = []
        assistant_msgs: list[str] = []

        try:
            with open(chat_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = entry.get("type", "")
                    content = self.extract_text(entry.get("content", ""))

                    if not content:
                        continue

                    if msg_type == "user":
                        # Cap individual message length
                        if len(content) > 500:
                            content = content[:500] + "..."
                        user_msgs.append(content)
                    elif msg_type == "assistant":
                        if len(content) > 500:
                            content = content[:500] + "..."
                        assistant_msgs.append(content)
        except OSError:
            pass

        return user_msgs, assistant_msgs

def _url_decode(encoded: str) -> str:
    """Decode URL-encoded path component."""
    return unquote(encoded)
