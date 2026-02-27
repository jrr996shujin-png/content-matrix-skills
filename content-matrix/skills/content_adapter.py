#!/usr/bin/env python3
"""
Skill: Content Adapter (跨平台内容分发)
Takes a "mother content" and generates platform-specific versions
for Xiaohongshu, Reddit, X (tweet + thread), and LinkedIn.

Usage:
  python3 content_adapter.py "你的母体内容" [options]
  python3 content_adapter.py -f content.txt --platforms x,reddit,linkedin
  python3 content_adapter.py "母体内容" --provider anthropic --model claude-sonnet-4-5-20250929

Output: JSON with all platform versions + publish schedule

VERSION: 5.4-sequential
"""

import json
import sys
import os
import argparse
import re
import traceback
from datetime import datetime, timezone

# Force UTF-8 encoding to avoid ASCII errors with Chinese/Unicode content
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ['PYTHONIOENCODING'] = 'utf-8'

_VERSION = "5.4-sequential"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "configs")

ALL_PLATFORMS = ["xiaohongshu", "reddit", "x", "linkedin"]


def sanitize_unicode(text):
    """Replace problematic Unicode characters that cause ASCII encoding errors."""
    if not isinstance(text, str):
        return text
    replacements = {
        '\u201c': '"', '\u201d': '"',   # curly double quotes
        '\u2018': "'", '\u2019': "'",   # curly single quotes
        '\u2013': '-', '\u2014': '--',  # en/em dash
        '\u00a0': ' ',                  # non-breaking space
        '\u2026': '...',               # ellipsis
        '\uff1a': ':',                 # fullwidth colon
        '\uff0c': ',',                 # fullwidth comma
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def deep_sanitize(obj):
    """Recursively sanitize all strings in any data structure."""
    if isinstance(obj, str):
        return sanitize_unicode(obj)
    elif isinstance(obj, dict):
        return {deep_sanitize(k): deep_sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_sanitize(item) for item in obj]
    return obj


def load_config(filename):
    """Load a JSON config file."""
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        # Try relative to current dir
        path = os.path.join("configs", filename)
    if not os.path.exists(path):
        sys.stderr.write(f"[content-adapter] Warning: config not found: {filename}\n")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
        raw = sanitize_unicode(raw)
        data = json.loads(raw)
        return deep_sanitize(data)


def build_prompt(mother_content, platforms, platform_rules, publish_timing, style_config, compact=False):
    """Build the AI prompt for content adaptation.
    
    compact=True: Stripped-down prompt for models with small context windows.
    """

    # Build platform instructions (compact = much shorter)
    platform_sections = []
    for p in platforms:
        rules = platform_rules.get(p, {})
        cr = rules.get("content_rules", {})
        name = rules.get("name", p)
        lang = rules.get("language", "en")
        max_len = rules.get("max_length", rules.get("max_length_tweet", ""))

        if compact:
            # Ultra-short: only the essentials
            section = f"\n### {name} (lang:{lang}, max:{max_len})\n"
            section += f"Tone: {cr.get('tone', 'casual')}\n"
            if p == "x":
                section += "Output: 1 tweet (<=280 chars) + 1 thread (5-8 tweets)\n"
            if p == "reddit":
                subs = cr.get("subreddit_matching", {})
                if subs:
                    all_subs = [s for sl in subs.values() for s in sl]
                    section += f"Subreddits: {', '.join(all_subs[:6])}\n"
                    section += "Pick 1-2 best subreddits.\n"
            platform_sections.append(section)
            continue

        # Normal mode (original logic)
        section = f"\n### Platform: {name}\n"
        section += f"Language: {lang}\n"
        section += f"Tone: {cr.get('tone', 'N/A')}\n"
        section += f"Structure: {cr.get('structure', cr.get('structure_tweet', 'N/A'))}\n"

        if cr.get("do"):
            section += "DO:\n" + "\n".join(f"  - {d}" for d in cr["do"]) + "\n"
        if cr.get("dont"):
            section += "DON'T:\n" + "\n".join(f"  - {d}" for d in cr["dont"]) + "\n"

        if max_len:
            section += f"Max length: {max_len}\n"

        if rules.get("requires_image"):
            section += f"Requires image: {cr.get('image_suggestion', 'yes')}\n"

        if p == "x":
            section += "Generate: 1 single tweet (<=280 chars) + 1 thread (5-8 tweets, each <=280 chars)\n"

        if p == "reddit":
            subs = cr.get("subreddit_matching", {})
            if subs:
                section += "Subreddit options:\n"
                for category, sub_list in subs.items():
                    section += f"  {category}: {', '.join(sub_list)}\n"
                section += "Pick 1-2 most relevant.\n"
            post_types = cr.get("post_types", {})
            if post_types:
                section += "Post types: " + ", ".join(f"{k}({v})" for k, v in post_types.items()) + "\n"

        fmt = cr.get("format_template", cr.get("format_template_tweet", ""))
        if fmt and not compact:
            section += f"Format: {fmt}\n"

        platform_sections.append(section)

    # Build style instructions
    style_section = ""
    if style_config and style_config.get("author", {}).get("name") != "你的名字":
        author = style_config.get("author", {})
        voice = style_config.get("voice", {})
        prefs = style_config.get("content_preferences", {})

        style_section = f"## Author: {author.get('name', '')}, {author.get('role', '')}\n"
        style_section += f"Audience: {author.get('target_audience', '')}\n"
        style_section += f"Voice: {voice.get('personality', '')}\n"

        if prefs.get("always_include"):
            style_section += f"Always include: {prefs['always_include']}\n"
        if prefs.get("never_include"):
            style_section += f"Never include: {prefs['never_include']}\n"

        # Sample posts: only in non-compact mode, max 2 samples, truncated
        if not compact:
            personas = style_config.get("platform_personas", {})
            for p in platforms:
                persona = personas.get(p, {})
                samples = persona.get("sample_posts", [])
                real_samples = [s for s in samples if s and not s.startswith("贴") and not s.startswith("把")]
                if real_samples:
                    style_section += f"\n{p} sample voice:\n"
                    for s in real_samples[:2]:  # max 2 instead of 3
                        truncated = s[:300] + "..." if len(s) > 300 else s
                        style_section += f"---\n{truncated}\n---\n"

    # Timing: compact = skip entirely
    timing_section = ""
    if publish_timing and not compact:
        timing_section = "\n## Schedule\n"
        ordered = sorted(
            [(p, publish_timing.get(p, {})) for p in platforms],
            key=lambda x: x[1].get("publish_order", 99)
        )
        for p, t in ordered:
            timing_section += f"{p}: #{t.get('publish_order','?')}, {', '.join(t.get('best_days', [])[:2])} {', '.join(t.get('best_times', [])[:1])}\n"

    prompt = f"""You are a multi-platform content strategist. Create platform-native versions of this content.

## Mother Content
{mother_content}

{style_section}
## Platforms
{"".join(platform_sections)}
{timing_section}
## Output
For each platform, provide:
### [Platform Name]
**Target:** (Reddit: subreddit + why)
**Content:** (ready to copy-paste)
**Image suggestion:** (if needed)
**Publishing notes:** (timing tips)

Generate all {len(platforms)} versions now. Each must feel native to its platform.
"""
    return sanitize_unicode(prompt)


def estimate_tokens(text):
    """Rough token estimate."""
    return max(1, len(text) // 3)


def analyze_openai(prompt, model="gpt-4o-mini", base_url=None, max_tokens=4000):
    """Call OpenAI-compatible API using curl subprocess.

    v5.1 fix: Python's httpx and urllib both have encoding issues with
    non-ASCII content (httpx uses latin-1 internally, urllib's http.client
    also uses latin-1 for certain operations). Using curl via subprocess
    completely bypasses all Python HTTP encoding problems.

    The JSON payload is written to a temp file with UTF-8 encoding,
    and curl reads it directly — zero Python encoding in the HTTP path.
    """
    import subprocess
    import tempfile

    prompt = sanitize_unicode(prompt)
    system_msg = sanitize_unicode(
        "You are an expert multi-platform content strategist. "
        "You create content that feels native to each platform. "
        "When the platform language is zh-CN, write in Chinese. "
        "When it's en, write in English."
    )

    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    api_key = os.environ.get("OPENAI_API_KEY", "")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ]
    }

    # Write JSON payload to temp file (UTF-8), let curl handle the rest
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    try:
        cmd = [
            "curl", "-s", "-S", "--fail-with-body",
            "-X", "POST", url,
            "-H", "Content-Type: application/json; charset=utf-8",
            "-H", f"Authorization: Bearer {api_key}",
            "-H", "User-Agent: KimiCLI/0.77",
            "-d", f"@{tmp_path}",
            "--max-time", "120"
        ]
        sys.stderr.write(f"[content-adapter] Calling API via curl: {url}\n")
        result = subprocess.run(cmd, capture_output=True, timeout=130)

        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            raise RuntimeError(f"curl failed (code {result.returncode}): {stderr}\n{stdout}")

        data = json.loads(stdout)
    finally:
        os.unlink(tmp_path)

    return data["choices"][0]["message"]["content"]


