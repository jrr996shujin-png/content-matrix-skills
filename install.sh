#!/bin/bash
# Install content-matrix-skills into OpenClaw or Claude Code
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCLAW_SKILLS="$HOME/.openclaw/skills"
CLAUDE_SKILLS=".claude/skills"

echo "📣 content-matrix-skills installer"
echo "=================================="
echo ""

# Detect target
if [ -d "$OPENCLAW_SKILLS" ]; then
    TARGET="$OPENCLAW_SKILLS"
    echo "✅ Detected OpenClaw at $TARGET"
elif [ -d "$CLAUDE_SKILLS" ]; then
    TARGET="$CLAUDE_SKILLS"
    echo "✅ Detected Claude Code at $TARGET"
else
    # Default to OpenClaw
    TARGET="$OPENCLAW_SKILLS"
    mkdir -p "$TARGET"
    echo "📁 Created $TARGET"
fi

echo ""

# Install content-matrix skill
echo "📦 Installing content-matrix..."
rm -rf "$TARGET/content-matrix"
cp -r "$SCRIPT_DIR/content-matrix" "$TARGET/content-matrix"
echo "   ✅ content-matrix installed"

# Install reddit-cultivate skill
echo "📦 Installing reddit-cultivate..."
rm -rf "$TARGET/reddit-cultivate"
cp -r "$SCRIPT_DIR/reddit-cultivate" "$TARGET/reddit-cultivate"
echo "   ✅ reddit-cultivate installed"

echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install openai requests tweepy --quiet --break-system-packages 2>/dev/null || \
pip3 install openai requests tweepy --quiet 2>/dev/null || \
echo "   ⚠️  Could not auto-install. Run manually: pip install openai requests tweepy"

echo ""
echo "=================================="
echo "✅ Installation complete!"
echo ""
echo "Skills installed to: $TARGET"
echo ""
echo "Next steps:"
echo "  1. Restart OpenClaw or start a new session"
echo "  2. Set up platform credentials:"
echo ""
echo "     # LinkedIn (free)"
echo "     python3 $TARGET/content-matrix/skills/publishers/linkedin_publisher.py --setup"
echo ""
echo "     # X/Twitter (requires developer account)"
echo "     export TWITTER_API_KEY='...'"
echo "     export TWITTER_API_SECRET='...'"
echo "     export TWITTER_ACCESS_TOKEN='...'"
echo "     export TWITTER_ACCESS_SECRET='...'"
echo ""
echo "     # Reddit (macOS only — enable Chrome JS access)"
echo "     # Chrome → View → Developer → Allow JavaScript from Apple Events"
echo ""
echo "  3. Edit your personal style:"
echo "     $TARGET/content-matrix/configs/my_style.json"
echo ""
echo "  4. Try it:"
echo "     python3 $TARGET/content-matrix/skills/content_adapter.py \"Your content here\""
echo ""
