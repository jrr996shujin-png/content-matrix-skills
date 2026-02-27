#!/usr/bin/env python3
"""
Reddit Karma Cultivator — Anti-Shadowban Edition
Uses AppleScript + Chrome browser automation to grow Reddit karma safely.

Designed for OpenClaw / Claude Code skill system.
"""

import subprocess
import json
import time
import random
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────
LOG_FILE = os.path.expanduser("~/.openclaw/reddit-cultivate-log.json")
MAX_COMMENTS_PER_SESSION = 5
MAX_SESSIONS_PER_DAY = 2
MIN_HOURS_BETWEEN_SESSIONS = 6
MAX_POST_AGE_HOURS = 6
POSTS_PER_SUBREDDIT = 10

# ── AppleScript Helpers ────────────────────────────────────────

def chrome_execute_js(js_code: str, timeout: float = 10.0) -> str:
    """Execute JavaScript in Chrome's active tab via AppleScript and return result."""
    # Use document.title trick for async results
    escaped = js_code.replace('\\', '\\\\').replace('"', '\\"')
    applescript = f'''
    tell application "Google Chrome"
        tell active tab of first window
            execute javascript "{escaped}"
        end tell
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {e}"


def chrome_read_title() -> str:
    """Read Chrome's active tab title (used to retrieve async JS results)."""
    applescript = '''
    tell application "Google Chrome"
        return title of active tab of first window
    end tell
    '''
    result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
    return result.stdout.strip()


def chrome_navigate(url: str):
    """Navigate Chrome's active tab to a URL."""
    escaped = url.replace('"', '\\"')
    applescript = f'''
    tell application "Google Chrome"
        tell active tab of first window
            set URL to "{escaped}"
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)


def chrome_execute_async(js_code: str, wait: float = 3.0) -> str:
    """Execute async JS, wait, then read result from document.title."""
    # Wrap in async and write result to title
    wrapper = f'''
    (async () => {{
        try {{
            const __result = await (async () => {{ {js_code} }})();
            document.title = JSON.stringify(__result);
        }} catch(e) {{
            document.title = JSON.stringify({{error: e.message}});
        }}
    }})();
    '''
    chrome_execute_js(wrapper)
    time.sleep(wait)
    return chrome_read_title()


# ── Reddit API (via Chrome) ───────────────────────────────────

def check_login() -> dict:
    """Check if user is logged into Reddit in Chrome."""
    chrome_navigate("https://www.reddit.com")
    time.sleep(2)
    
    result = chrome_execute_async("""
        const resp = await fetch('https://www.reddit.com/api/me.json', {credentials: 'include'});
        const data = await resp.json();
        return {
            name: data.data?.name || null,
            link_karma: data.data?.link_karma || 0,
            comment_karma: data.data?.comment_karma || 0,
            total_karma: (data.data?.link_karma || 0) + (data.data?.comment_karma || 0),
            created_utc: data.data?.created_utc || 0,
            is_suspended: data.data?.is_suspended || false
        };
    """, wait=3)
    
    try:
        return json.loads(result)
    except:
        return {"error": "Failed to check login. Make sure Chrome is open and logged into Reddit."}


def get_rising_posts(subreddit: str, limit: int = 10) -> list:
    """Fetch rising/hot posts from a subreddit."""
    result = chrome_execute_async(f"""
        const resp = await fetch('https://www.reddit.com/r/{subreddit}/rising.json?limit={limit}', 
            {{credentials: 'include'}});
        const data = await resp.json();
        const posts = (data.data?.children || []).map(c => ({{
            id: c.data.name,
            title: c.data.title,
            selftext: (c.data.selftext || '').substring(0, 500),
            author: c.data.author,
            subreddit: c.data.subreddit,
            score: c.data.score,
            num_comments: c.data.num_comments,
            created_utc: c.data.created_utc,
            permalink: c.data.permalink,
            url: c.data.url
        }}));
        return posts;
    """, wait=3)
    
    try:
        posts = json.loads(result)
        if isinstance(posts, dict) and "error" in posts:
            return []
        return posts if isinstance(posts, list) else []
    except:
        return []


