#!/usr/bin/env python3
"""Sync daily digest data to Notion.

Usage:
    python notion_sync.py --input digest.json
    cat digest.json | python notion_sync.py --stdin
    python notion_sync.py --input digest.json --dry-run

Requires:
    pip install notion-client>=2.2.1

Environment variables:
    NOTION_TOKEN         - Notion integration secret
    NOTION_DATABASE_ID   - Target database ID

The script creates or updates a page in the target database for the
given date. It is idempotent — running twice for the same date updates
the existing page rather than creating a duplicate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError

    _HAS_NOTION_CLIENT = True
except ImportError:
    _HAS_NOTION_CLIENT = False


def _check_notion_client() -> None:
    """Verify notion-client is installed."""
    if not _HAS_NOTION_CLIENT:
        raise ImportError(
            "notion-client not installed. Run: pip install 'notion-client>=2.2.1'"
        )


def get_client() -> "Client":
    """Create a Notion client from environment variable."""
    _check_notion_client()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise EnvironmentError("NOTION_TOKEN environment variable not set.")
    return Client(auth=token)


def get_database_id() -> str:
    """Get target database ID from environment variable."""
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not db_id:
        raise EnvironmentError("NOTION_DATABASE_ID environment variable not set.")
    return db_id


def _ensure_projects_property(client: "Client", db_id: str) -> None:
    """Auto-create the Projects multi_select property if it doesn't exist."""
    try:
        ds_id = _resolve_data_source_id(client, db_id)
        ds = client.data_sources.retrieve(ds_id)
        props = ds.get("properties", {})
        if "Projects" not in props:
            client.data_sources.update(
                data_source_id=ds_id,
                properties={"Projects": {"multi_select": {"options": []}}},
            )
            print("Auto-created 'Projects' property in Notion database.",
                  file=sys.stderr)
    except Exception as e:
        print(f"Warning: could not ensure Projects property: {e}",
              file=sys.stderr)


def _resolve_data_source_id(client: Client, db_id: str) -> str:
    """Resolve the data_source_id from a database_id (notion-client v3+)."""
    db = client.databases.retrieve(db_id)
    data_sources = db.get("data_sources", [])
    if data_sources:
        return data_sources[0]["id"]
    return db_id  # fallback to db_id if no data_sources found


def find_existing_page(client: Client, db_id: str, target_date: str) -> str | None:
    """Check if a page for the given date already exists. Returns page ID or None."""
    try:
        ds_id = _resolve_data_source_id(client, db_id)
        response = client.data_sources.query(
            data_source_id=ds_id,
            filter={"property": "Day", "date": {"equals": target_date}},
            page_size=1,
        )
        results = response.get("results", [])
        if results:
            return results[0]["id"]
    except APIResponseError as e:
        print(f"Warning: failed to query database: {e}", file=sys.stderr)
    return None


def build_page_properties(digest: dict) -> dict:
    """Build Notion page properties from digest data."""
    target_date = digest["date"]
    dt = datetime.fromisoformat(target_date)
    day_name = dt.strftime("%A")
    date_title = f"{target_date} ({day_name})"

    conversations = digest.get("conversations", [])
    work_items = digest.get("work_items", {})

    sources_used = set()
    projects_used = set()
    for conv in conversations:
        sources_used.add(conv.get("source", "unknown"))
        project = conv.get("project", "")
        if project and project != "unknown":
            projects_used.add(project)

    props = {
        "Date": {"title": [{"text": {"content": date_title}}]},
        "Day": {"date": {"start": target_date}},
        "Conversations": {
            "rich_text": [
                {"type": "text", "text": {"content": str(len(conversations))}}
            ]
        },
        "Done": {"number": len(work_items.get("done", []))},
        "Pending": {"number": len(work_items.get("pending", []))},
        "In Progress": {"number": len(work_items.get("in_progress", []))},
        "Sources": {
            "multi_select": [{"name": s} for s in sorted(sources_used)]
        },
        "Status": {"select": {"name": "synced"}},
    }

    if projects_used:
        props["Projects"] = {
            "multi_select": [{"name": p} for p in sorted(projects_used)]
        }

    return props


