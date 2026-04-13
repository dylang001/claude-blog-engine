#!/bin/bash
#
# Blog Engine — Install skills + scripts for Claude Code
# Copies skills to ~/.claude/skills/ and scripts to ~/.claude/blog-scripts/
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SOURCE="$SCRIPT_DIR/skills"
SCRIPTS_SOURCE="$SCRIPT_DIR/scripts"
SKILLS_TARGET="$HOME/.claude/skills"
SCRIPTS_TARGET="$HOME/.claude/blog-scripts"

# Check source files exist
if [ ! -d "$SKILLS_SOURCE" ]; then
  echo "Error: skills/ directory not found. Run this from the claude-blog-engine repo root."
  exit 1
fi

# Create target directories
mkdir -p "$SCRIPTS_TARGET"

# Copy skill directories
COPIED=0
for skill_dir in "$SKILLS_SOURCE"/blog-*/; do
  skill_name=$(basename "$skill_dir")
  mkdir -p "$SKILLS_TARGET/$skill_name"
  cp "$skill_dir/SKILL.md" "$SKILLS_TARGET/$skill_name/SKILL.md"
  echo "  Installed: /$skill_name"
  COPIED=$((COPIED + 1))
done

# Copy script files
SCRIPTS_COPIED=0
if [ -d "$SCRIPTS_SOURCE" ]; then
  for file in "$SCRIPTS_SOURCE"/*.py; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    cp "$file" "$SCRIPTS_TARGET/$filename"
    echo "  Installed script: $filename"
    SCRIPTS_COPIED=$((SCRIPTS_COPIED + 1))
  done
fi

echo ""
echo "Done — $COPIED skills + $SCRIPTS_COPIED scripts installed"
echo "  Skills:   $SKILLS_TARGET"
echo "  Scripts:  $SCRIPTS_TARGET"
echo ""
echo "Restart Claude Code, then run:"
echo "  /blog-hub                         see status & next step"
echo "  /blog-onboard https://yoursite.com one-time setup"
echo "  /blog-topics                       find 10 topics"
echo "  /blog-write                        write an article"
echo ""
echo "API keys: create a .env file in your project root."
echo "  Copy .env.example from this repo, or just run /blog-onboard"
echo "  and it will create the file for you automatically."
