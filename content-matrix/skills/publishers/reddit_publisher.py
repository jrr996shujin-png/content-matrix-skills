#!/usr/bin/env python3
"""
Publisher: Reddit
Post to subreddits via Reddit API (PRAW).

Setup:
  1. Go to https://www.reddit.com/prefs/apps
  2. Create a "script" type app
  3. Set environment variables:
     export REDDIT_CLIENT_ID='...'
     export REDDIT_CLIENT_SECRET='...'
     export REDDIT_USERNAME='...'
     export REDDIT_PASSWORD='...'

  pip install praw
"""

import os
import sys
import json


def check_credentials():
    required = [
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
        "REDDIT_USERNAME", "REDDIT_PASSWORD"
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, missing
    return True, []


def get_client():
    try:
        import praw
    except ImportError:
        raise RuntimeError("pip install praw")

    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="script:content-matrix:v1.0 (by /u/{})".format(os.environ["REDDIT_USERNAME"])
    )


def publish(title, body, subreddit="test"):
    """Post a text submission to a subreddit.
    
    Args:
        title: Post title
        body: Post body (selftext, Markdown supported)
        subreddit: Target subreddit name (without r/)
    
    Returns:
        dict with success status and post URL
    """
    ok, missing = check_credentials()
    if not ok:
        return {"success": False, "error": f"Missing env vars: {', '.join(missing)}"}

    try:
        reddit = get_client()
        sub = reddit.subreddit(subreddit)

        # Check if subreddit allows text posts
        # (some subreddits are link-only)
        submission = sub.submit(
            title=title,
            selftext=body
        )

        return {
            "success": True,
            "url": f"https://www.reddit.com{submission.permalink}",
            "post_id": submission.id,
            "subreddit": subreddit
        }
    except Exception as e:
        error_msg = str(e)
        # Common errors
        if "SUBREDDIT_NOTALLOWED" in error_msg:
            return {"success": False, "error": f"Not allowed to post in r/{subreddit}. Check subreddit rules."}
        elif "RATELIMIT" in error_msg:
            return {"success": False, "error": "Rate limited. Wait a few minutes and try again."}
        return {"success": False, "error": error_msg}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Publish to Reddit")
    parser.add_argument("--title", required=True, help="Post title")
    parser.add_argument("--body", help="Post body text")
    parser.add_argument("--body-file", help="Read body from file")
    parser.add_argument("--subreddit", default="test", help="Target subreddit (default: test)")
    args = parser.parse_args()

    body = args.body or ""
    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()

    result = publish(args.title, body, args.subreddit)
    print(json.dumps(result, indent=2))
