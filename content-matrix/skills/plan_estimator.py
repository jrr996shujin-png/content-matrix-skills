#!/usr/bin/env python3
"""
Skill: Plan & Cost Estimator (Universal)
Preview execution plan and estimate token cost BEFORE running AI analysis.

Input:  Standard data contract JSON (stdin or file)
Output: Plan summary with cost estimate (stdout)

Usage:
  cat filtered.json | python3 plan_estimator.py
  python3 plan_estimator.py -i filtered.json
  python3 plan_estimator.py -i filtered.json --model gpt-4o --confirm

Pipe-friendly (insert before ai_analyzer):
  python3 reddit_fetcher.py "https://..." | \
  python3 keyword_filter.py "skills" | \
  python3 plan_estimator.py --confirm | \
  python3 ai_analyzer.py | \
  python3 markdown_reporter.py -o report.md
"""

import json
import sys
import argparse
import math

# ═══════════════════════════════════════════════════════════════
# Token pricing per 1M tokens (as of Feb 2026, approximate)
# ═══════════════════════════════════════════════════════════════

PRICING = {
    # OpenAI
    "gpt-4o":           {"input": 2.50,  "output": 10.00, "provider": "OpenAI"},
    "gpt-4o-mini":      {"input": 0.15,  "output": 0.60,  "provider": "OpenAI"},
    "gpt-4.1":          {"input": 2.00,  "output": 8.00,  "provider": "OpenAI"},
    "gpt-4.1-mini":     {"input": 0.40,  "output": 1.60,  "provider": "OpenAI"},
    "gpt-4.1-nano":     {"input": 0.10,  "output": 0.40,  "provider": "OpenAI"},
    "o3-mini":          {"input": 1.10,  "output": 4.40,  "provider": "OpenAI"},

    # Anthropic
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00, "provider": "Anthropic"},
    "claude-haiku-4-5-20251001":  {"input": 0.80, "output": 4.00,  "provider": "Anthropic"},

    # Kimi / Moonshot
    "kimi-k2.5":        {"input": 0.60,  "output": 2.40,  "provider": "Moonshot"},
    "moonshot-v1-128k": {"input": 0.84,  "output": 0.84,  "provider": "Moonshot"},

    # DeepSeek
    "deepseek-chat":    {"input": 0.14,  "output": 0.28,  "provider": "DeepSeek"},
    "deepseek-reasoner":{"input": 0.55,  "output": 2.19,  "provider": "DeepSeek"},

    # Local / Free
    "llama3":           {"input": 0.00,  "output": 0.00,  "provider": "Ollama (local)"},
    "qwen2":            {"input": 0.00,  "output": 0.00,  "provider": "Ollama (local)"},
}

DEFAULT_MODEL = "gpt-4o-mini"


