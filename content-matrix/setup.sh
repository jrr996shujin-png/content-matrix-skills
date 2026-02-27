#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  📣 Content Matrix - 跨平台内容分发"
echo "═══════════════════════════════════════════════════════"
echo ""

# Check Python
echo -e "${YELLOW}[1/3]${NC} Checking Python..."
if command -v python3 &> /dev/null; then
    echo -e "  ✅ $(python3 --version)"
else
    echo "  ❌ Python 3 required"; exit 1
fi

# Install deps
echo -e "${YELLOW}[2/3]${NC} Installing dependencies..."
pip3 install requests openai tweepy praw --quiet 2>/dev/null || \
pip3 install requests openai tweepy praw --quiet --break-system-packages 2>/dev/null
echo -e "  ✅ Core deps installed"
echo -e "  📝 Optional: pip install playwright && playwright install chromium (for 小红书 + HN)"
echo -e "  📝 Optional: pip install anthropic (for Claude models)"

# Remind about config
echo -e "${YELLOW}[3/3]${NC} Configuration..."
echo -e "  📝 Edit ${CYAN}configs/my_style.json${NC} with your personal style"
echo ""

echo "═══════════════════════════════════════════════════════"
echo -e "  ${GREEN}✅ Ready!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Set your API key:"
echo "  export OPENAI_API_KEY='sk-...'"
echo ""
echo "Quick start:"
echo '  # 1. Check which platforms are ready'
echo '  python3 skills/auto_publisher.py --check-setup'
echo ""
echo '  # 2. Dry run (generate + preview, no publish)'
echo '  python3 skills/auto_publisher.py "你的母体内容" --dry-run'
echo ""
echo '  # 3. Full pipeline (generate → preview → confirm → publish → track)'
echo '  python3 skills/auto_publisher.py "你的母体内容"'
echo ""
echo '  # 4. Monitor engagement 24h'
echo '  python3 skills/engagement_tracker.py monitor'
echo ""
echo -e "${CYAN}Important:${NC} Edit configs/my_style.json to teach AI your writing voice!"
echo ""
