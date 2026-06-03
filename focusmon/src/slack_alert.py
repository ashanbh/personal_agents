"""Minimal Slack webhook helper for FocusMon real-time alerts.

The webhook URL lives in .env as SLACK_WEBHOOK_URL. While it's the placeholder
value (REPLACE_ME / empty / unset), send_slack() prints a notice and returns
False rather than failing — that way the hourly Fomi-check task can call it
unconditionally before the user has configured the webhook.

CLI usage:
    poetry run python slack_alert.py "Fomi is not running right now"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_VALUES = {"", "REPLACE_ME", "PLACEHOLDER", "TODO"}


def _webhook_url() -> str | None:
    raw = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
    if raw in PLACEHOLDER_VALUES:
        return None
    return raw


def _mention_prefix() -> str:
    """Optional prefix prepended to every alert (e.g. '<!here> <@U03B2APLGG2>').

    Configure via SLACK_MENTION_PREFIX in .env. Slack mention syntax for webhooks:
      <!here>          -> @here notification to online channel members
      <!channel>       -> @channel notification to all channel members
      <@U03B2APLGG2>   -> mentions a specific user by Slack user ID
    """
    return (os.getenv("SLACK_MENTION_PREFIX") or "").strip()


def send_slack(
    text: str,
    *,
    raise_on_error: bool = False,
    mention: bool = True,
) -> bool:
    """Post a message to the configured Slack webhook.

    Args:
        text: Plain text message body. Slack mrkdwn is supported.
        raise_on_error: If True, re-raise transport errors instead of swallowing.
        mention: If True (default), prepend SLACK_MENTION_PREFIX (e.g. @here + @user)
                 so the message produces a real notification. Pass False for quiet
                 messages like smoke tests.

    Returns:
        True if Slack returned 2xx, False if the webhook is not yet configured
        or if the post failed (and raise_on_error is False).
    """
    url = _webhook_url()
    if url is None:
        print(
            "[slack_alert] SLACK_WEBHOOK_URL not configured (still REPLACE_ME); "
            "skipping alert. Message was: " + text,
            file=sys.stderr,
        )
        return False

    if mention:
        prefix = _mention_prefix()
        if prefix:
            text = f"{prefix} {text}"

    payload = json.dumps({"text": text, "link_names": 1}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                body = resp.read().decode("utf-8", errors="replace")
                print(
                    f"[slack_alert] Slack responded {resp.status}: {body}",
                    file=sys.stderr,
                )
            return ok
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"[slack_alert] Webhook POST failed: {exc}", file=sys.stderr)
        if raise_on_error:
            raise
        return False


if __name__ == "__main__":
    args = list(sys.argv[1:])
    mention = True
    if "--no-mention" in args:
        mention = False
        args.remove("--no-mention")
    msg = " ".join(args) or "FocusMon test alert"
    ok = send_slack(msg, mention=mention)
    print("sent" if ok else "skipped or failed")
    sys.exit(0 if ok else 1)