def get_modhash() -> str:
    """Get Reddit modhash (CSRF token) for posting."""
    result = chrome_execute_async("""
        const resp = await fetch('https://www.reddit.com/api/me.json', {credentials: 'include'});
        const data = await resp.json();
        return data.data?.modhash || '';
    """, wait=2)
    try:
        return json.loads(result)
    except:
        return ""


def post_comment(parent_id: str, text: str, modhash: str) -> dict:
    """Post a comment to Reddit."""
    # Escape the text for JS
    escaped_text = text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
    
    result = chrome_execute_async(f"""
        const formData = new URLSearchParams();
        formData.append('thing_id', '{parent_id}');
        formData.append('text', '{escaped_text}');
        formData.append('uh', '{modhash}');
        formData.append('api_type', 'json');
        
        const resp = await fetch('https://www.reddit.com/api/comment', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: formData.toString()
        }});
        const data = await resp.json();
        return {{
            success: !data.json?.errors?.length,
            errors: data.json?.errors || [],
            comment_url: data.json?.data?.things?.[0]?.data?.permalink || null
        }};
    """, wait=4)
    
    try:
        return json.loads(result)
    except:
        return {"success": False, "errors": ["Failed to parse response"]}


def upvote_post(post_id: str, modhash: str) -> bool:
    """Upvote a post (makes commenting look more natural)."""
    result = chrome_execute_async(f"""
        const formData = new URLSearchParams();
        formData.append('id', '{post_id}');
        formData.append('dir', '1');
        formData.append('uh', '{modhash}');
        
        const resp = await fetch('https://www.reddit.com/api/vote', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: formData.toString()
        }});
        return resp.ok;
    """, wait=2)
    try:
        return json.loads(result) == True
    except:
        return False


# ── Activity Log ──────────────────────────────────────────────

def load_log() -> dict:
    """Load activity log from disk."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return {"comments": [], "sessions": [], "karma_history": []}


def save_log(log: dict):
    """Save activity log to disk."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)


