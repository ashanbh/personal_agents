#!/usr/bin/env python3
"""
notify_via_whatsapp.py — send a WhatsApp message TO YOURSELF (self-notification).

This is a notification channel for Argus/reminders — it messages YOUR OWN
number (WHATSAPP_TO in the repo-root .env), never third parties.

Stdlib-only. Uses the whatsapp:// URL scheme + a synthetic Return keypress, so:
  - WhatsApp desktop must be installed and logged in,
  - Accessibility permission is required for the keystroke,
  - it briefly steals window focus (inherent to this method).
Multi-line messages are flattened to one line (the URL scheme can't carry
newlines reliably).

.env key:
  WHATSAPP_TO=+1415...   # your own WhatsApp number

Usage:
  python3 notify_via_whatsapp.py "message text"
  python3 notify_via_whatsapp.py --to +14155551234 "override target"
"""

import argparse
import os
import re
import subprocess
import sys
import time
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "..", ".env")


def load_env(path: str) -> dict:
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


def send_whatsapp_notification(message: str, to: Optional[str] = None,
                               send_delay: float = 4.0) -> str:
    to = to or os.environ.get("WHATSAPP_TO") or load_env(ENV_PATH).get("WHATSAPP_TO")
    if not to:
        raise RuntimeError("WHATSAPP_TO is not set (add it to the repo .env).")
    number = re.sub(r"\D", "", to)
    # Flatten newlines: the URL scheme can't carry them.
    flat = " | ".join(ln.strip() for ln in message.splitlines() if ln.strip())
    url = f"whatsapp://send?phone={number}&text={flat}"
    subprocess.run(["open", url], check=True)
    time.sleep(send_delay)
    press_return = (
        'tell application "WhatsApp" to activate\n'
        'delay 1\n'
        'tell application "System Events" to keystroke return'
    )
    res = subprocess.run(["osascript", "-e", press_return],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")
    return number


def main() -> int:
    ap = argparse.ArgumentParser(description="WhatsApp yourself a notification.")
    ap.add_argument("--to", default=None, help="Override target (defaults to WHATSAPP_TO).")
    ap.add_argument("--delay", type=float, default=4.0,
                    help="Seconds to wait for WhatsApp to open before pressing Send.")
    ap.add_argument("message", nargs="?",
                    default="✅ Argus test: WhatsApp self-notifications work.")
    args = ap.parse_args()
    try:
        to = send_whatsapp_notification(args.message, args.to, send_delay=args.delay)
    except Exception as e:
        print(f"WhatsApp notification FAILED: {e}", file=sys.stderr)
        return 1
    print(f"WhatsApp notification sent to {to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
