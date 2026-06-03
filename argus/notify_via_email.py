#!/usr/bin/env python3
"""
notify_via_email.py — send an email via SMTP.

Reads SMTP settings from the repo-root .env
(/Users/amit/PROJ/ASHANBH/personal_agents/.env):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_TO

Usage:
  poetry run python notify_via_email.py --subject "Alert" "body text"
  poetry run python notify_via_email.py            # sends a default test email

Importable:
  from notify_via_email import send_email
  send_email("Argus alert", "birthday job failed")
"""

import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, "..", ".env"))


def send_email(subject: str, body: str, to: str | None = None) -> str:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to = to or os.environ.get("SMTP_TO") or user
    if not all([host, user, password, to]):
        raise RuntimeError("Missing SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_TO in .env.")

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=context)
            s.login(user, password)
            s.send_message(msg)
    return to


def main() -> int:
    ap = argparse.ArgumentParser(description="Send an email via SMTP.")
    ap.add_argument("--subject", default="Argus test email")
    ap.add_argument("--to", default=None, help="Override recipient (defaults to SMTP_TO).")
    ap.add_argument("body", nargs="?",
                    default="✅ Argus test: email notifications are working.")
    args = ap.parse_args()
    try:
        to = send_email(args.subject, args.body, args.to)
    except Exception as e:
        print(f"Email send FAILED: {e}", file=sys.stderr)
        return 1
    print(f"Email sent to {to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
