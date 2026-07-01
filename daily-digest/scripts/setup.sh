#!/usr/bin/env bash
set -euo pipefail

# daily-digest setup script
# Verifies Python, installs dependencies, and tests Notion connectivity.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== daily-digest setup ==="
echo ""

# 1. Check Python version
echo "1. Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "   ❌ python3 not found. Install Python 3.10+."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "   ❌ Python $PYTHON_VERSION found. Need 3.10+."
    exit 1
fi
echo "   ✅ Python $PYTHON_VERSION"

# 2. Install notion-client
echo ""
echo "2. Installing Python dependencies..."
pip3 install --quiet 'notion-client>=2.2.1' 2>/dev/null || pip install --quiet 'notion-client>=2.2.1'
echo "   ✅ notion-client installed"

# 3. Check NOTION_TOKEN
echo ""
echo "3. Checking environment variables..."

if [ -z "${NOTION_TOKEN:-}" ]; then
    echo "   ❌ NOTION_TOKEN not set."
    echo ""
    echo "   To fix:"
    echo "   1. Go to https://www.notion.so/my-integrations"
    echo "   2. Create a new integration (name: 'Daily Digest')"
    echo "   3. Copy the Internal Integration Secret"
    echo "   4. Add to ~/.zshrc or ~/.bashrc:"
    echo "      export NOTION_TOKEN='your-secret-here'"
    echo "   5. Run: source ~/.zshrc"
    echo ""
    MISSING_TOKEN=1
else
    echo "   ✅ NOTION_TOKEN is set"
    MISSING_TOKEN=0
fi

if [ -z "${NOTION_DATABASE_ID:-}" ]; then
    echo "   ❌ NOTION_DATABASE_ID not set."
    echo ""
    echo "   To fix:"
    echo "   1. Create a database in Notion (see docs/SETUP.md for schema)"
    echo "   2. Share it with your 'Daily Digest' integration"
    echo "   3. Copy the database ID from the URL:"
    echo "      https://notion.so/<workspace>/<DATABASE_ID>?v=..."
    echo "   4. Add to ~/.zshrc or ~/.bashrc:"
    echo "      export NOTION_DATABASE_ID='your-database-id'"
    echo "   5. Run: source ~/.zshrc"
    echo ""
    MISSING_DB=1
else
    echo "   ✅ NOTION_DATABASE_ID is set"
    MISSING_DB=0
fi

# 4. Test Notion API connection
if [ "$MISSING_TOKEN" -eq 0 ] && [ "$MISSING_DB" -eq 0 ]; then
    echo ""
    echo "4. Testing Notion API connection..."
    python3 -c "
from notion_client import Client
import os

client = Client(auth=os.environ['NOTION_TOKEN'])
try:
    db = client.databases.retrieve(database_id=os.environ['NOTION_DATABASE_ID'])
    title_parts = db.get('title', [])
    title = title_parts[0]['plain_text'] if title_parts else '(untitled)'
    print(f'   ✅ Connected to database: {title}')
except Exception as e:
    print(f'   ❌ Connection failed: {e}')
    exit(1)
"
else
    echo ""
    echo "4. ⏭️  Skipping API test (missing environment variables)"
fi

# 5. Test collector
echo ""
echo "5. Testing session collector..."
cd "$SCRIPT_DIR"
RESULT=$(python3 collect_sessions.py --list-sources 2>/dev/null || echo '{"error": "failed"}')
echo "   Available sources: $RESULT"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  Run /daily-digest in Grok to generate today's digest"
echo "  Run /daily-digest 2026-06-30 to digest a specific date"
