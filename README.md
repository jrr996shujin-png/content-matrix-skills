# 📣 content-matrix-skills

**Cross-platform content distribution skill pack for [OpenClaw](https://openclaw.ai) — generate, adapt, and auto-publish content to X, LinkedIn, and Reddit from one command.**

You write content once. AI adapts it to each platform's native style, tone, and format. Then publishers push it out — LinkedIn via API, X via API, Reddit via browser automation (AppleScript + Chrome, inspired by [PHY041/claude-skill-reddit](https://github.com/PHY041/claude-skill-reddit)).

This skill pack gives your OpenClaw agent the ability to:

* ✍️ **Generate** platform-native versions of any content for 3 platforms (X, LinkedIn, Reddit)
* 🚀 **Publish** directly to X (Twitter), LinkedIn, and Reddit without leaving your terminal
* 🦀 **Cultivate** Reddit karma automatically with anti-shadowban safeguards (for new accounts)
* 📊 **Track** post engagement across all platforms

## Skills Overview

| Skill | What It Does | Trigger Examples |
| --- | --- | --- |
| [`content-matrix`](#content-matrix) | Transform one piece of content into platform-native versions for X, LinkedIn, and Reddit | *"Distribute this content to all platforms"* *"Generate a LinkedIn version of this"* |
| [`reddit-cultivate`](#reddit-cultivate) | Auto-grow Reddit karma by commenting on rising posts with AI-generated, value-first responses | *"Help me grow my Reddit account"* *"Comment on r/indiehackers posts"* |

### How They Work Together

```
┌──────────────────────────────┐
│       content-matrix         │
│   (generate + adapt content) │
└──────┬───────┬───────┬───────┘
       │       │       │
       ▼       ▼       ▼
   ┌───────┐ ┌────┐ ┌────────┐
   │LinkedIn│ │ X  │ │ Reddit │
   │  API   │ │API │ │Chrome  │
   │ (free) │ │($) │ │(free)  │
   └───────┘ └────┘ └───┬────┘
                        │
              account too new?
              CAPTCHA blocking?
                        │
                        ▼
              ┌──────────────────┐
              │ reddit-cultivate │
              │ (build karma     │
              │  until CAPTCHA   │
              │  goes away)      │
              └──────────────────┘
```

---

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/jrr996shujin-png/content-matrix-skills.git

# Run the installer
cd content-matrix-skills
bash install.sh
```

This copies both skills into `~/.openclaw/skills/`. Restart OpenClaw or start a new session to pick them up.

### Platform Setup

#### LinkedIn (Free — API)

```bash
# Run OAuth setup wizard
python3 ~/.openclaw/skills/content-matrix/skills/publishers/linkedin_publisher.py --setup
# Follow prompts → get access token
export LINKEDIN_ACCESS_TOKEN='your-token-here'
```

Requires a [LinkedIn Developer App](https://www.linkedin.com/developers/apps) with "Share on LinkedIn" (w_member_social) permission. Token expires every 60 days.

#### X / Twitter (Prepaid — minimum $5, ~$0.01 per tweet)

```bash
export TWITTER_API_KEY='...'
export TWITTER_API_SECRET='...'
export TWITTER_ACCESS_TOKEN='...'
export TWITTER_ACCESS_SECRET='...'
pip install tweepy
```

Requires a [Twitter Developer Account](https://developer.twitter.com). Uses a prepaid credit system — minimum top-up is $5, which is enough for hundreds of tweets (~$0.01 each). Credits never expire.

> **💡 Tip:** $5 is all you need to get started. One top-up lasts months for typical indie hacker posting frequency.

#### Reddit (Free — Browser Automation)

No API key needed. Uses AppleScript + Chrome (macOS only), inspired by [PHY041/claude-skill-reddit](https://github.com/PHY041/claude-skill-reddit).

```bash
# 1. Enable Chrome JavaScript access
# Chrome → View → Developer → Allow JavaScript from Apple Events → Restart Chrome

# 2. Log into Reddit in Chrome

# 3. Test
python3 ~/.openclaw/skills/content-matrix/skills/publishers/reddit_publisher.py --check-login
```

> **⚠️ New Reddit accounts** (low karma) will trigger CAPTCHA when posting. Use the `reddit-cultivate` skill to build karma first, or post manually until CAPTCHA stops appearing.

### Try It

Message your OpenClaw:

```
"把这篇关于AI工具的文章发到所有平台"
"Generate X + LinkedIn + Reddit versions of this blog post"
"Help me grow my Reddit karma on r/indiehackers"
"Post this to LinkedIn"
```

Or from the terminal:

```bash
# Generate content for all platforms
python3 ~/.openclaw/skills/content-matrix/skills/content_adapter.py "We tested AI video editing and found 3 surprising problems"

# Publish to LinkedIn
python3 ~/.openclaw/skills/content-matrix/skills/publishers/linkedin_publisher.py --text "Your post content here"

# Publish to X
python3 ~/.openclaw/skills/content-matrix/skills/publishers/x_publisher.py "Your tweet here"

# Publish to Reddit (browser automation)
python3 ~/.openclaw/skills/content-matrix/skills/publishers/reddit_publisher.py \
  --title "Your title" --body "Your post" --subreddit indiehackers
```

---

## Skills in Detail

### `content-matrix`

**What it does:** Takes one piece of "mother content" and generates platform-native versions for 3 platforms simultaneously. Each version follows platform-specific rules for tone, format, length, and audience expectations.

**Why not just use ChatGPT?** Because ChatGPT requires you to ask one platform at a time, re-describe your style every time, and has no built-in knowledge of platform-specific rules. Content Matrix generates all versions at once with a rules engine and style learning.

**Platforms:**

| Platform | Language | Auto-Publish | Key Adaptations |
| --- | --- | --- | --- |
| X (Twitter) | English | ✅ via API ($5 prepaid) | Single tweet (≤280 chars) + Thread (5-8 tweets), opinionated tone |
| LinkedIn | English | ✅ via API (free) | Professional narrative, first 3 lines hook, links in comments |
| Reddit | English | ✅ via Chrome (free) | Authentic storytelling, admit failures, suggest subreddit + flair |

**Features:**
- **Platform Rules Engine** — not just translation, each platform has a full rule set (`configs/platform_rules.json`)
- **Personal Style Learning** — paste your old posts into `configs/my_style.json`, AI learns your voice
- **Cost Transparency** — preview token usage before generating (`--plan`)
- **Multi-Model Support** — OpenAI, Anthropic, DeepSeek, Kimi, Ollama (local/free)

**Usage:**

```bash
# All platforms
python3 skills/content_adapter.py "Your content here"

# Specific platforms only
python3 skills/content_adapter.py "Your content" --platforms x,reddit,linkedin

# Preview cost first
python3 skills/content_adapter.py "Your content" --plan

# Use cheaper model
python3 skills/content_adapter.py "Your content" --base-url https://api.deepseek.com --model deepseek-chat
```

---

### `reddit-cultivate`

**What it does:** Automatically builds Reddit karma by finding rising posts in target subreddits and posting thoughtful, AI-generated comments. Designed specifically for new accounts that need karma before the `content-matrix` Reddit publisher can work without CAPTCHA.

**Why it exists:** New Reddit accounts trigger CAPTCHA on every post, blocking automation. Once you reach ~20-50 karma, CAPTCHA disappears and the Reddit publisher works fully automatically. This skill bridges that gap.

**Anti-Shadowban Safeguards:**

| Rule | Setting | Why |
| --- | --- | --- |
| Max comments per session | 5 (hard cap) | Reddit flags accounts that comment in bursts |
| Delay between comments | 45-90 seconds (randomized) | Fixed intervals look like bots |
| Max sessions per day | 2, 6+ hours apart | Spread activity throughout the day |
| Post age filter | Only posts < 6 hours old | Commenting on old posts is suspicious |
| Auto-upvote | Upvotes post before commenting | Mimics natural user behavior |
| Duplicate prevention | Logs all commented posts | Never comments on same post twice |
| Skip days | Aim for 4-5 days/week | Daily activity without exception is a red flag |

**Comment Quality Rules (enforced in SKILL.md):**
- NO self-promotion, NO generic responses ("Great post!")
- Minimum 2-3 sentences with specific reference to post content
- Add personal perspective or experience
- Casual Reddit tone — contractions, humor, lowercase
- Varied sentence starters (not every comment begins the same way)

**Usage:**

```bash
# Check account status
python3 scripts/reddit_cultivate.py --check-only

# Preview mode (no actual posting)
python3 scripts/reddit_cultivate.py --dry-run --subreddits "indiehackers,startups"

# Run cultivation
python3 scripts/reddit_cultivate.py --subreddits "indiehackers,SideProject,startups,technology" --max-comments 5

# Check for shadowban
python3 scripts/reddit_cultivate.py --check-shadowban
```

**Requirements:**
- macOS only (AppleScript)
- Chrome with "Allow JavaScript from Apple Events" enabled
- Logged into Reddit in Chrome

---

## Platform Cost Comparison

| Platform | API Cost | Setup Difficulty | Auto-Publish |
| --- | --- | --- | --- |
| **LinkedIn** | Free | Medium (OAuth setup) | ✅ Yes |
| **X (Twitter)** | Prepaid min $5 (~$0.01/tweet) | Easy (API keys) | ✅ Yes |
| **Reddit** | Free | Easy (just login in Chrome) | ✅ Yes (macOS) |

> **Total cost for indie hackers:** $5 one-time top-up for X, everything else free. The content generation itself costs ~$0.01 per run with gpt-4o-mini, or $0 with Ollama local models.

---

## Directory Structure

```
~/.openclaw/skills/                          (after installation)
├── content-matrix/
│   ├── SKILL.md                             ← OpenClaw skill definition
│   ├── setup.sh
│   ├── .env.example
│   ├── configs/
│   │   ├── platform_rules.json              ← Platform-specific content rules
│   │   ├── publish_timing.json              ← Best posting times per platform
│   │   ├── my_style.json                    ← Your personal style (edit this!)
│   │   └── competitors.json
│   ├── skills/
│   │   ├── content_adapter.py               ← Core: AI content generation engine
│   │   ├── plan_estimator.py                ← Cost preview
│   │   ├── engagement_tracker.py            ← Post-publish data tracking
│   │   └── publishers/
│   │       ├── linkedin_publisher.py        ← LinkedIn API publisher
│   │       ├── x_publisher.py               ← X/Twitter API publisher
│   │       └── reddit_publisher.py          ← Reddit browser automation publisher
│   └── compositions/
│       └── content_matrix.yaml
└── reddit-cultivate/
    ├── SKILL.md                             ← Anti-shadowban karma builder
    └── scripts/
        └── reddit_cultivate.py              ← Cultivation automation script
```

## Requirements

| Requirement | Required For | Notes |
| --- | --- | --- |
| [OpenClaw](https://openclaw.ai) | Everything | Or Claude Code |
| Python 3.8+ | Everything | |
| `openai` pip package | Content generation | `pip install openai` |
| `tweepy` pip package | X/Twitter publishing | `pip install tweepy` |
| `requests` pip package | LinkedIn publishing | `pip install requests` |
| macOS + Chrome | Reddit publishing & cultivation | AppleScript is macOS-only |
| Twitter API keys | X publishing | [developer.twitter.com](https://developer.twitter.com) |
| LinkedIn OAuth token | LinkedIn publishing | Run `--setup` wizard |

`content-matrix` content generation works with no API keys if you use Ollama for local AI models.

## Credits

- Reddit browser automation approach inspired by [PHY041/claude-skill-reddit](https://github.com/PHY041/claude-skill-reddit) — AppleScript + Chrome technique for undetectable Reddit automation
- Built for the [OpenClaw](https://openclaw.ai) ecosystem

## Contributing

Contributions welcome! Some areas that could use help:

- Windows/Linux support for Reddit automation (currently macOS-only)
- Xiaohongshu auto-publish via browser automation
- More platform support (Dev.to, Medium, Hacker News)
- Better engagement tracking with automatic data collection
- Comment quality scoring before posting

Please open an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)