def analyze_anthropic(prompt, model="claude-sonnet-4-5-20250929"):
    import anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=model, max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
        system="You are an expert multi-platform content strategist. You create content that feels native to each platform. When the platform language is zh-CN, write in Chinese. When it's en, write in English."
    )
    return r.content[0].text


def run(mother_content, platforms=None, provider="openai", model=None, base_url=None,
        plan_only=False, output_file=None, compact=False):
    """Main entry point.

    Args:
        mother_content: The source content to adapt
        platforms: List of platform names (default: all)
        provider: AI provider (openai/anthropic)
        model: Model name
        base_url: Custom API base URL
        plan_only: If True, only show plan without calling AI
        output_file: Optional output file path
    """
    if platforms is None:
        platforms = ALL_PLATFORMS

    # Sanitize input
    mother_content = sanitize_unicode(mother_content)

    # Load configs
    platform_rules = load_config("platform_rules.json")
    publish_timing = load_config("publish_timing.json")
    style_config = load_config("my_style.json")

    sys.stderr.write(f"[content-adapter] Mother content: {len(mother_content)} chars\n")
    sys.stderr.write(f"[content-adapter] Platforms: {', '.join(platforms)}\n")
    sys.stderr.write(f"[content-adapter] Version: {_VERSION}\n")

    # Build prompt
    prompt = build_prompt(mother_content, platforms, platform_rules, publish_timing, style_config, compact=compact)
    input_tokens = estimate_tokens(prompt)
    # Dynamic output tokens: ~2000 per platform, capped
    output_tokens = min(2000 * len(platforms), 6000)

    # ── Plan mode ──
    if plan_only:
        # Reuse plan_estimator style output
        sys.stderr.write("\n" + "=" * 60 + "\n")
        sys.stderr.write("  📋 CONTENT DISTRIBUTION PLAN\n")
        sys.stderr.write("=" * 60 + "\n\n")
        sys.stderr.write(f"  Mother content: {len(mother_content)} chars\n")
        sys.stderr.write(f"  Target platforms: {len(platforms)}\n\n")

        ordered = sorted(
            [(p, publish_timing.get(p, {})) for p in platforms],
            key=lambda x: x[1].get("publish_order", 99)
        )
        for p, t in ordered:
            rules = platform_rules.get(p, {})
            name = rules.get("name", p)
            lang = rules.get("language", "?")
            img = "📸 需要配图" if rules.get("requires_image") else "📝 纯文字"
            sys.stderr.write(f"  #{t.get('publish_order', '?')} {name} [{lang}] {img}\n")
            sys.stderr.write(f"     Best: {', '.join(t.get('best_days', []))} {', '.join(t.get('best_times', []))}\n")
            sys.stderr.write(f"     {t.get('reason', '')}\n\n")

        sys.stderr.write(f"  Estimated tokens: ~{input_tokens + output_tokens:,}\n")

        # Cost table
        from plan_estimator import PRICING
        sys.stderr.write("\n  💰 COST ESTIMATE\n")
        sys.stderr.write(f"  {'Model':<35} {'Est. Cost':>10}\n")
        sys.stderr.write(f"  {'─'*35} {'─'*10}\n")
        for m, p in PRICING.items():
            cost = (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]
            cost_str = "FREE" if cost == 0 else (f"< $0.01" if cost < 0.01 else f"${cost:.4f}")
            sys.stderr.write(f"  {m:<35} {cost_str:>10}\n")

        sys.stderr.write("\n" + "=" * 60 + "\n")
        sys.stderr.write("  ⏸️  Plan only. Add --confirm to execute.\n\n")
        return None

    # ── Execute ──
    # Sequential mode: if multiple platforms, run one at a time to avoid context overflow
    if len(platforms) > 1:
        sys.stderr.write(f"[content-adapter] Sequential mode: generating {len(platforms)} platforms one by one...\n")
        all_results = []
        for i, plat in enumerate(platforms):
            sys.stderr.write(f"\n[content-adapter] [{i+1}/{len(platforms)}] Generating {plat}...\n")
            single_prompt = build_prompt(mother_content, [plat], platform_rules, publish_timing, style_config, compact=compact)
            single_max = 4000
            try:
                if provider == "anthropic" and not base_url:
                    m = model or "claude-sonnet-4-5-20250929"
                    text = analyze_anthropic(single_prompt, m)
                else:
                    m = model or "gpt-4o-mini"
                    text = analyze_openai(single_prompt, m, base_url, max_tokens=single_max)
                sys.stderr.write(f"[content-adapter] [{i+1}/{len(platforms)}] {plat} Done!\n")
                all_results.append(text)
            except Exception as e:
                sys.stderr.write(f"[content-adapter] [{i+1}/{len(platforms)}] {plat} failed: {e}\n")
                all_results.append(f"### {plat}\n\n*AI generation failed: {e}*")
        result_text = "\n\n---\n\n".join(all_results)
    else:
        max_out = 4000
        sys.stderr.write(f"[content-adapter] Generating {len(platforms)} platform version (max_tokens={max_out}, compact={compact})...\n")
        try:
            if provider == "anthropic" and not base_url:
                m = model or "claude-sonnet-4-5-20250929"
                result_text = analyze_anthropic(prompt, m)
            else:
                m = model or "gpt-4o-mini"
                result_text = analyze_openai(prompt, m, base_url, max_tokens=max_out)
            sys.stderr.write("[content-adapter] Done!\n")
        except Exception as e:
            sys.stderr.write(f"[content-adapter] AI failed: {e}\n")
            sys.stderr.write("[content-adapter] Full traceback:\n")
            traceback.print_exc(file=sys.stderr)
            result_text = f"*AI generation failed: {e}*"

    # Build output
    result = {
        "mother_content": mother_content,
        "platforms": platforms,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_used": m,
        "content": result_text,
        "publish_schedule": {
            p: {
                "order": publish_timing.get(p, {}).get("publish_order", 99),
                "best_times": publish_timing.get(p, {}).get("best_times", []),
                "best_days": publish_timing.get(p, {}).get("best_days", []),
                "notes": publish_timing.get(p, {}).get("notes", "")
            }
            for p in platforms
        }
    }

    # Generate report
    report = generate_report(result, platform_rules)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        sys.stderr.write(f"[content-adapter] Report saved: {output_file}\n")

    return report


