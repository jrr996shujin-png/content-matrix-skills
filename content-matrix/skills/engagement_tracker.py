#!/usr/bin/env python3
"""
Skill: Engagement Tracker (跨平台数据追踪)
Monitor post performance (likes, comments, views) across platforms.

Usage:
  # Register a post for tracking
  python3 engagement_tracker.py add --platform x --url "https://x.com/user/status/123"
  python3 engagement_tracker.py add --platform reddit --url "https://reddit.com/r/SaaS/comments/abc/..."

  # Check all tracked posts
  python3 engagement_tracker.py check

  # Run 24-hour monitoring (checks every 2 hours)
  python3 engagement_tracker.py monitor --hours 24 --interval 120

  # Show report
  python3 engagement_tracker.py report
"""

import json
import sys
import os
import argparse
import time
import re
import requests
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
TRACKING_FILE = os.path.join(DATA_DIR, "tracked_posts.json")

HEADERS_REDDIT = {'User-Agent': 'script:content-matrix:v1.0 (engagement-tracker)'}


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_tracked():
    ensure_data_dir()
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": []}


def save_tracked(data):
    ensure_data_dir()
    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# Platform-specific data fetchers
# ═══════════════════════════════════════════════════════════════

def fetch_reddit_metrics(url):
    """Fetch Reddit post metrics via JSON API."""
    try:
        json_url = re.sub(r'/?$', '.json', url.split('?')[0])
        r = requests.get(json_url, headers=HEADERS_REDDIT, params={"raw_json": 1}, timeout=15)
        if r.status_code == 429:
            time.sleep(60)
            r = requests.get(json_url, headers=HEADERS_REDDIT, params={"raw_json": 1}, timeout=15)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, list) and len(data) > 0:
            post = data[0]["data"]["children"][0]["data"]
            comments_count = len(data[1]["data"]["children"]) if len(data) > 1 else 0
            return {
                "score": post.get("score", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "num_comments": post.get("num_comments", 0),
                "views": None,  # Reddit doesn't expose view count via API
                "saves": None,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        sys.stderr.write(f"  Reddit fetch error: {e}\n")
    return None


def fetch_x_metrics(url):
    """Fetch X/Twitter metrics via API v2. Requires TWITTER_BEARER_TOKEN."""
    bearer = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not bearer:
        return {"error": "Set TWITTER_BEARER_TOKEN env var", "fetched_at": datetime.now(timezone.utc).isoformat()}

    # Extract tweet ID from URL
    match = re.search(r'/status/(\d+)', url)
    if not match:
        return {"error": "Cannot extract tweet ID from URL"}

    tweet_id = match.group(1)
    try:
        r = requests.get(
            f"https://api.twitter.com/2/tweets/{tweet_id}",
            headers={"Authorization": f"Bearer {bearer}"},
            params={"tweet.fields": "public_metrics,created_at"},
            timeout=15
        )
        if r.status_code == 429:
            time.sleep(30)
            return {"error": "Rate limited, try again later"}
        r.raise_for_status()
        data = r.json().get("data", {})
        metrics = data.get("public_metrics", {})
        return {
            "score": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "quotes": metrics.get("quote_count", 0),
            "bookmarks": metrics.get("bookmark_count", 0),
            "views": metrics.get("impression_count", 0),
            "num_comments": metrics.get("reply_count", 0),
            "saves": metrics.get("bookmark_count", 0),
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        sys.stderr.write(f"  X fetch error: {e}\n")
    return None


def fetch_linkedin_metrics(url):
    """LinkedIn doesn't have public API for post metrics."""
    return {
        "error": "LinkedIn不支持公开API获取帖子数据，请手动记录",
        "manual_fields": ["reactions", "comments", "reposts", "impressions"],
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }



def fetch_xiaohongshu_metrics(url):
    """Xiaohongshu doesn't have public API."""
    return {
        "error": "小红书没有公开API，请手动记录数据",
        "manual_fields": ["likes", "favorites", "comments", "shares"],
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }


FETCHERS = {
    "reddit": fetch_reddit_metrics,
    "x": fetch_x_metrics,
    "linkedin": fetch_linkedin_metrics,
    "xiaohongshu": fetch_xiaohongshu_metrics,
}


# ═══════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════

def cmd_add(platform, url, title=""):
    """Add a post to tracking."""
    tracked = load_tracked()

    # Check duplicate
    for p in tracked["posts"]:
        if p["url"] == url:
            sys.stderr.write(f"Already tracking: {url}\n")
            return

    post = {
        "platform": platform,
        "url": url,
        "title": title or f"{platform} post",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "snapshots": []
    }

    tracked["posts"].append(post)
    save_tracked(tracked)
    sys.stderr.write(f"✅ Added {platform} post for tracking: {url}\n")


def cmd_add_manual(platform, title=""):
    """Add a post that requires manual data entry (xiaohongshu, linkedin)."""
    tracked = load_tracked()
    post = {
        "platform": platform,
        "url": "",
        "title": title or f"{platform} post",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "snapshots": []
    }
    tracked["posts"].append(post)
    save_tracked(tracked)
    sys.stderr.write(f"✅ Added {platform} post (manual tracking). Use 'log' command to record metrics.\n")


def cmd_log(index, likes=0, comments=0, views=0, saves=0):
    """Manually log metrics for platforms without API (xiaohongshu, linkedin)."""
    tracked = load_tracked()
    if index < 0 or index >= len(tracked["posts"]):
        sys.stderr.write(f"Invalid post index: {index}\n")
        return

    snapshot = {
        "score": likes,
        "num_comments": comments,
        "views": views,
        "saves": saves,
        "manual": True,
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }
    tracked["posts"][index]["snapshots"].append(snapshot)
    save_tracked(tracked)
    sys.stderr.write(f"✅ Logged metrics for post #{index}\n")


def cmd_check():
    """Fetch latest metrics for all tracked posts."""
    tracked = load_tracked()
    if not tracked["posts"]:
        sys.stderr.write("No posts being tracked. Use 'add' command first.\n")
        return

    sys.stderr.write(f"\n{'='*60}\n")
    sys.stderr.write(f"  📊 ENGAGEMENT CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    sys.stderr.write(f"{'='*60}\n\n")

    for i, post in enumerate(tracked["posts"]):
        platform = post["platform"]
        fetcher = FETCHERS.get(platform)

        sys.stderr.write(f"  [{i}] {post['platform'].upper()} - {post['title'][:50]}\n")
        sys.stderr.write(f"      {post['url'][:60]}\n")

        if fetcher and post.get("url"):
            metrics = fetcher(post["url"])
            if metrics and "error" not in metrics:
                post["snapshots"].append(metrics)
                score = metrics.get("score", "?")
                comments = metrics.get("num_comments", "?")
                views = metrics.get("views", "N/A")
                saves = metrics.get("saves", "N/A")
                sys.stderr.write(f"      👍 {score}  💬 {comments}  👁 {views}  🔖 {saves}\n")

                # Show change from first snapshot
                if len(post["snapshots"]) > 1:
                    first = post["snapshots"][0]
                    delta_score = (metrics.get("score", 0) or 0) - (first.get("score", 0) or 0)
                    delta_comments = (metrics.get("num_comments", 0) or 0) - (first.get("num_comments", 0) or 0)
                    sys.stderr.write(f"      📈 Since first check: +{delta_score} likes, +{delta_comments} comments\n")
            elif metrics and "error" in metrics:
                sys.stderr.write(f"      ⚠️  {metrics['error']}\n")
        else:
            if post["snapshots"]:
                last = post["snapshots"][-1]
                sys.stderr.write(f"      Last manual entry: 👍 {last.get('score', '?')}  💬 {last.get('num_comments', '?')}\n")
            else:
                sys.stderr.write(f"      ⚠️  需要手动记录. Use: python3 engagement_tracker.py log {i} --likes N --comments N\n")

        sys.stderr.write("\n")

    save_tracked(tracked)


def cmd_monitor(hours=24, interval=120):
    """Continuously monitor posts for specified duration."""
    end_time = datetime.now() + timedelta(hours=hours)
    check_count = 0

    sys.stderr.write(f"\n🔄 Starting {hours}h monitoring (check every {interval}min)\n")
    sys.stderr.write(f"   Will run until: {end_time.strftime('%Y-%m-%d %H:%M')}\n")
    sys.stderr.write(f"   Press Ctrl+C to stop\n\n")

    try:
        while datetime.now() < end_time:
            check_count += 1
            sys.stderr.write(f"\n--- Check #{check_count} at {datetime.now().strftime('%H:%M')} ---\n")
            cmd_check()
            next_check = datetime.now() + timedelta(minutes=interval)
            if next_check < end_time:
                sys.stderr.write(f"Next check at {next_check.strftime('%H:%M')}\n")
                time.sleep(interval * 60)
            else:
                break
    except KeyboardInterrupt:
        sys.stderr.write("\n\n⏹️  Monitoring stopped.\n")

    sys.stderr.write(f"\n📊 Monitoring complete. Run 'report' to see summary.\n")


def cmd_report():
    """Generate final performance report."""
    tracked = load_tracked()
    if not tracked["posts"]:
        print("No tracked posts.")
        return

    report = []
    report.append("# 📊 跨平台发布效果报告\n")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    report.append("")

    # Summary table
    report.append("## 总览\n")
    report.append("| 平台 | 帖子 | 👍 点赞 | 💬 评论 | 👁 浏览 | 🔖 收藏 | 追踪时长 |")
    report.append("|------|------|---------|---------|---------|---------|----------|")

    for post in tracked["posts"]:
        platform = post["platform"].upper()
        title = post["title"][:20]
        snapshots = post["snapshots"]

        if snapshots:
            latest = snapshots[-1]
            score = latest.get("score", "?")
            comments = latest.get("num_comments", "?")
            views = latest.get("views", "N/A") or "N/A"
            saves = latest.get("saves", "N/A") or "N/A"

            # Calculate tracking duration
            first_time = snapshots[0].get("fetched_at", "")
            last_time = snapshots[-1].get("fetched_at", "")
            try:
                t1 = datetime.fromisoformat(first_time.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
                duration = str(t2 - t1).split(".")[0]
            except:
                duration = "?"
        else:
            score = comments = views = saves = "—"
            duration = "未记录"

        report.append(f"| {platform} | {title} | {score} | {comments} | {views} | {saves} | {duration} |")

    report.append("")

    # Detailed per-post section
    report.append("## 详细数据\n")
    for i, post in enumerate(tracked["posts"]):
        report.append(f"### [{post['platform'].upper()}] {post['title']}\n")
        report.append(f"- URL: {post.get('url', 'N/A')}")
        report.append(f"- Added: {post['added_at']}")
        report.append(f"- Snapshots: {len(post['snapshots'])}\n")

        if post["snapshots"]:
            report.append("| 时间 | 👍 点赞 | 💬 评论 | 👁 浏览 | 🔖 收藏 |")
            report.append("|------|---------|---------|---------|---------|")
            for s in post["snapshots"]:
                t = s.get("fetched_at", "?")
                try:
                    t = datetime.fromisoformat(t.replace("Z", "+00:00")).strftime("%m-%d %H:%M")
                except:
                    pass
                report.append(f"| {t} | {s.get('score', '?')} | {s.get('num_comments', '?')} | {s.get('views', 'N/A') or 'N/A'} | {s.get('saves', 'N/A') or 'N/A'} |")

            # Growth summary
            first = post["snapshots"][0]
            last = post["snapshots"][-1]
            if len(post["snapshots"]) > 1:
                delta_s = (last.get("score", 0) or 0) - (first.get("score", 0) or 0)
                delta_c = (last.get("num_comments", 0) or 0) - (first.get("num_comments", 0) or 0)
                report.append(f"\n📈 **增长: +{delta_s} 点赞, +{delta_c} 评论**\n")

        report.append("")

    output = "\n".join(report)
    print(output)

    # Also save to file
    report_file = os.path.join(DATA_DIR, f"engagement_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(output)
    sys.stderr.write(f"\nReport saved: {report_file}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Track post engagement across platforms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  add       Add a post URL to track
  log       Manually log metrics (for xiaohongshu/linkedin)
  check     Fetch latest metrics for all tracked posts
  monitor   Continuous monitoring for N hours
  report    Generate performance report

Examples:
  python3 engagement_tracker.py add --platform reddit --url "https://reddit.com/r/..."
  python3 engagement_tracker.py add --platform x --url "https://x.com/user/status/123"
  python3 engagement_tracker.py add --platform xiaohongshu --title "AI剪辑踩坑帖"
  python3 engagement_tracker.py log 2 --likes 150 --comments 23 --views 5000
  python3 engagement_tracker.py check
  python3 engagement_tracker.py monitor --hours 24 --interval 120
  python3 engagement_tracker.py report
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # add
    p_add = subparsers.add_parser("add", help="Add post to track")
    p_add.add_argument("--platform", required=True, choices=["reddit", "x", "linkedin", "xiaohongshu"])
    p_add.add_argument("--url", default="", help="Post URL")
    p_add.add_argument("--title", default="", help="Post title/description")

    # log
    p_log = subparsers.add_parser("log", help="Manually log metrics")
    p_log.add_argument("index", type=int, help="Post index number")
    p_log.add_argument("--likes", type=int, default=0)
    p_log.add_argument("--comments", type=int, default=0)
    p_log.add_argument("--views", type=int, default=0)
    p_log.add_argument("--saves", type=int, default=0)

    # check
    subparsers.add_parser("check", help="Check latest metrics")

    # monitor
    p_mon = subparsers.add_parser("monitor", help="Continuous monitoring")
    p_mon.add_argument("--hours", type=int, default=24, help="How long to monitor (hours)")
    p_mon.add_argument("--interval", type=int, default=120, help="Check interval (minutes)")

    # report
    subparsers.add_parser("report", help="Generate performance report")

    args = parser.parse_args()

    if args.command == "add":
        if args.url:
            cmd_add(args.platform, args.url, args.title)
        else:
            cmd_add_manual(args.platform, args.title)
    elif args.command == "log":
        cmd_log(args.index, args.likes, args.comments, args.views, args.saves)
    elif args.command == "check":
        cmd_check()
    elif args.command == "monitor":
        cmd_monitor(args.hours, args.interval)
    elif args.command == "report":
        cmd_report()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
