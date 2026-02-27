#!/usr/bin/env python3
"""
Skill: Changelog Monitor (竞品更新监控)
Track competitor websites for changes: landing pages, changelogs,
pricing pages, blog posts, and app store listings.

Workflow:
  1. snapshot  — Capture current state of all competitor pages
  2. diff      — Compare latest snapshot with previous one
  3. analyze   — AI analysis of what changed and what it means
  4. report    — Generate structured report

Usage:
  # First run: take baseline snapshots
  python3 changelog_monitor.py snapshot

  # Later: check for changes
  python3 changelog_monitor.py diff

  # Full report with AI analysis
  python3 changelog_monitor.py report

  # Monitor specific competitor only
  python3 changelog_monitor.py snapshot --competitor manus
  python3 changelog_monitor.py diff --competitor manus

  # Auto-monitor (run daily via cron or manual)
  python3 changelog_monitor.py auto --interval 24

  # Show tracking status
  python3 changelog_monitor.py status
"""

import os
import sys
import json
import hashlib
import re
import argparse
import time
import difflib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR = os.path.join(PROJECT_DIR, "configs")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8"
}


def ensure_dirs():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


def load_competitors():
    path = os.path.join(CONFIG_DIR, "competitors.json")
    if not os.path.exists(path):
        sys.stderr.write(f"[changelog-monitor] Config not found: {path}\n")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("competitors", [])


def clean_html(html):
    """Extract readable text from HTML, removing scripts/styles/tags."""
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"')
    return text


def url_to_filename(url):
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    name = parsed.netloc + parsed.path
    name = re.sub(r'[^\w\-.]', '_', name).strip('_')
    return name[:100]


# ═══════════════════════════════════════════════════════════════
# Snapshot: capture current page state
# ═══════════════════════════════════════════════════════════════