def build_page_body(digest: dict) -> list[dict]:
    """Build Notion block children (page body) from digest data.

    Structure: project-first layout. Each project gets its own section with
    aggregated work items and conversation details nested underneath.
    """
    blocks: list[dict] = []
    conversations = digest.get("conversations", [])

    # ---- Group conversations by project ----
    from collections import OrderedDict

    project_groups: OrderedDict[str, list[dict]] = OrderedDict()
    for conv in conversations:
        project = conv.get("project", "unknown")
        if project not in project_groups:
            project_groups[project] = []
        project_groups[project].append(conv)

    # ---- Day-level summary line ----
    total_done = len(digest.get("work_items", {}).get("done", []))
    total_ip = len(digest.get("work_items", {}).get("in_progress", []))
    total_pending = len(digest.get("work_items", {}).get("pending", []))
    total_priority = len(digest.get("work_items", {}).get("priority", []))
    summary_parts = [
        f"{len(conversations)} conversations",
        f"{len(project_groups)} projects",
    ]
    counts = []
    if total_done:
        counts.append(f"✅ {total_done} done")
    if total_ip:
        counts.append(f"🔄 {total_ip} in progress")
    if total_pending:
        counts.append(f"⏳ {total_pending} pending")
    if total_priority:
        counts.append(f"🔥 {total_priority} priority")
    if counts:
        summary_parts.append(" · ".join(counts))

    blocks.append(_paragraph(" | ".join(summary_parts), bold=True))
    blocks.append(_divider())

    # ---- Per-project sections ----
    conv_counter = 0
    for project_name, project_convs in project_groups.items():
        # Aggregate work items for this project
        p_done: list[str] = []
        p_in_progress: list[str] = []
        p_pending: list[str] = []
        p_priority: list[str] = []
        for conv in project_convs:
            wi = conv.get("work_items", {})
            p_done.extend(wi.get("done", []))
            p_in_progress.extend(wi.get("in_progress", []))
            p_pending.extend(wi.get("pending", []))
            p_priority.extend(wi.get("priority", []))

        # Project heading with session count
        blocks.append(
            _heading2(f"📁 {project_name} ({len(project_convs)} sessions)")
        )

        # -- Work items for this project --
        blocks.append(_heading3("📋 Work Items"))

        if p_done:
            blocks.append(_paragraph("✅ Done", bold=True))
            for item in p_done:
                blocks.append(_bullet(item))

        if p_in_progress:
            blocks.append(_paragraph("🔄 In Progress", bold=True))
            for item in p_in_progress:
                blocks.append(_bullet(item))

        if p_pending:
            blocks.append(_paragraph("⏳ Pending", bold=True))
            for item in p_pending:
                blocks.append(_bullet(item))

        if p_priority:
            blocks.append(_paragraph("🔥 Priority", bold=True))
            for item in p_priority:
                blocks.append(_bullet(item))

        if not any([p_done, p_in_progress, p_pending, p_priority]):
            blocks.append(_bullet("No work items recorded"))

        # -- Conversations for this project --
        blocks.append(_heading3("💬 Conversations"))

        for conv in project_convs:
            conv_counter += 1
            title = conv.get("title", "Untitled")
            source = conv.get("source", "unknown")
            blocks.append(_paragraph(f"{conv_counter}. {title} ({source})", bold=True))

            # Metadata line
            meta_parts = []
            if conv.get("duration_seconds"):
                mins = conv["duration_seconds"] // 60
                meta_parts.append(f"Duration: {mins} min")
            if conv.get("message_count"):
                meta_parts.append(f"Messages: {conv['message_count']}")
            if conv.get("model"):
                meta_parts.append(f"Model: {conv['model']}")
            if conv.get("branch"):
                meta_parts.append(f"Branch: {conv['branch']}")

            if meta_parts:
                blocks.append(_paragraph(" · ".join(meta_parts)))

            # Summary
            summary = conv.get("summary", "")
            if summary:
                blocks.append(_paragraph(summary))

            # Key decisions
            decisions = conv.get("decisions", [])
            if decisions:
                blocks.append(_paragraph("Key Decisions:", bold=True))
                for decision in decisions:
                    blocks.append(_bullet(decision))

            # Files changed
            files = conv.get("files_changed", [])
            if files:
                files_text = ", ".join(f"`{f}`" for f in files[:10])
                if len(files) > 10:
                    files_text += f" (+{len(files) - 10} more)"
                blocks.append(_paragraph(f"Files: {files_text}"))

        blocks.append(_divider())

    return blocks


