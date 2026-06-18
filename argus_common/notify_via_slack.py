#!/usr/bin/env python3
"""
notify_via_slack.py — send a Slack message via an incoming webhook.

Reads SLACK_WEBHOOK_URL from the repo-root .env
(/Users/amit/PROJ/ASHANBH/personal_agents/.env).

Usage:
  poetry run python notify_via_slack.py "your message"
  poetry run python notify_via_slack.py            # sends a default test message

Importable:
  from notify_via_slack import send_slack
  send_slack("Argus: birthday job failed!")
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
# .env lives at the repo root, one level up from argus/
load_dotenv(os.path.join(HERE, "..", ".env"))


def send_slack(text: str, webhook_url: str | None = None) -> None:
    webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL is not set (check the repo .env).")
    resp = requests.post(webhook_url, json={"text": text}, timeout=15)
    resp.raise_for_status()
    if resp.text.strip() != "ok":
        raise RuntimeError(f"Unexpected Slack response: {resp.status_code} {resp.text!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a Slack message via webhook.")
    ap.add_argument("message", nargs="?",
                    default="✅ Argus test: Slack notifications are working.")
    args = ap.parse_args()
    try:
        send_slack(args.message)
    except Exception as e:
        print(f"Slack send FAILED: {e}", file=sys.stderr)
        return 1
    print("Slack message sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
