#!/usr/bin/env python3
"""
Publisher: LinkedIn
Post articles/shares via LinkedIn API.

Setup:
  1. Create a LinkedIn App: https://www.linkedin.com/developers/apps
  2. Request "Share on LinkedIn" (w_member_social) permission
  3. Complete OAuth 2.0 flow to get access token
  4. Set environment variable:
     export LINKEDIN_ACCESS_TOKEN='...'

  For first-time OAuth setup, run:
     python3 linkedin_publisher.py --setup

  Note: LinkedIn access tokens expire after 60 days.
  You'll need to refresh periodically.
"""

import os
import sys
import json
import requests
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs


LINKEDIN_API = "https://api.linkedin.com/v2"


def check_credentials():
    if not os.environ.get("LINKEDIN_ACCESS_TOKEN"):
        return False, ["LINKEDIN_ACCESS_TOKEN"]
    return True, []


def get_user_id(access_token):
    """Get the current user's LinkedIn URN."""
    r = requests.get(
        f"{LINKEDIN_API}/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("sub")
    # Fallback to /me endpoint
    r = requests.get(
        f"{LINKEDIN_API}/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    r.raise_for_status()
    return r.json()["id"]


def publish(text, link=None):
    """Publish a post to LinkedIn.
    
    Args:
        text: Post content
        link: Optional URL to include (will be added as article share)
    
    Returns:
        dict with success status
    """
    ok, missing = check_credentials()
    if not ok:
        return {"success": False, "error": f"Missing env vars: {', '.join(missing)}. Run with --setup first."}

    access_token = os.environ["LINKEDIN_ACCESS_TOKEN"]

    try:
        user_id = get_user_id(access_token)
        author = f"urn:li:person:{user_id}"

        # Build post payload
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        # Add link if provided
        if link:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                "status": "READY",
                "originalUrl": link
            }]

        r = requests.post(
            f"{LINKEDIN_API}/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            json=payload
        )

        if r.status_code in (200, 201):
            post_id = r.headers.get("x-restli-id", r.json().get("id", "unknown"))
            return {
                "success": True,
                "post_id": post_id,
                "note": "Post published to LinkedIn. Check your profile to see it."
            }
        else:
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def oauth_setup():
    """Interactive OAuth 2.0 setup flow."""
    print("\n═══ LinkedIn OAuth Setup ═══\n")
    print("You need a LinkedIn App first.")
    print("Create one at: https://www.linkedin.com/developers/apps\n")

    client_id = input("LinkedIn App Client ID: ").strip()
    client_secret = input("LinkedIn App Client Secret: ").strip()
    redirect_uri = "https://localhost:8443/callback"

    # Step 1: Authorization URL
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile w_member_social"
    })

    print(f"\nOpening browser for authorization...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    print("After authorizing, you'll be redirected to a URL like:")
    print("https://localhost:8443/callback?code=XXXXXX\n")
    callback_url = input("Paste the full redirect URL here: ").strip()

    # Extract code
    parsed = urlparse(callback_url)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        print("Error: Could not extract authorization code.")
        return

    # Step 2: Exchange code for token
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret
        }
    )

    if r.status_code == 200:
        token = r.json()["access_token"]
        expires_in = r.json().get("expires_in", 5184000)
        print(f"\n✅ Success! Your access token (expires in {expires_in // 86400} days):\n")
        print(f"export LINKEDIN_ACCESS_TOKEN='{token}'\n")
        print("Add this to your .env or shell profile.")
    else:
        print(f"\n❌ Error: {r.text}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Publish to LinkedIn")
    parser.add_argument("--text", help="Post text")
    parser.add_argument("--text-file", help="Read text from file")
    parser.add_argument("--link", help="Optional URL to include")
    parser.add_argument("--setup", action="store_true", help="Run OAuth setup")
    args = parser.parse_args()

    if args.setup:
        oauth_setup()
    else:
        text = args.text or ""
        if args.text_file:
            with open(args.text_file) as f:
                text = f.read()
        if not text:
            print("Provide --text or --text-file")
            sys.exit(1)
        result = publish(text, args.link)
        print(json.dumps(result, indent=2))