def check_rate_limits(log: dict) -> tuple:
    """Check if we're within safe rate limits. Returns (ok, reason)."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    # Count today's sessions
    today_sessions = [s for s in log.get("sessions", []) if s.get("date") == today]
    if len(today_sessions) >= MAX_SESSIONS_PER_DAY:
        return False, f"Already had {len(today_sessions)} sessions today (max {MAX_SESSIONS_PER_DAY})"
    
    # Check time since last session
    if today_sessions:
        last_session = max(today_sessions, key=lambda s: s.get("timestamp", ""))
        last_time = datetime.fromisoformat(last_session["timestamp"])
        hours_since = (now - last_time).total_seconds() / 3600
        if hours_since < MIN_HOURS_BETWEEN_SESSIONS:
            return False, f"Only {hours_since:.1f}h since last session (need {MIN_HOURS_BETWEEN_SESSIONS}h)"
    
    # Count today's comments
    today_comments = [c for c in log.get("comments", []) if c.get("date") == today]
    if len(today_comments) >= MAX_COMMENTS_PER_SESSION * MAX_SESSIONS_PER_DAY:
        return False, f"Already posted {len(today_comments)} comments today (daily max: {MAX_COMMENTS_PER_SESSION * MAX_SESSIONS_PER_DAY})"
    
    return True, "OK"


def is_already_commented(log: dict, post_id: str) -> bool:
    """Check if we already commented on this post."""
    return any(c.get("post_id") == post_id for c in log.get("comments", []))


def filter_posts(posts: list, log: dict) -> list:
    """Filter posts to only those safe to comment on."""
    now = time.time()
    filtered = []
    
    for post in posts:
        # Skip if already commented
        if is_already_commented(log, post.get("id", "")):
            continue
        
        # Skip posts older than MAX_POST_AGE_HOURS
        post_age_hours = (now - post.get("created_utc", 0)) / 3600
        if post_age_hours > MAX_POST_AGE_HOURS:
            continue
        
        # Skip posts by [deleted] authors
        if post.get("author") in ["[deleted]", "AutoModerator"]:
            continue
        
        # Skip posts with 0 or very high score (extremes are risky)
        score = post.get("score", 0)
        if score < 1 or score > 500:
            continue
        
        filtered.append(post)
    
    return filtered


# ── Shadowban Detection ───────────────────────────────────────

def check_shadowban(username: str) -> dict:
    """Check if account might be shadowbanned."""
    # Open user profile in a non-logged-in context
    result = chrome_execute_async(f"""
        const resp = await fetch('https://www.reddit.com/user/{username}/about.json', {{
            credentials: 'omit'
        }});
        if (resp.status === 404) {{
            return {{shadowbanned: true, status: 404}};
        }}
        const data = await resp.json();
        return {{
            shadowbanned: false, 
            status: resp.status,
            name: data.data?.name || null
        }};
    """, wait=3)
    
    try:
        return json.loads(result)
    except:
        return {"shadowbanned": "unknown", "error": "Could not check"}


# ── Main Logic ────────────────────────────────────────────────

def run_check_only():
    """Just check account status."""
    print("🔍 Checking Reddit account status...")
    info = check_login()
    
    if "error" in info:
        print(f"❌ {info['error']}")
        return
    
    if not info.get("name"):
        print("❌ Not logged into Reddit in Chrome.")
        print("   → Open Chrome, go to reddit.com, and log in.")
        return
    
    print(f"✅ Logged in as: u/{info['name']}")
    print(f"   📊 Comment Karma: {info.get('comment_karma', 0)}")
    print(f"   📊 Link Karma: {info.get('link_karma', 0)}")
    print(f"   📊 Total Karma: {info.get('total_karma', 0)}")
    
    # Check rate limits
    log = load_log()
    ok, reason = check_rate_limits(log)
    if ok:
        print(f"   ✅ Rate limits OK — can run a session now")
    else:
        print(f"   ⚠️  Rate limit: {reason}")
    
    # Show recent activity
    today = datetime.now().strftime("%Y-%m-%d")
    today_comments = [c for c in log.get("comments", []) if c.get("date") == today]
    print(f"   📝 Comments today: {len(today_comments)}")
    
    # Karma trend
    history = log.get("karma_history", [])
    if len(history) >= 2:
        diff = history[-1].get("total", 0) - history[-2].get("total", 0)
        print(f"   📈 Karma change since last check: {'+' if diff >= 0 else ''}{diff}")
    
    # Save karma snapshot
    history.append({
        "timestamp": datetime.now().isoformat(),
        "total": info.get("total_karma", 0),
        "comment": info.get("comment_karma", 0),
        "link": info.get("link_karma", 0)
    })
    log["karma_history"] = history[-100:]  # Keep last 100 snapshots
    save_log(log)


def run_shadowban_check():
    """Check for shadowban."""
    print("🔍 Checking for shadowban...")
    info = check_login()
    if not info.get("name"):
        print("❌ Not logged in.")
        return
    
    result = check_shadowban(info["name"])
    if result.get("shadowbanned"):
        print(f"🚨 SHADOWBAN DETECTED for u/{info['name']}!")
        print("   ⛔ STOP ALL AUTOMATION IMMEDIATELY")
        print("   → Wait 1-2 weeks before any activity")
        print("   → When resuming, only comment manually")
    elif result.get("shadowbanned") == False:
        print(f"✅ u/{info['name']} is NOT shadowbanned — profile visible to public")
    else:
        print(f"⚠️  Could not determine shadowban status: {result.get('error', 'unknown')}")


def run_cultivate(subreddits: list, max_comments: int, min_delay: int, max_delay: int, dry_run: bool):
    """Main cultivation loop."""
    # Enforce hard cap
    max_comments = min(max_comments, MAX_COMMENTS_PER_SESSION)
    
    print("🦀 Reddit Karma Cultivator — Anti-Shadowban Edition")
    print(f"   Target subreddits: {', '.join(subreddits)}")
    print(f"   Max comments: {max_comments}")
    print(f"   Delay range: {min_delay}-{max_delay}s")
    print(f"   Mode: {'DRY RUN (no posting)' if dry_run else 'LIVE'}")
    print()
    
    # Check login
    info = check_login()
    if not info.get("name"):
        print("❌ Not logged into Reddit. Open Chrome and log in first.")
        return
    
    username = info["name"]
    print(f"✅ Logged in as u/{username} (karma: {info.get('total_karma', 0)})")
    
    # Check rate limits
    log = load_log()
    ok, reason = check_rate_limits(log)
    if not ok:
        print(f"⛔ Rate limit exceeded: {reason}")
        print("   → Try again later to stay safe.")
        return
    
    # Get modhash
    modhash = get_modhash()
    if not modhash and not dry_run:
        print("❌ Could not get modhash (CSRF token). Try refreshing Reddit in Chrome.")
        return
    
    # Shuffle subreddits for randomness
    random.shuffle(subreddits)
    
    # Collect candidate posts
    print("\n📡 Scanning for rising posts...")
    all_posts = []
    for sub in subreddits:
        posts = get_rising_posts(sub, POSTS_PER_SUBREDDIT)
        filtered = filter_posts(posts, log)
        all_posts.extend(filtered)
        print(f"   r/{sub}: {len(posts)} found, {len(filtered)} eligible")
        time.sleep(random.uniform(1, 3))  # Small delay between fetches
    
    if not all_posts:
        print("\n⚠️  No eligible posts found. Try different subreddits or wait.")
        return
    
    # Shuffle and pick top candidates
    random.shuffle(all_posts)
    candidates = all_posts[:max_comments]
    
    print(f"\n📝 Selected {len(candidates)} posts to comment on:\n")
    
    results = []
    session_start = datetime.now().isoformat()
    
    for i, post in enumerate(candidates):
        print(f"{'─' * 60}")
        print(f"[{i+1}/{len(candidates)}] r/{post['subreddit']}: {post['title'][:80]}")
        print(f"   Score: {post['score']} | Comments: {post['num_comments']} | By: u/{post['author']}")
        
        # Generate comment context for AI
        context = {
            "subreddit": post["subreddit"],
            "title": post["title"],
            "body": post.get("selftext", "")[:500],
            "score": post["score"],
            "num_comments": post["num_comments"]
        }
        
        print(f"\n   💬 POST CONTEXT FOR AI TO GENERATE COMMENT:")
        print(f"   Subreddit: r/{context['subreddit']}")
        print(f"   Title: {context['title']}")
        if context['body']:
            print(f"   Body: {context['body'][:200]}...")
        print(f"\n   ⏳ [AI should generate comment here based on SKILL.md guidelines]")
        print(f"   >>> PLACEHOLDER: AI-generated comment needed <<<")
        
        # In actual OpenClaw usage, the AI agent reads this output and generates
        # the comment, then calls post_comment(). This script provides the infrastructure.
        
        if dry_run:
            print(f"   🏷️  DRY RUN — would comment on: {post['permalink']}")
            results.append({
                "post_id": post["id"],
                "subreddit": post["subreddit"],
                "title": post["title"][:80],
                "status": "dry_run",
                "permalink": post["permalink"]
            })
        else:
            # NOTE: In actual use, the OpenClaw agent fills in the comment text
            # This is a placeholder — the agent should call:
            #   post_comment(post["id"], generated_comment_text, modhash)
            print(f"   ⚠️  Comment text must be provided by the AI agent.")
            print(f"   To post manually, use:")
            print(f"   python3 {__file__} --post-comment '{post['id']}' --text 'YOUR COMMENT'")
        
        # Log the attempt
        log["comments"].append({
            "post_id": post["id"],
            "subreddit": post["subreddit"],
            "title": post["title"][:100],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "status": "dry_run" if dry_run else "pending",
            "permalink": post.get("permalink", "")
        })
        
        # Human-like delay between comments
        if i < len(candidates) - 1:
            delay = random.uniform(min_delay, max_delay)
            print(f"\n   ⏱️  Waiting {delay:.0f}s before next comment...")
            if not dry_run:
                time.sleep(delay)
    
    # Record session
    log["sessions"].append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": session_start,
        "comments_attempted": len(candidates),
        "subreddits": list(set(p["subreddit"] for p in candidates)),
        "dry_run": dry_run
    })
    
    save_log(log)
    
    print(f"\n{'═' * 60}")
    print(f"✅ Session complete!")
    print(f"   Posts scanned: {len(all_posts)}")
    print(f"   Comments {'previewed' if dry_run else 'attempted'}: {len(candidates)}")
    print(f"   Log saved to: {LOG_FILE}")


def run_post_single_comment(post_id: str, text: str):
    """Post a single comment (called by AI agent with generated text)."""
    print(f"💬 Posting comment to {post_id}...")
    
    info = check_login()
    if not info.get("name"):
        print("❌ Not logged in.")
        return
    
    modhash = get_modhash()
    if not modhash:
        print("❌ Could not get modhash.")
        return
    
    # Upvote the post first (looks natural)
    print("   👍 Upvoting post...")
    upvote_post(post_id, modhash)
    time.sleep(random.uniform(2, 5))
    
    # Post the comment
    print("   ✍️  Posting comment...")
    result = post_comment(post_id, text, modhash)
    
    if result.get("success"):
        comment_url = result.get("comment_url", "")
        print(f"   ✅ Comment posted!")
        if comment_url:
            print(f"   🔗 https://www.reddit.com{comment_url}")
        
        # Log it
        log = load_log()
        log["comments"].append({
            "post_id": post_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "status": "posted",
            "comment_url": comment_url,
            "text_preview": text[:100]
        })
        save_log(log)
    else:
        errors = result.get("errors", [])
        print(f"   ❌ Failed: {errors}")
        if any("RATELIMIT" in str(e) for e in errors):
            print("   ⚠️  Rate limited by Reddit! Wait before trying again.")
        elif any("CAPTCHA" in str(e).upper() for e in errors):
            print("   ⚠️  CAPTCHA required — account too new. Need more manual activity first.")


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reddit Karma Cultivator (Anti-Shadowban)")
    parser.add_argument("--subreddits", type=str, 
                       default="indiehackers,SideProject,startups,technology,AskReddit",
                       help="Comma-separated subreddit list")
    parser.add_argument("--max-comments", type=int, default=5,
                       help="Max comments per session (hard cap: 5)")
    parser.add_argument("--min-delay", type=int, default=45,
                       help="Min seconds between comments")
    parser.add_argument("--max-delay", type=int, default=90,
                       help="Max seconds between comments")
    parser.add_argument("--check-only", action="store_true",
                       help="Just check account status")
    parser.add_argument("--check-shadowban", action="store_true",
                       help="Check for shadowban")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview without posting")
    parser.add_argument("--post-comment", type=str,
                       help="Post a comment to specific post ID")
    parser.add_argument("--text", type=str,
                       help="Comment text (used with --post-comment)")
    parser.add_argument("--check-login", action="store_true",
                       help="Quick login check")
    
    args = parser.parse_args()
    
    if args.check_login:
        info = check_login()
        if info.get("name"):
            print(f"✅ Logged in as u/{info['name']} (karma: {info.get('total_karma', 0)})")
        else:
            print("❌ Not logged in.")
        return
    
    if args.check_only:
        run_check_only()
        return
    
    if args.check_shadowban:
        run_shadowban_check()
        return
    
    if args.post_comment:
        if not args.text:
            print("❌ --text is required with --post-comment")
            return
        run_post_single_comment(args.post_comment, args.text)
        return
    
    subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    run_cultivate(subreddits, args.max_comments, args.min_delay, args.max_delay, args.dry_run)


if __name__ == "__main__":
    main()