def sync_to_notion(digest: dict, dry_run: bool = False) -> dict:
    """Sync a digest to Notion. Returns status info."""
    if dry_run:
        props = build_page_properties(digest)
        body = build_page_body(digest)
        return {
            "status": "dry_run",
            "properties": props,
            "blocks_count": len(body),
            "date": digest["date"],
        }

    client = get_client()
    db_id = get_database_id()
    target_date = digest["date"]

    properties = build_page_properties(digest)
    body_blocks = build_page_body(digest)

    # Ensure Projects property exists in the data source schema
    if "Projects" in properties:
        _ensure_projects_property(client, db_id)

    # Check for existing page (idempotency)
    existing_page_id = find_existing_page(client, db_id, target_date)

    if existing_page_id:
        # Update existing page properties
        client.pages.update(page_id=existing_page_id, properties=properties)

        # Clear existing body blocks and replace
        existing_blocks = client.blocks.children.list(block_id=existing_page_id)
        for block in existing_blocks.get("results", []):
            try:
                client.blocks.delete(block_id=block["id"])
            except APIResponseError as e:
                print(f"Warning: failed to delete block {block['id']}: {e}",
                      file=sys.stderr)

        # Add new body blocks (Notion API limits to 100 blocks per call)
        for i in range(0, len(body_blocks), 100):
            chunk = body_blocks[i : i + 100]
            client.blocks.children.append(
                block_id=existing_page_id, children=chunk
            )

        return {
            "status": "updated",
            "page_id": existing_page_id,
            "date": target_date,
            "blocks_count": len(body_blocks),
        }
    else:
        # Create new page
        page = client.pages.create(
            parent={"database_id": db_id},
            properties=properties,
            children=body_blocks[:100],  # First 100 blocks with create
        )
        page_id = page["id"]

        # Append remaining blocks if any
        if len(body_blocks) > 100:
            for i in range(100, len(body_blocks), 100):
                chunk = body_blocks[i : i + 100]
                client.blocks.children.append(
                    block_id=page_id, children=chunk
                )

        return {
            "status": "created",
            "page_id": page_id,
            "date": target_date,
            "blocks_count": len(body_blocks),
        }


# ---- Notion Block Helpers ----

# Notion API limits rich_text content to 2000 characters
_MAX_NOTION_TEXT = 2000


def _truncate(text: str) -> str:
    """Truncate text to Notion's 2000-char limit."""
    if len(text) > _MAX_NOTION_TEXT:
        return text[: _MAX_NOTION_TEXT - 15] + " [...truncated]"
    return text


def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _paragraph(text: str, bold: bool = False) -> dict:
    text = _truncate(text)
    annotations = {}
    if bold:
        annotations["bold"] = True

    rich_text_item: dict = {"type": "text", "text": {"content": text}}
    if annotations:
        rich_text_item["annotations"] = annotations

    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [rich_text_item]},
    }


def _bullet(text: str) -> dict:
    text = _truncate(text)
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        },
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


# ---- Main ----

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync daily digest to Notion")
    parser.add_argument(
        "--input",
        type=str,
        help="Path to digest JSON file",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read digest JSON from stdin",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without calling Notion API",
    )

    args = parser.parse_args()

    if args.stdin:
        digest_json = sys.stdin.read()
    elif args.input:
        digest_json = Path(args.input).read_text()
    else:
        print("Error: provide --input <file> or --stdin", file=sys.stderr)
        sys.exit(1)

    try:
        digest = json.loads(digest_json)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        result = sync_to_notion(digest, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    except (ImportError, EnvironmentError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error syncing to Notion: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