def fetch_page(url):
    """Fetch a page and return cleaned text + metadata."""
    if not HAS_REQUESTS:
        return None, "pip install requests"

    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        raw_html = r.text
        clean_text = clean_html(raw_html)
        return {
            "url": url,
            "status_code": r.status_code,
            "content_length": len(raw_html),
            "text_length": len(clean_text),
            "text": clean_text,
            "title": extract_title(raw_html),
            "meta_description": extract_meta(raw_html, "description"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.md5(clean_text.encode()).hexdigest()
        }, None
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP {e.response.status_code}"
    except requests.exceptions.ConnectionError:
        return None, "Connection failed"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def extract_title(html):
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_meta(html, name):
    match = re.search(
        rf'<meta[^>]*name=["\']?{name}["\']?[^>]*content=["\']([^"\']*)["\']',
        html, re.IGNORECASE
    )
    if not match:
        match = re.search(
            rf'<meta[^>]*content=["\']([^"\']*)["\']?[^>]*name=["\']?{name}["\']',
            html, re.IGNORECASE
        )
    return match.group(1).strip() if match else ""


def save_snapshot(competitor_id, page_type, url, data):
    """Save a snapshot to disk."""
    ensure_dirs()
    comp_dir = os.path.join(SNAPSHOT_DIR, competitor_id)
    os.makedirs(comp_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{page_type}_{timestamp}.json"
    filepath = os.path.join(comp_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Also save as "latest" for easy comparison
    latest_path = os.path.join(comp_dir, f"{page_type}_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def get_previous_snapshot(competitor_id, page_type):
    """Get the second-most-recent snapshot (the one before latest)."""
    comp_dir = os.path.join(SNAPSHOT_DIR, competitor_id)
    if not os.path.exists(comp_dir):
        return None

    # Find all snapshots for this page type
    files = sorted([
        f for f in os.listdir(comp_dir)
        if f.startswith(f"{page_type}_") and f != f"{page_type}_latest.json"
    ])

    if len(files) < 2:
        return None  # Need at least 2 snapshots to compare

    # Return second-to-last (the previous one)
    prev_path = os.path.join(comp_dir, files[-2])
    with open(prev_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_snapshot(competitor_id, page_type):
    """Get the most recent snapshot."""
    latest_path = os.path.join(SNAPSHOT_DIR, competitor_id, f"{page_type}_latest.json")
    if not os.path.exists(latest_path):
        return None
    with open(latest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# Diff: compare snapshots
# ═══════════════════════════════════════════════════════════════

def compute_diff(old_data, new_data, context_lines=3):
    """Compute differences between two snapshots."""
    if not old_data or not new_data:
        return None

    old_text = old_data.get("text", "")
    new_text = new_data.get("text", "")

    # Quick check: any change?
    if old_data.get("content_hash") == new_data.get("content_hash"):
        return {"changed": False}

    # Split into sentences for better diff
    old_sentences = re.split(r'(?<=[.!?。！？])\s+', old_text)
    new_sentences = re.split(r'(?<=[.!?。！？])\s+', new_text)

    differ = difflib.unified_diff(
        old_sentences, new_sentences,
        fromfile=f"Previous ({old_data.get('fetched_at', '?')})",
        tofile=f"Current ({new_data.get('fetched_at', '?')})",
        lineterm="",
        n=context_lines
    )
    diff_lines = list(differ)

    # Count changes
    added = [l[1:] for l in diff_lines if l.startswith('+') and not l.startswith('+++')]
    removed = [l[1:] for l in diff_lines if l.startswith('-') and not l.startswith('---')]

    # Title change
    title_changed = old_data.get("title") != new_data.get("title")

    # Meta description change
    meta_changed = old_data.get("meta_description") != new_data.get("meta_description")

    # Content length change
    len_old = old_data.get("text_length", 0)
    len_new = new_data.get("text_length", 0)
    len_change = len_new - len_old
    len_change_pct = (len_change / len_old * 100) if len_old > 0 else 0

    return {
        "changed": True,
        "url": new_data.get("url", ""),
        "title_changed": title_changed,
        "old_title": old_data.get("title", ""),
        "new_title": new_data.get("title", ""),
        "meta_changed": meta_changed,
        "old_meta": old_data.get("meta_description", ""),
        "new_meta": new_data.get("meta_description", ""),
        "content_added": added[:20],  # Cap at 20 items
        "content_removed": removed[:20],
        "added_count": len(added),
        "removed_count": len(removed),
        "length_change": len_change,
        "length_change_pct": round(len_change_pct, 1),
        "old_hash": old_data.get("content_hash"),
        "new_hash": new_data.get("content_hash"),
        "old_time": old_data.get("fetched_at"),
        "new_time": new_data.get("fetched_at"),
        "diff_text": "\n".join(diff_lines[:100])
    }


# ═══════════════════════════════════════════════════════════════
# AI Analysis
# ═══════════════════════════════════════════════════════════════

def ai_analyze_changes(competitor_name, changes, provider="openai", model=None, base_url=None):
    """Use AI to analyze what the changes mean strategically."""
    # Build summary of changes
    change_summary = []
    for page_type, diff in changes.items():
        if not diff or not diff.get("changed"):
            continue
        section = f"\n[{page_type.upper()}] {diff['url']}\n"
        if diff.get("title_changed"):
            section += f"  Title: '{diff['old_title']}' → '{diff['new_title']}'\n"
        if diff.get("meta_changed"):
            section += f"  Meta: '{diff['old_meta'][:80]}' → '{diff['new_meta'][:80]}'\n"
        section += f"  Content: +{diff['added_count']} additions, -{diff['removed_count']} removals\n"
        section += f"  Size change: {diff['length_change']:+d} chars ({diff['length_change_pct']:+.1f}%)\n"
        if diff.get("content_added"):
            section += "  New content samples:\n"
            for item in diff["content_added"][:5]:
                section += f"    + {item[:120]}\n"
        if diff.get("content_removed"):
            section += "  Removed content samples:\n"
            for item in diff["content_removed"][:3]:
                section += f"    - {item[:120]}\n"
        change_summary.append(section)

    if not change_summary:
        return "No significant changes detected."

    prompt = f"""You are a competitive intelligence analyst. Analyze the following changes detected on {competitor_name}'s website and tell me:

1. **What changed**: Summarize the key changes in plain language
2. **Why it matters**: What does this suggest about their strategy?
3. **Recommended response**: What should we consider doing in response?

Changes detected:
{"".join(change_summary)}

Be specific and actionable. Focus on strategic implications, not cosmetic changes.
Write in Chinese (简体中文).
"""

    try:
        if provider == "anthropic" and not base_url:
            import anthropic
            client = anthropic.Anthropic()
            r = client.messages.create(
                model=model or "claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return r.content[0].text
        else:
            from openai import OpenAI
            kwargs = {}
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
            r = client.chat.completions.create(
                model=model or "gpt-4o-mini",
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": "You are a competitive intelligence analyst. Respond in Chinese."},
                    {"role": "user", "content": prompt}
                ]
            )
            return r.choices[0].message.content
    except Exception as e:
        return f"AI analysis failed: {e}"


# ═══════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════

def cmd_snapshot(competitor_filter=None):
    """Take snapshots of all competitor pages."""
    competitors = load_competitors()
    if not competitors:
        print("No competitors configured. Edit configs/competitors.json")
        return

    print(f"\n📸 Taking snapshots...\n")
    total = 0
    errors = 0

    for comp in competitors:
        comp_id = comp["id"]
        comp_name = comp["name"]

        if competitor_filter and comp_id != competitor_filter:
            continue

        urls = comp.get("urls", {})
        print(f"  {comp_name}:")

        for page_type, url in urls.items():
            if not url:
                continue

            sys.stdout.write(f"    {page_type}: {url[:50]}... ")
            sys.stdout.flush()

            data, error = fetch_page(url)
            if data:
                filepath = save_snapshot(comp_id, page_type, url, data)
                print(f"✅ ({data['text_length']} chars)")
                total += 1
            else:
                print(f"❌ {error}")
                errors += 1

        # GitHub
        github_url = comp.get("github", "")
        if github_url:
            sys.stdout.write(f"    github: {github_url[:50]}... ")
            data, error = fetch_page(github_url)
            if data:
                save_snapshot(comp_id, "github", github_url, data)
                print(f"✅")
                total += 1
            else:
                print(f"❌ {error}")

    print(f"\n  📊 Done: {total} pages captured, {errors} errors\n")


def cmd_diff(competitor_filter=None):
    """Compare latest snapshots with previous ones."""
    competitors = load_competitors()
    all_changes = {}

    print(f"\n🔍 Checking for changes...\n")

    for comp in competitors:
        comp_id = comp["id"]
        comp_name = comp["name"]

        if competitor_filter and comp_id != competitor_filter:
            continue

        urls = comp.get("urls", {})
        comp_changes = {}
        has_changes = False

        print(f"  {comp_name}:")

        for page_type, url in urls.items():
            if not url:
                continue

            # Get latest and previous
            latest = get_latest_snapshot(comp_id, page_type)
            prev = get_previous_snapshot(comp_id, page_type)

            if not latest:
                print(f"    {page_type}: ⚠️  No snapshot yet (run 'snapshot' first)")
                continue
            if not prev:
                print(f"    {page_type}: 📸 Only 1 snapshot (need 2+ to compare)")
                continue

            diff = compute_diff(prev, latest)
            comp_changes[page_type] = diff

            if diff and diff.get("changed"):
                has_changes = True
                print(f"    {page_type}: 🔴 CHANGED (+{diff['added_count']}/-{diff['removed_count']}, {diff['length_change']:+d} chars)")
                if diff.get("title_changed"):
                    print(f"      Title: '{diff['old_title'][:40]}' → '{diff['new_title'][:40]}'")
            else:
                print(f"    {page_type}: ✅ No changes")

        if has_changes:
            all_changes[comp_name] = comp_changes

        print()

    if not all_changes:
        print("  🟢 No changes detected across all competitors.\n")
    else:
        print(f"  🔴 Changes detected for: {', '.join(all_changes.keys())}\n")

    return all_changes


def cmd_report(competitor_filter=None, provider="openai", model=None, base_url=None):
    """Full report: snapshot → diff → AI analysis."""
    # Step 1: Take new snapshots
    print("=" * 60)
    print("  📊 COMPETITIVE INTELLIGENCE REPORT")
    print("=" * 60)

    cmd_snapshot(competitor_filter)

    # Step 2: Diff
    all_changes = cmd_diff(competitor_filter)

    if not all_changes:
        print("No changes to analyze. Report complete.\n")
        return

    # Step 3: AI Analysis
    print("🤖 Running AI analysis...\n")

    report_lines = []
    report_lines.append(f"# 竞品监控报告")
    report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    for comp_name, changes in all_changes.items():
        report_lines.append(f"\n## {comp_name}\n")

        # Raw changes
        for page_type, diff in changes.items():
            if diff and diff.get("changed"):
                report_lines.append(f"### {page_type}")
                report_lines.append(f"- URL: {diff.get('url', '')}")
                report_lines.append(f"- 变化: +{diff['added_count']} 新增, -{diff['removed_count']} 删除")
                report_lines.append(f"- 内容量变化: {diff['length_change']:+d} 字符 ({diff['length_change_pct']:+.1f}%)")
                if diff.get("title_changed"):
                    report_lines.append(f"- 标题变化: '{diff['old_title']}' → '{diff['new_title']}'")
                report_lines.append("")

        # AI Analysis
        analysis = ai_analyze_changes(comp_name, changes, provider, model, base_url)
        report_lines.append(f"### AI 分析\n")
        report_lines.append(analysis)
        report_lines.append("")

    report_text = "\n".join(report_lines)

    # Save report
    ensure_dirs()
    report_file = os.path.join(REPORTS_DIR, f"competitive_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(report_text)
    print(f"\n📄 Report saved: {report_file}\n")


def cmd_status():
    """Show current tracking status."""
    competitors = load_competitors()

    print(f"\n{'='*60}")
    print(f"  📡 MONITORING STATUS")
    print(f"{'='*60}\n")

    for comp in competitors:
        comp_id = comp["id"]
        comp_name = comp["name"]
        urls = comp.get("urls", {})

        print(f"  {comp_name} ({comp_id}):")

        comp_dir = os.path.join(SNAPSHOT_DIR, comp_id)
        if not os.path.exists(comp_dir):
            print(f"    ⚠️  No snapshots yet\n")
            continue

        for page_type, url in urls.items():
            if not url:
                continue

            latest = get_latest_snapshot(comp_id, page_type)
            if latest:
                fetched = latest.get("fetched_at", "?")
                try:
                    t = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
                    age = datetime.now(timezone.utc) - t
                    age_str = f"{age.days}d {age.seconds//3600}h ago"
                except:
                    age_str = "?"
                print(f"    {page_type}: ✅ Last snapshot {age_str} ({latest.get('text_length', '?')} chars)")
            else:
                print(f"    {page_type}: ❌ No snapshot")

        # Count total snapshots
        files = [f for f in os.listdir(comp_dir) if f.endswith('.json') and 'latest' not in f]
        print(f"    📊 Total snapshots: {len(files)}")
        print()

    print(f"{'='*60}\n")


def cmd_auto(interval_hours=24, provider="openai", model=None, base_url=None):
    """Continuous monitoring."""
    print(f"\n🔄 Starting auto-monitor (every {interval_hours}h)")
    print(f"   Press Ctrl+C to stop\n")

    try:
        while True:
            print(f"\n{'─'*40}")
            print(f"  Check at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            print(f"{'─'*40}")
            cmd_report(provider=provider, model=model, base_url=base_url)

            next_check = datetime.now() + timedelta(hours=interval_hours)
            print(f"  Next check at {next_check.strftime('%Y-%m-%d %H:%M')}")
            time.sleep(interval_hours * 3600)
    except KeyboardInterrupt:
        print("\n\n⏹️  Auto-monitor stopped.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor competitor websites for changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  snapshot   Capture current state of competitor pages
  diff       Compare with previous snapshots
  report     Full report with AI analysis
  status     Show monitoring status
  auto       Continuous monitoring

Examples:
  # First time: take baseline
  python3 changelog_monitor.py snapshot

  # Next day: check changes
  python3 changelog_monitor.py diff

  # Full report with AI analysis
  python3 changelog_monitor.py report

  # Monitor one competitor
  python3 changelog_monitor.py report --competitor manus

  # Use cheaper model
  python3 changelog_monitor.py report --base-url https://api.deepseek.com --model deepseek-chat

  # Auto-run every 24 hours
  python3 changelog_monitor.py auto --interval 24
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Capture page snapshots")
    p_snap.add_argument("--competitor", help="Only this competitor ID")

    # diff
    p_diff = subparsers.add_parser("diff", help="Compare snapshots")
    p_diff.add_argument("--competitor", help="Only this competitor ID")

    # report
    p_report = subparsers.add_parser("report", help="Full report with AI analysis")
    p_report.add_argument("--competitor", help="Only this competitor ID")
    p_report.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    p_report.add_argument("--model", help="AI model")
    p_report.add_argument("--base-url", help="Custom API base URL")

    # status
    subparsers.add_parser("status", help="Show monitoring status")

    # auto
    p_auto = subparsers.add_parser("auto", help="Continuous monitoring")
    p_auto.add_argument("--interval", type=int, default=24, help="Check interval (hours)")
    p_auto.add_argument("--provider", default="openai")
    p_auto.add_argument("--model", help="AI model")
    p_auto.add_argument("--base-url", help="Custom API base URL")

    args = parser.parse_args()

    if args.command == "snapshot":
        cmd_snapshot(args.competitor)
    elif args.command == "diff":
        cmd_diff(args.competitor)
    elif args.command == "report":
        cmd_report(args.competitor, args.provider, getattr(args, 'model', None), getattr(args, 'base_url', None))
    elif args.command == "status":
        cmd_status()
    elif args.command == "auto":
        cmd_auto(args.interval, args.provider, getattr(args, 'model', None), getattr(args, 'base_url', None))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
