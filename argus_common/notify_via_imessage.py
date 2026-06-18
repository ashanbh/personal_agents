#!/usr/bin/env python3
"""
notify_via_imessage.py — send an iMessage TO YOURSELF (self-notification).

This is a notification channel for Argus/reminders — it messages YOUR OWN
number (IMESSAGE_TO in the repo-root .env), never third parties.

Stdlib-only (osascript via Messages.app), so it runs under /usr/bin/python3
with no venv. Requires Messages to be signed in and Automation permission
("... wants to control Messages") granted to the caller on first run.

.env key:
  IMESSAGE_TO=+1415...   # your own iMessage number

Usage:
  python3 notify_via_imessage.py "message text"
  python3 notify_via_imessage.py --to +14155551234 "override target"

Importable:
  from notify_via_imessage import send_imessage_notification
"""

import argparse
import os
import subprocess
import sys
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "..", ".env")


def load_env(path: str) -> dict:
    """Minimal .env parser (stdlib-only; no python-dotenv dependency)."""
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def send_imessage_notification(message: str, to: Optional[str] = None) -> str:
    to = to or os.environ.get("IMESSAGE_TO") or load_env(ENV_PATH).get("IMESSAGE_TO")
    if not to:
        raise RuntimeError("IMESSAGE_TO is not set (add it to the repo .env).")
    script = (
        'on run {addr, msg}\n'
        '  tell application "Messages"\n'
        '    try\n'
        '      set svc to 1st service whose service type = iMessage\n'
        '      send msg to buddy addr of svc\n'
        '    on error\n'
        '      set acct to 1st account whose service type = iMessage\n'
        '      send msg to participant addr of acct\n'
        '    end try\n'
        '  end tell\n'
        'end run'
    )
    res = subprocess.run(["osascript", "-e", script, to, message],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")
    return to


def main() -> int:
    ap = argparse.ArgumentParser(description="iMessage yourself a notification.")
    ap.add_argument("--to", default=None, help="Override target (defaults to IMESSAGE_TO).")
    ap.add_argument("message", nargs="?",
                    default="✅ Argus test: iMessage self-notifications work.")
    args = ap.parse_args()
    try:
        to = send_imessage_notification(args.message, args.to)
    except Exception as e:
        print(f"iMessage notification FAILED: {e}", file=sys.stderr)
        return 1
    print(f"iMessage notification sent to {to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
