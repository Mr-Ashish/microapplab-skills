#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
#  Hashnode MCP Server — Setup
#  Installs dependencies and prints configuration steps.
# ─────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$(dirname "$SCRIPT_DIR")/mcp-server"

echo "=== Hashnode MCP Server Setup ==="
echo ""

# 1. Install npm dependencies
echo "→ Installing dependencies..."
cd "$MCP_DIR"
npm install --silent
echo "  Done."
echo ""

# 2. Print the MCP server config the user needs to add
SERVER_PATH="$MCP_DIR/src/server.mjs"

echo "→ Add this to ~/.grok/config.toml:"
echo ""
cat <<EOF
[mcp_servers.hashnode]
command = "node"
args = ["$SERVER_PATH"]
env = { HASHNODE_PAT = "\${HASHNODE_PAT}", HASHNODE_PUBLICATION_ID = "\${HASHNODE_PUBLICATION_ID}" }
EOF
echo ""

# 3. Print credential instructions
echo ""
echo "→ Set these env vars in your shell profile (~/.zshrc or ~/.zprofile):"
echo ""
echo "  export HASHNODE_PAT=\"<your-personal-access-token>\""
echo "  export HASHNODE_PUBLICATION_ID=\"<your-publication-id>\""
echo ""
echo "→ Where to get your credentials:"
echo ""
echo "  HASHNODE_PAT (Personal Access Token):"
echo "    1. Go to https://hashnode.com/settings/developer"
echo "    2. Click 'Generate New Token'"
echo "    3. Copy the token"
echo ""
echo "  HASHNODE_PUBLICATION_ID:"
echo "    1. Go to your Hashnode blog dashboard"
echo "    2. The publication ID is the long string in the URL:"
echo "       https://hashnode.com/<THIS-LONG-ID>/dashboard"
echo ""
echo "  NOTE: Hashnode's GraphQL API requires a Pro plan (as of May 2026)."
echo "        Upgrade at your blog dashboard → Billing if needed."
echo ""
echo "→ After setting env vars, restart your terminal and Grok session."
echo "  Then run /publish-blog at the end of any conversation to test it."
echo ""
echo "=== Setup complete ==="