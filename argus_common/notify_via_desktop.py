#!/usr/bin/env python3
"""
notify_via_desktop.py — show a native macOS desktop (banner) notification.

Stdlib-only (no venv needed): tries `terminal-notifier` first (brew install
terminal-notifier), then falls back to `osascript display notification`.
Both can run via /usr/bin/python3 from launchd. No credentials required.

Banner troubleshooting:
  - terminal-notifier: System Settings > Notifications > terminal-notifier
    → set style to "Banners" or "Alerts"
  - osascript fallback: same but look for "Script Editor"
  Sound playing without a banner means the style is set to "None" — fix it
  in Notifications settings for whichever sender appears there.

Install terminal-notifier for reliable banners:
  brew install terminal-notifier

Usage:
  python3 notify_via_desktop.py "message text"
  python3 notify_via_desktop.py --title "🎂 Birthdays" --sound Glass "message"

Importable:
  from notify_via_desktop import send_desktop
  send_desktop("2 birthdays today", title="🎂 Birthday reminders")
"""

import argparse
import shutil
import subprocess
import sys
from typing import Optional


def _send_via_terminal_notifier(message: str, title: str, sound: Optional[str]) -> None:
    """Use terminal-notifier (brew install terminal-notifier) if available."""
    cmd = ["terminal-notifier", "-message", message, "-title", title]
    if sound:
        cmd += ["-sound", sound]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "terminal-notifier failed (no detail)")


def _send_via_osascript(message: str, title: str, sound: Optional[str]) -> None:
    """Fallback: osascript display notification (Script Editor in Notifications)."""
    if sound:
        script = (
            "on run argv\n"
            "  display notification (item 1 of argv) "
            "with title (item 2 of argv) sound name (item 3 of argv)\n"
            "end run"
        )
        args = [message, title, sound]
    else:
        script = (
            "on run argv\n"
            "  display notification (item 1 of argv) with title (item 2 of argv)\n"
            "end run"
        )
        args = [message, title]
    res = subprocess.run(["osascript", "-e", script, *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")


def send_desktop(message: str, title: str = "Argus", sound: Optional[str] = None) -> None:
    if shutil.which("terminal-notifier"):
        _send_via_terminal_notifier(message, title, sound)
    else:
        _send_via_osascript(message, title, sound)


def main() -> int:
    ap = argparse.ArgumentParser(description="Show a macOS desktop notification.")
    ap.add_argument("--title", default="Argus")
    ap.add_argument("--sound", default=None,
                    help='Optional sound name, e.g. "Glass", "Ping".')
    ap.add_argument("message", nargs="?", default="✅ Argus test: desktop notifications work.")
    args = ap.parse_args()
    try:
        send_desktop(args.message, title=args.title, sound=args.sound)
    except Exception as e:
        print(f"Desktop notification FAILED: {e}", file=sys.stderr)
        return 1
    print("Desktop notification shown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
