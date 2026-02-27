---
name: reddit-cultivate
description: Automatically grow Reddit karma by finding rising posts and leaving thoughtful, AI-generated comments. Uses AppleScript + Chrome browser automation — undetectable by Reddit's anti-bot systems. Includes anti-shadowban safeguards with rate limiting, human-like timing, and quality checks.
metadata: {"openclaw":{"emoji":"🦀","os":["darwin"],"requires":{"bins":["python3","osascript"]},"homepage":"https://github.com/jrr996shujin-png/reddit-cultivate"}}
---

# Reddit Karma Cultivator (Anti-Shadowban Edition)

Automatically builds Reddit karma by commenting on rising posts with genuine, value-first responses.

## Prerequisites

1. **macOS only** (uses AppleScript)
2. **Google Chrome** with "Allow JavaScript from Apple Events" enabled:
   - Chrome → View → Developer → Allow JavaScript from Apple Events
   - Restart Chrome after enabling
3. **Logged into Reddit** in Chrome

## How It Works

1. AppleScript injects JavaScript into your logged-in Chrome browser
2. Fetches rising/hot posts from target subreddits via Reddit's internal JSON API
3. AI drafts a natural, value-first comment for each post
4. Posts comments with human-like delays and rate limiting
5. Tracks all activity to prevent duplicate comments

## Anti-Shadowban Rules (CRITICAL — FOLLOW EXACTLY)

These rules are non-negotiable. Violating them WILL get the account shadowbanned:

### Frequency Limits
- **Maximum 5 comments per session** (never exceed this)
- **Minimum 45-90 seconds between comments** (randomized delay)
- **Maximum 2 sessions per day** (morning + evening, 6+ hours apart)
- **Skip days randomly** — do NOT comment every single day. Aim for 4-5 days per week.

### Comment Quality Rules
- **NO self-promotion** — never mention your own product, link, or project
- **NO generic responses** — "Great post!", "I agree!", "This is helpful" will get flagged
- **Minimum 2 sentences** per comment, ideally 3-5 sentences
- **Must directly address** the specific content of the post
- **Add personal experience or perspective** — share an anecdote, opinion, or related info
- **Vary sentence structure** — don't start every comment the same way
- **Use casual Reddit tone** — contractions, lowercase "i" sometimes, occasional humor
- **NO emojis or excessive formatting** — Redditors hate that

### Subreddit Behavior
- **Rotate subreddits** — don't hammer the same subreddit repeatedly
- **Mix "easy karma" subs with niche subs** — balance r/AskReddit type posts with r/indiehackers
- **Read the room** — serious subs need serious comments, casual subs can be lighter
- **Avoid commenting on posts older than 6 hours** — comments on old posts look suspicious

### Red Flags to Avoid
- Commenting immediately after account creation
- All comments in same time window (looks like a bot schedule)
- Copy-paste or templated language across comments
- Only commenting, never upvoting (the script should upvote posts it comments on)
- Sudden spike in activity after days of silence

## Usage

Run the cultivation script:

```bash
python3 {baseDir}/scripts/reddit_cultivate.py --subreddits "indiehackers,SideProject,startups,AskReddit,technology" --max-comments 5
```

### Parameters
- `--subreddits`: Comma-separated list of target subreddits (default: indiehackers,SideProject,startups,technology,AskReddit)
- `--max-comments`: Maximum comments this session (default: 5, hard cap: 5)
- `--min-delay`: Minimum seconds between comments (default: 45)
- `--max-delay`: Maximum seconds between comments (default: 90)
- `--check-only`: Just check account status and karma, don't comment
- `--dry-run`: Generate comments but don't post them (for review)

### Check Account Status
```bash
python3 {baseDir}/scripts/reddit_cultivate.py --check-only
```

### Dry Run (Preview Comments)
```bash
python3 {baseDir}/scripts/reddit_cultivate.py --subreddits "indiehackers,startups" --dry-run
```

## Comment Generation Guidelines for AI

When generating comments, follow these patterns:

**Good comment patterns:**
- "I ran into this exact same issue last month. What worked for me was [specific approach]. The key thing I learned was [insight]."
- "Interesting take. I'd push back a little on [specific point] though — in my experience [alternative perspective]. That said, [agreement with part of post]."
- "This reminds me of [related concept/experience]. Have you considered [thoughtful question]? I found that [relevant observation]."

**Bad comment patterns (NEVER use):**
- "Great post! Thanks for sharing." (too generic)
- "Check out my tool at [link]" (self-promotion)
- "I totally agree with everything here." (no substance)
- "As an AI language model..." (obviously wrong)
- Starting every comment with "I think" or "In my opinion"

## Activity Log

The script maintains a log at `~/.openclaw/reddit-cultivate-log.json` tracking:
- Timestamps of all comments
- Subreddits commented in
- Post IDs (to avoid duplicate comments)
- Daily/weekly comment counts
- Karma snapshots over time

This log is used to enforce rate limits and detect patterns that could trigger shadowban.

## Shadowban Detection

Run periodically to check if the account has been shadowbanned:

```bash
python3 {baseDir}/scripts/reddit_cultivate.py --check-shadowban
```

This opens an incognito window and checks if the user profile is visible to logged-out users. If shadowbanned, STOP all automation immediately.
