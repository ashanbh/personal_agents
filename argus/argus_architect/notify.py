#!/usr/bin/env python3
"""
notify.py — demo notifier for the focus_coach_native architect loop.

Stdlib-only (no venv, no requests/dotenv needed) so it runs from the build
sandbox or the host. Sends to Slack (incoming webhook) and Email (SMTP), reading
credentials from the repo-root .env:
  /Users/amit/PROJ/ASHANBH/personal_agents/.env
Keys used: SLACK_WEBHOOK_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_TO

This is intentionally separate from the generic argus/notify_via_*.py helpers:
it has zero third-party deps and a single "send a demo announcement" entrypoint.

Usage:
  python3 notify.py --subject "DEMO M0 ready" "body text..."
  python3 notify.py --subject "x" --channels slack "slack only"
  python3 notify.py --subject "x" --channels slack,email --html-file report.html "fallback"

Importable:
  from notify import send_demo
  send_demo("DEMO M0 ready", "body", html="<p>rich</p>")
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
# .env lives at repo root, two levels up: argus/argus_architect/ -> repo root
ENV_PATH = os.path.abspath(os.path.join(HERE, "..", "..", ".env"))


def load_env(path: str = ENV_PATH) -> dict:
    """Minimal .env parser (stdlib only)."""
    env: dict[str, str] = {}
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


def send_slack(text: str, env: dict) -> None:
    url = env.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL not set (repo .env).")
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", "replace").strip()
        if body != "ok":
            raise RuntimeError(f"Unexpected Slack response: {resp.status} {body!r}")


def send_email(subject: str, body: str, env: dict, html: Optional[str] = None) -> str:
    host = env.get("SMTP_HOST")
    port = int(env.get("SMTP_PORT", "587"))
    user = (env.get("SMTP_USER") or "").split(",")[0].strip()  # first token = auth login
    password = env.get("SMTP_PASSWORD")
    to = env.get("SMTP_TO") or user
    if not (host and user and password and to):
        raise RuntimeError("SMTP_HOST/USER/PASSWORD/TO not fully set (repo .env).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls(context=ctx)
        s.login(user, password)
        s.send_message(msg)
    return to


def send_demo(subject: str, body: str, channels=("slack", "email"),
              html: Optional[str] = None, env: Optional[dict] = None) -> dict:
    """Send a demo announcement. Returns {channel: 'ok' | 'error: ...'}."""
    env = env or load_env()
    results: dict[str, str] = {}
    if "slack" in channels:
        try:
            send_slack(f"*{subject}*\n{body}", env)
            results["slack"] = "ok"
        except Exception as e:  # noqa: BLE001
            results["slack"] = f"error: {e}"
    if "email" in channels:
        try:
            to = send_email(subject, body, env, html=html)
            results["email"] = f"ok -> {to}"
        except Exception as e:  # noqa: BLE001
            results["email"] = f"error: {e}"
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a demo announcement (Slack + Email).")
    ap.add_argument("body", help="Message body / plain-text fallback.")
    ap.add_argument("--subject", default="focus_coach_native — demo ready")
    ap.add_argument("--channels", default="slack,email",
                    help="Comma list: slack,email")
    ap.add_argument("--html-file", default=None, help="Optional HTML body file.")
    args = ap.parse_args()

    html = None
    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()

    channels = tuple(c.strip() for c in args.channels.split(",") if c.strip())
    results = send_demo(args.subject, args.body, channels=channels, html=html)
    for ch, status in results.items():
        print(f"{ch}: {status}")
    # Non-zero exit if any requested channel failed.
    return 0 if all(v.startswith("ok") for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
