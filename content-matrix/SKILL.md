---
name: content-matrix
description: Cross-platform content distribution — generate platform-native versions of content for X, LinkedIn, Reddit, and Xiaohongshu from one input, then auto-publish via API or browser automation. Use when distributing content, creating social posts, or publishing across platforms.
metadata: {"openclaw":{"emoji":"📣","requires":{"bins":["python3"]},"homepage":"https://github.com/jrr996shujin-png/content-matrix-skills"}}
---

# Content Matrix — Cross-Platform Content Distribution

## Trigger
Activate when user mentions:
- "distribute content", "cross-platform", "content matrix"
- "post to LinkedIn / X / Reddit / Xiaohongshu"
- "generate social media versions"
- "multi-platform publishing"
- "发帖", "内容分发", "跨平台"

## Quick Start

### Generate content for all platforms
```bash
python3 {baseDir}/skills/content_adapter.py "Your mother content here"
```

### Generate for specific platforms
```bash
python3 {baseDir}/skills/content_adapter.py "Content" --platforms x,reddit,linkedin
```

### Preview cost before generating
```bash
python3 {baseDir}/skills/content_adapter.py "Content" --plan
```

## Publishing

### LinkedIn (Free — API)
```bash
# First-time setup
python3 {baseDir}/skills/publishers/linkedin_publisher.py --setup

# Publish
python3 {baseDir}/skills/publishers/linkedin_publisher.py --text "Your post"
```

### X / Twitter (~$0.01/tweet)
```bash
# Requires: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
python3 {baseDir}/skills/publishers/x_publisher.py "Your tweet"

# Thread
python3 {baseDir}/skills/publishers/x_publisher.py --thread "Tweet 1" "Tweet 2" "Tweet 3"
```

### Reddit (Free — Browser Automation, macOS only)
```bash
# Requires: Chrome with "Allow JavaScript from Apple Events" + logged into Reddit
python3 {baseDir}/skills/publishers/reddit_publisher.py --check-login
python3 {baseDir}/skills/publishers/reddit_publisher.py --title "Title" --body "Body" --subreddit test
```

Note: New Reddit accounts trigger CAPTCHA. Use `reddit-cultivate` skill to build karma first.

## AI Model Support
```bash
# OpenAI (default, ~$0.01)
python3 {baseDir}/skills/content_adapter.py "Content"

# DeepSeek (cheapest, ~$0.001)
python3 {baseDir}/skills/content_adapter.py "Content" --base-url https://api.deepseek.com --model deepseek-chat

# Claude
python3 {baseDir}/skills/content_adapter.py "Content" --provider anthropic

# Ollama local (free)
python3 {baseDir}/skills/content_adapter.py "Content" --base-url http://localhost:11434/v1 --model llama3
```

## Configuration

### Personal Style (important!)
Edit `{baseDir}/configs/my_style.json` — paste your old posts so AI learns your voice.

### Platform Rules
`{baseDir}/configs/platform_rules.json` — content rules per platform. Usually no need to edit.

### Publish Timing
`{baseDir}/configs/publish_timing.json` — best posting times and order.

## Engagement Tracking
```bash
python3 {baseDir}/skills/engagement_tracker.py add --platform reddit --url "https://reddit.com/r/..."
python3 {baseDir}/skills/engagement_tracker.py check
python3 {baseDir}/skills/engagement_tracker.py report
```

## Dependencies
- Python 3.8+
- openai (`pip install openai`)
- tweepy (`pip install tweepy`) — for X publishing
- requests (`pip install requests`) — for LinkedIn publishing
