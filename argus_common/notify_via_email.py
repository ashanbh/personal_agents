#!/usr/bin/env python3
"""
notify_via_email.py — send an email via SMTP.

Reads SMTP settings from the repo-root .env
(/Users/amit/PROJ/ASHANBH/personal_agents/.env):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_TO

Usage:
  poetry run python notify_via_email.py --subject "Alert" "body text"
  poetry run python notify_via_email.py            # sends a default test email
  poetry run python notify_via_email.py --html-file report.html --subject "x" "fallback"

Importable:
  from notify_via_email import send_email
  send_email("Argus alert", "birthday job failed")
  send_email("FocusMon", "plain fallback", html="<p>rich</p>")  # multipart
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


def send_email(
    subject: str,
    body: str,
    to: str | None = None,
    html: str | None = None,
) -> str:
    """Send an email via SMTP.

    Args:
        subject: Email subject line.
        body: Plain-text body. Required (becomes the fallback for clients that
            cannot render HTML).
        to: Recipient(s). Single address or a comma-separated list. Defaults to
            SMTP_TO from .env. If the first comma-token is meant as the auth
            user only, pass `to=` explicitly.
        html: Optional HTML body. When provided, the email is sent as
            multipart/alternative with `body` as text/plain and `html` as
            text/html. Mail clients pick the richest part they support.

    Returns:
        The resolved recipient string.
    """
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    # SMTP_USER may legacy-include a comma list; first address is the auth login.
    user_raw = (os.environ.get("SMTP_USER") or "").split(",")[0].strip()
    password = os.environ.get("SMTP_PASSWORD")
    to = to or os.environ.get("SMTP_TO") or user_raw
    if not all([host, user_raw, password, to]):
        raise RuntimeError("Missing SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_TO in .env.")

    msg = EmailMessage()
    msg["From"] = user_raw
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    # sendmail() needs a list of recipient addresses, not the joined header.
    rcpts = [r.strip() for r in to.split(",") if r.strip()]

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as s:
            s.login(user_raw, password)
            s.send_message(msg, from_addr=user_raw, to_addrs=rcpts)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=context)
            s.login(user_raw, password)
            s.send_message(msg, from_addr=user_raw, to_addrs=rcpts)
    return to


def main() -> int:
    ap = argparse.ArgumentParser(description="Send an email via SMTP.")
    ap.add_argument("--subject", default="Argus test email")
    ap.add_argument("--to", default=None, help="Override recipient (defaults to SMTP_TO).")
    ap.add_argument(
        "--html-file",
        default=None,
        help="Path to an HTML file. When supplied, sent as multipart/alternative "
        "with the positional body as the plain-text fallback.",
    )
    ap.add_argument("body", nargs="?",
                    default="✅ Argus test: email notifications are working.")
    args = ap.parse_args()
    html_body = None
    if args.html_file:
        try:
            with open(args.html_file, encoding="utf-8") as f:
                html_body = f.read()
        except OSError as e:
            print(f"Could not read --html-file: {e}", file=sys.stderr)
            return 2
    try:
        to = send_email(args.subject, args.body, args.to, html=html_body)
    except Exception as e:
        print(f"Email send FAILED: {e}", file=sys.stderr)
        return 1
    print(f"Email sent to {to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
