#!/bin/bash
#
# Blog Engine — Install commands + scripts for Claude Code
# Copies commands to ~/.claude/commands/ and scripts to ~/.claude/blog-scripts/
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMANDS_DIR="$HOME/.claude/commands"
SCRIPTS_DIR="$HOME/.claude/blog-scripts"
SOURCE_DIR="$SCRIPT_DIR/commands"
SOURCE_SCRIPTS="$SCRIPT_DIR/scripts"

# Check source files exist
if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: commands/ directory not found. Run this from the claude-blog-engine repo root."
  exit 1
fi

# Create target directories
mkdir -p "$COMMANDS_DIR"
mkdir -p "$SCRIPTS_DIR"

# Copy command files
COPIED=0
for file in "$SOURCE_DIR"/blog-*.md; do
  filename=$(basename "$file")
  cp "$file" "$COMMANDS_DIR/$filename"
  echo "  Installed: /user:${filename%.md}"
  COPIED=$((COPIED + 1))
done

# Copy script files
SCRIPTS_COPIED=0
if [ -d "$SOURCE_SCRIPTS" ]; then
  for file in "$SOURCE_SCRIPTS"/*.py; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    cp "$file" "$SCRIPTS_DIR/$filename"
    echo "  Installed script: $filename"
    SCRIPTS_COPIED=$((SCRIPTS_COPIED + 1))
  done
fi

echo ""
echo "Done — $COPIED commands + $SCRIPTS_COPIED scripts installed"
echo "  Commands:  $COMMANDS_DIR"
echo "  Scripts:   $SCRIPTS_DIR"
echo ""
echo "Restart Claude Code, then run:"
echo "  /user:blog-hub                         see status & next step"
echo "  /user:blog-onboard https://yoursite.com one-time setup"
echo "  /user:blog-topics                       find 10 topics"
echo "  /user:blog-write                        write an article"
echo ""
echo "API keys: create a .env file in your project root."
echo "  Copy .env.example from this repo, or just run /user:blog-onboard"
echo "  and it will create the file for you automatically."