def estimate_tokens(text):
    """Rough token estimate: ~1 token per 4 chars for English, ~1 token per 2 chars for CJK."""
    if not text:
        return 0
    # Simple heuristic
    return max(1, len(text) // 3)


def analyze_data(data):
    """Analyze data contract and return plan details."""
    posts = data.get("posts", [])
    source = data.get("source", "unknown")
    source_id = data.get("source_id", "")
    meta = data.get("metadata", {})
    keywords = meta.get("keywords", [])

    total_posts = meta.get("total_posts", len(posts))
    matched_posts = meta.get("matched_posts", len(posts))

    # Calculate text volume
    total_chars = 0
    total_comments = 0
    for p in posts:
        total_chars += len(p.get("title", "")) + len(p.get("body", ""))
        for c in p.get("comments", []):
            total_chars += len(c.get("body", ""))
            total_comments += 1

    # The AI analyzer truncates to ~14000 chars and adds prompt template (~500 chars)
    ai_input_chars = min(total_chars, 14000) + 500
    ai_input_tokens = estimate_tokens(ai_input_chars * "a")  # rough
    ai_input_tokens = max(ai_input_tokens, len(str(ai_input_chars)))
    ai_input_tokens = min(total_chars, 14000) // 3 + 200  # prompt overhead

    # Estimated output: ~2000-3000 tokens for analysis
    ai_output_tokens = 2500

    return {
        "source": source,
        "source_id": source_id,
        "keywords": keywords,
        "total_posts_scanned": total_posts,
        "matched_posts": matched_posts,
        "total_comments": total_comments,
        "total_chars": total_chars,
        "ai_input_chars": min(total_chars, 14000) + 500,
        "ai_input_tokens": ai_input_tokens,
        "ai_output_tokens": ai_output_tokens,
        "total_tokens": ai_input_tokens + ai_output_tokens,
    }


def estimate_cost(plan, model=DEFAULT_MODEL):
    """Calculate estimated cost for a given model."""
    pricing = PRICING.get(model)
    if not pricing:
        return None, None, None

    input_cost = (plan["ai_input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (plan["ai_output_tokens"] / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    return input_cost, output_cost, total_cost


def format_plan(plan, models=None):
    """Format plan as readable output."""
    if models is None:
        models = ["gpt-4o-mini", "gpt-4o", "claude-sonnet-4-5-20250929", "kimi-k2.5", "deepseek-chat", "llama3"]

    output = []
    output.append("=" * 60)
    output.append("  📋 EXECUTION PLAN")
    output.append("=" * 60)
    output.append("")
    output.append(f"  Source:          {plan['source']} / {plan['source_id']}")
    output.append(f"  Keywords:        {', '.join(plan['keywords']) if plan['keywords'] else 'N/A'}")
    output.append(f"  Posts scanned:   {plan['total_posts_scanned']}")
    output.append(f"  Posts matched:   {plan['matched_posts']}")
    output.append(f"  Comments:        {plan['total_comments']}")
    output.append(f"  Total text:      {plan['total_chars']:,} chars")
    output.append("")
    output.append("  Steps:")
    output.append("  ┌─ ✅ 1. Fetch data        (done, 0 tokens)")
    output.append("  ├─ ✅ 2. Filter keywords    (done, 0 tokens)")
    output.append(f"  ├─ ⏳ 3. AI Analysis       (~{plan['ai_input_tokens']:,} input + ~{plan['ai_output_tokens']:,} output tokens)")
    output.append("  └─ ⏳ 4. Generate report   (0 tokens)")
    output.append("")
    output.append(f"  Total estimated tokens:  ~{plan['total_tokens']:,}")
    output.append("")
    output.append("-" * 60)
    output.append("  💰 COST ESTIMATE BY MODEL")
    output.append("-" * 60)
    output.append("")
    output.append(f"  {'Model':<35} {'Provider':<15} {'Est. Cost':>10}")
    output.append(f"  {'─'*35} {'─'*15} {'─'*10}")

    for model in models:
        pricing = PRICING.get(model)
        if not pricing:
            continue
        _, _, total_cost = estimate_cost(plan, model)
        if total_cost == 0:
            cost_str = "FREE"
        elif total_cost < 0.01:
            cost_str = f"< $0.01"
        else:
            cost_str = f"${total_cost:.4f}"
        output.append(f"  {model:<35} {pricing['provider']:<15} {cost_str:>10}")

    output.append("")
    output.append("=" * 60)

    return "\n".join(output)


def run(data, model=DEFAULT_MODEL, confirm=False):
    """Main entry point.
    
    If confirm=False: prints plan, returns None (pipeline stops).
    If confirm=True: prints plan, passes data through (pipeline continues).
    """
    plan = analyze_data(data)
    plan_text = format_plan(plan)

    sys.stderr.write(plan_text + "\n")

    if not confirm:
        sys.stderr.write("\n  ⏸️  Pipeline paused. Review the plan above.\n")
        sys.stderr.write("  To continue, add --confirm flag.\n\n")
        return None
    else:
        sys.stderr.write("\n  ▶️  Plan confirmed. Continuing pipeline...\n\n")
        return data


def main():
    parser = argparse.ArgumentParser(
        description="Preview execution plan and estimate AI cost before running.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Just see the plan (pipeline stops)
  cat filtered.json | python3 plan_estimator.py

  # See plan and continue (pipeline proceeds)
  cat filtered.json | python3 plan_estimator.py --confirm | python3 ai_analyzer.py

  # Check cost for a specific model
  python3 plan_estimator.py -i filtered.json --model claude-sonnet-4-5-20250929
"""
    )
    parser.add_argument("-i", "--input", help="Input JSON (default: stdin)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Primary model to estimate (default: {DEFAULT_MODEL})")
    parser.add_argument("--confirm", action="store_true", help="Confirm and pass data through (pipeline continues)")
    args = parser.parse_args()

    # Read input
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif not sys.stdin.isatty():
        data = json.load(sys.stdin)
    else:
        print("Error: provide input via -i flag or stdin pipe")
        sys.exit(1)

    result = run(data, args.model, args.confirm)

    # If confirmed, pass data through to next skill in pipe
    if result is not None:
        json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
