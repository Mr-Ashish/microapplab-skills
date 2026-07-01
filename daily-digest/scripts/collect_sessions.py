#!/usr/bin/env python3
"""Collect AI agent conversation sessions from all registered sources.

Usage:
    python collect_sessions.py                     # Today's sessions
    python collect_sessions.py --date 2026-07-01   # Specific date
    python collect_sessions.py --source grok       # Single source only
    python collect_sessions.py --output /tmp/out.json  # Write to file

Outputs JSON to stdout (or file) with all discovered sessions and their
extracted context, ready for LLM summarization.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone

# Ensure the script can import the sources package
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sources import get_all_sources, get_source, list_source_names


def collect(target_date: date, source_name: str | None = None) -> dict:
    """Collect sessions from all (or one) source for the given date.

    Returns a dict with:
    {
        "date": "2026-07-01",
        "collected_at": "<ISO timestamp>",
        "sources_queried": ["grok", "claude_code", "cursor"],
        "sources_succeeded": ["grok", "cursor"],
        "sources_failed": {"claude_code": "error message"},
        "total_sessions": 7,
        "sessions": [ ... SessionContext dicts ... ]
    }
    """
    if source_name:
        adapter = get_source(source_name)
        if not adapter:
            available = list_source_names()
            return {
                "error": f"Unknown source '{source_name}'. Available: {available}",
                "date": target_date.isoformat(),
            }
        adapters = [adapter]
    else:
        adapters = get_all_sources()

    sources_queried: list[str] = []
    sources_succeeded: list[str] = []
    sources_failed: dict[str, str] = {}
    all_sessions: list[dict] = []

    for adapter in adapters:
        sources_queried.append(adapter.name)
        try:
            contexts = adapter.collect(target_date)
            sources_succeeded.append(adapter.name)
            for ctx in contexts:
                session_dict = asdict(ctx)
                all_sessions.append(session_dict)
        except Exception as e:
            sources_failed[adapter.name] = str(e)
            print(f"[collect] Error from {adapter.name}: {e}", file=sys.stderr)

    # Sort by created_at timestamp
    all_sessions.sort(key=lambda s: s.get("meta", {}).get("created_at", ""))

    return {
        "date": target_date.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "sources_queried": sources_queried,
        "sources_succeeded": sources_succeeded,
        "sources_failed": sources_failed,
        "total_sessions": len(all_sessions),
        "sessions": all_sessions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect AI agent sessions for a given date"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Collect from a single source only (e.g., grok, claude_code, cursor)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write JSON to file instead of stdout",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List all registered source adapters and exit",
    )

    args = parser.parse_args()

    if args.list_sources:
        names = list_source_names()
        print(json.dumps({"sources": names}, indent=2))
        return

    # Parse target date
    if args.date:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            print(f"Error: invalid date format '{args.date}'. Use YYYY-MM-DD.",
                  file=sys.stderr)
            sys.exit(1)
    else:
        target = date.today()

    # Collect
    result = collect(target, source_name=args.source)

    # Output
    output_json = json.dumps(result, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(output_json)
        print(f"Wrote {result['total_sessions']} sessions to {args.output}",
              file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