def generate_report(result, platform_rules):
    """Generate a Markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    report = f"""# 📣 跨平台内容分发报告

**Generated:** {now}
**Model:** {result['model_used']}
**Platforms:** {', '.join(result['platforms'])}

---

## 母体内容 (Mother Content)

{result['mother_content']}

---

## 各平台适配版本

{result['content']}

---

## 📅 发布计划 (Publishing Schedule)

| 顺序 | 平台 | 最佳时间 | 最佳日期 | 备注 |
|------|------|----------|----------|------|
"""
    ordered = sorted(result["publish_schedule"].items(), key=lambda x: x[1]["order"])
    for p, sched in ordered:
        name = platform_rules.get(p, {}).get("name", p)
        times = ", ".join(sched["best_times"][:2]) if sched["best_times"] else "N/A"
        days = ", ".join(sched["best_days"][:3]) if sched["best_days"] else "N/A"
        notes = sched.get("notes", "")
        report += f"| {sched['order']} | {name} | {times} | {days} | {notes} |\n"

    report += """
---

## ⚠️ 注意事项

- **小红书**需要配图才能发布，请根据上方建议准备封面图
- **Reddit**发帖后30分钟内请保持在线回复评论
- **LinkedIn**外链请放在评论区第一条，不要放正文
- 各平台版本可直接复制粘贴使用，建议发布前做最后人工审核
"""
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Transform mother content into multi-platform versions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate for all platforms
  python3 content_adapter.py "我们测试了AI自动剪辑长视频，发现3个意想不到的问题"

  # Only specific platforms
  python3 content_adapter.py "母体内容" --platforms x,reddit,linkedin

  # Preview plan without generating
  python3 content_adapter.py "母体内容" --plan

  # Use different AI model
  python3 content_adapter.py "母体内容" --provider anthropic --model claude-sonnet-4-5-20250929

  # Use DeepSeek (cheaper)
  python3 content_adapter.py "母体内容" --base-url https://api.deepseek.com --model deepseek-chat

  # Read content from file
  python3 content_adapter.py -f my_article.txt --platforms x,linkedin
"""
    )
    parser.add_argument("content", nargs="?", help="Mother content text")
    parser.add_argument("-f", "--file", help="Read mother content from file")
    parser.add_argument("--platforms", default=",".join(ALL_PLATFORMS),
                        help=f"Comma-separated platforms (default: all). Options: {','.join(ALL_PLATFORMS)}")
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--base-url", help="Custom API base URL")
    parser.add_argument("--plan", action="store_true", help="Only show plan, don't generate")
    parser.add_argument("--preview", action="store_true", help="Generate content, show preview, wait for confirmation before saving")
    parser.add_argument("--confirm", action="store_true", help="Execute (default behavior)")
    parser.add_argument("--compact", action="store_true", help="Use shorter prompt for models with small context windows (e.g. Kimi)")
    parser.add_argument("-o", "--output", help="Output report file (default: auto-named)")
    args = parser.parse_args()

    # Get mother content
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            mother_content = f.read().strip()
    elif args.content:
        mother_content = args.content
    else:
        print("Error: provide mother content as argument or via -f flag")
        sys.exit(1)

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    # Auto-generate output filename
    output_file = args.output
    if not output_file and not args.plan:
        safe_name = re.sub(r'[^\w\-]', '_', mother_content[:30])
        output_file = f"content_matrix_{safe_name}.md"

    result = run(
        mother_content=mother_content,
        platforms=platforms,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        plan_only=args.plan,
        output_file=None if args.preview else output_file,
        compact=args.compact
    )

    if result and args.preview:
        # Preview mode: show content, ask for confirmation
        print(result)
        print("\n" + "=" * 60)
        print("  👆 以上是各平台的内容预览")
        print("  确认发布请输入 y，取消请输入 n")
        print("=" * 60)
        try:
            answer = input("\n  确认? (y/n): ").strip().lower()
            if answer == "y":
                if output_file:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(result)
                    print(f"\n  ✅ Saved to {output_file}")
                    print(f"  📋 现在可以复制各平台内容去发布了")
                    print(f"  📊 发布后用 engagement_tracker.py 追踪数据")
                else:
                    print("\n  ✅ Confirmed. Content ready to use.")
            else:
                print("\n  ❌ Cancelled. Content not saved.")
                print("  💡 Tip: 调整 configs/platform_rules.json 后重新生成")
        except (EOFError, KeyboardInterrupt):
            print("\n  ❌ Cancelled.")
    elif result and not args.output:
        print(result)


if __name__ == "__main__":
    main()
