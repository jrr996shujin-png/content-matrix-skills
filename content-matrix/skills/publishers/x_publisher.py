#!/usr/bin/env python3
"""
Publisher: X (Twitter)
Post tweets and threads via Twitter API v2.

Setup:
  1. Apply for Twitter Developer Account: https://developer.twitter.com
  2. Create a project & app, get API keys
  3. Set environment variables:
     export TWITTER_API_KEY='...'
     export TWITTER_API_SECRET='...'
     export TWITTER_ACCESS_TOKEN='...'
     export TWITTER_ACCESS_SECRET='...'

  Or install tweepy: pip install tweepy
"""

import os
import sys
import json
import time

def check_credentials():
    """Check if Twitter credentials are configured."""
    required = [
        "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, missing
    return True, []


def publish_tweet(text):
    """Publish a single tweet (≤280 chars)."""
    try:
        import tweepy
    except ImportError:
        return {"success": False, "error": "pip install tweepy"}

    ok, missing = check_credentials()
    if not ok:
        return {"success": False, "error": f"Missing env vars: {', '.join(missing)}"}

    try:
        client = tweepy.Client(
            consumer_key=os.environ["TWITTER_API_KEY"],
            consumer_secret=os.environ["TWITTER_API_SECRET"],
            access_token=os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret=os.environ["TWITTER_ACCESS_SECRET"]
        )
        response = client.create_tweet(text=text[:280])
        tweet_id = response.data["id"]
        url = f"https://x.com/i/status/{tweet_id}"
        return {"success": True, "url": url, "tweet_id": tweet_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def publish_thread(tweets):
    """Publish a thread (list of tweet texts).
    
    Args:
        tweets: list of strings, each ≤280 chars
    """
    try:
        import tweepy
    except ImportError:
        return {"success": False, "error": "pip install tweepy"}

    ok, missing = check_credentials()
    if not ok:
        return {"success": False, "error": f"Missing env vars: {', '.join(missing)}"}

    try:
        client = tweepy.Client(
            consumer_key=os.environ["TWITTER_API_KEY"],
            consumer_secret=os.environ["TWITTER_API_SECRET"],
            access_token=os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret=os.environ["TWITTER_ACCESS_SECRET"]
        )

        results = []
        reply_to = None

        for i, text in enumerate(tweets):
            kwargs = {"text": text[:280]}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to

            response = client.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            results.append({
                "index": i + 1,
                "tweet_id": tweet_id,
                "url": f"https://x.com/i/status/{tweet_id}"
            })
            reply_to = tweet_id

            # Small delay between tweets to avoid rate limits
            if i < len(tweets) - 1:
                time.sleep(1)

        return {
            "success": True,
            "thread_url": results[0]["url"],
            "tweets": results,
            "count": len(results)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "published": len(results) if 'results' in dir() else 0}


def publish(content, mode="tweet"):
    """Main entry point.
    
    Args:
        content: str (single tweet) or list[str] (thread)
        mode: "tweet" or "thread"
    """
    if mode == "thread" and isinstance(content, list):
        return publish_thread(content)
    else:
        return publish_tweet(content if isinstance(content, str) else content[0])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Publish to X/Twitter")
    parser.add_argument("text", nargs="?", help="Tweet text")
    parser.add_argument("--thread", nargs="+", help="Thread tweets (multiple strings)")
    parser.add_argument("--file", help="Read content from file")
    args = parser.parse_args()

    if args.thread:
        result = publish(args.thread, mode="thread")
    elif args.file:
        with open(args.file) as f:
            result = publish(f.read().strip(), mode="tweet")
    elif args.text:
        result = publish(args.text, mode="tweet")
    else:
        print("Provide tweet text or --thread")
        sys.exit(1)

    print(json.dumps(result, indent=2))
