"""FocusMon Slack alert helper — thin wrapper around argus_common/notify_via_slack.py.

The webhook URL comes from the focusmon `.env` as SLACK_WEBHOOK_URL. While
that value is the placeholder REPLACE_ME / empty / unset, send_slack() prints
a notice and returns False rather than failing — that way callers can fire
unconditionally before the user has configured the webhook.

The shared notification primitive lives in
`/Users/amit/PROJ/ASHANBH/personal_agents/argus_common/notify_via_slack.py`. This
wrapper only adds the FocusMon-specific bits the argus core doesn't know
about: mention prefix (`<!here> <@U…>`) and the placeholder-aware skip.

CLI:
    poetry run python slack_alert.py "Fomi is not running right now"
    poetry run python slack_alert.py --no-mention "quiet test"
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_VALUES = {"", "REPLACE_ME", "PLACEHOLDER", "TODO"}

_ARGUS_DIR = os.environ.get(
    "ARGUS_DIR",
    os.path.expanduser("~/PROJ/ASHANBH/personal_agents/argus_common"),
)


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


def _ensure_argus_path() -> None:
    if _ARGUS_DIR not in sys.path:
        sys.path.insert(0, _ARGUS_DIR)


def send_slack(
    text: str,
    *,
    raise_on_error: bool = False,
    mention: bool = True,
) -> bool:
    """Post a message to the configured Slack webhook via argus.

    Args:
        text: Plain text message body. Slack mrkdwn is supported.
        raise_on_error: If True, re-raise transport errors instead of swallowing.
        mention: If True (default), prepend SLACK_MENTION_PREFIX so the message
            produces a real notification. Pass False for quiet messages.

    Returns:
        True if the webhook accepted the message, False if the webhook is not
        yet configured or the post failed (and raise_on_error is False).
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

    _ensure_argus_path()
    try:
        from notify_via_slack import send_slack as _argus_send_slack
    except ImportError as exc:
        msg = (
            f"[slack_alert] Could not import argus from {_ARGUS_DIR}: {exc}. "
            f"Check ARGUS_DIR or run `poetry install` so requests is available."
        )
        print(msg, file=sys.stderr)
        if raise_on_error:
            raise
        return False

    try:
        _argus_send_slack(text, webhook_url=url)
        return True
    except Exception as exc:
        print(f"[slack_alert] argus.send_slack failed: {exc}", file=sys.stderr)
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
