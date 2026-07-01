"""Base class for conversation source adapters.

Each source adapter reads AI agent conversations from a specific tool
(Grok, Claude Code, Cursor, etc.) and returns structured data for
the daily digest pipeline.

To add a new source:
1. Create <name>_source.py in this directory
2. Subclass SourceAdapter
3. Implement discover_sessions() and extract_context()
4. The registry auto-discovers it on import
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class SessionMeta:
    """Metadata about a single conversation session."""

    session_id: str
    source: str  # e.g., "grok", "claude_code", "cursor"
    title: str
    created_at: str  # ISO 8601
    updated_at: str  # ISO 8601
    workspace: str  # project/cwd path
    model: str = ""
    branch: str = ""
    message_count: int = 0
    turn_count: int = 0
    tool_call_count: int = 0
    tools_used: list[str] = field(default_factory=list)
    duration_seconds: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """Extracted conversation context for LLM summarization."""

    meta: SessionMeta
    # Key user messages (first prompt + significant follow-ups)
    user_messages: list[str] = field(default_factory=list)
    # Key assistant responses (abbreviated)
    assistant_responses: list[str] = field(default_factory=list)
    # Raw text excerpt for summarization (capped at ~2000 chars)
    conversation_excerpt: str = ""


class SourceAdapter(ABC):
    """Abstract base for conversation source adapters.

    Subclasses must set `name` and implement discover + extract methods.
    """

    name: str = ""

    @abstractmethod
    def discover_sessions(self, target_date: date) -> list[SessionMeta]:
        """Find all sessions active on the given date.

        Args:
            target_date: The date to search for (YYYY-MM-DD).

        Returns:
            List of SessionMeta objects for sessions found.
        """
        ...

    @abstractmethod
    def extract_context(self, session: SessionMeta) -> SessionContext:
        """Extract conversation context from a discovered session.

        This provides enough content for the LLM to generate a summary
        and extract work items. Implementations should cap extracted text
        to keep context manageable (~2000 chars per conversation).

        Args:
            session: A SessionMeta from discover_sessions().

        Returns:
            SessionContext with messages and excerpt.
        """
        ...

    @staticmethod
    def extract_text(content: str | list | dict) -> str:
        """Extract plain text from various LLM content formats.

        Handles strings, lists of text blocks, and dicts with a "text" key.
        Shared across all source adapters to avoid duplication.
        """
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts).strip()
        if isinstance(content, dict):
            return content.get("text", "")
        return ""

    def collect(self, target_date: date) -> list[SessionContext]:
        """Full pipeline: discover sessions then extract context for each.

        Override if you need custom orchestration.
        """
        sessions = self.discover_sessions(target_date)
        contexts: list[SessionContext] = []
        for session in sessions:
            try:
                ctx = self.extract_context(session)
                contexts.append(ctx)
            except Exception as e:
                # Log but don't fail the whole source
                print(f"[{self.name}] Warning: failed to extract context "
                      f"for session {session.session_id}: {e}",
                      file=__import__('sys').stderr)
        return contexts
