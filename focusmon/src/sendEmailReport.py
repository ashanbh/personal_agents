"""FocusMon email reporter (self-report).

Reads the hourly check log for a given date (default: today, local time) and
emails an HTML compliance summary to SMTP_TO (yourself). For the partner-facing
twice-daily accountability email, see attn_4Hourly.py.

Library entry points:
    send_email(to, subject, body, html=False)  -- generic SMTP send
    build_report(date)                         -- (subject, html, plain) for a given local date
    send_report(date=None, to=None)            -- end-to-end: read log, build, send

CLI usage:
    poetry run python sendEmailReport.py                # email today's report
    poetry run python sendEmailReport.py --date 2026-05-28
    poetry run python sendEmailReport.py --dry-run      # print, don't send
    poetry run python sendEmailReport.py --to a@x.com,b@x.com
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_cls, datetime

from dotenv import load_dotenv

from log_reader import (
    DayStats,
    LOCAL_TZ,
    LOG_DIR,  # re-exported for back-compat
    WORK_END_HOUR,
    WORK_START_HOUR,
    hour_label,
    stats_for_date,
)

load_dotenv()

SMTP_TO = os.getenv("SMTP_TO", "amit@bittlebits.ai")


# ---------------------------------------------------------------------------
# Argus-backed SMTP
# ---------------------------------------------------------------------------
#
# Notifications are sent via the shared argus helpers
# (~/PROJ/ASHANBH/personal_agents/argus/notify_via_email.py). This module keeps
# its existing public API — `send_email(to, subject, body, html=False, plain=None)`
# — and delegates to argus for the actual SMTP work. The argus location can be
# overridden via the ARGUS_DIR env var if the project moves.

_ARGUS_DIR = os.environ.get(
    "ARGUS_DIR",
    os.path.expanduser("~/PROJ/ASHANBH/personal_agents/argus"),
)


def _ensure_argus_path() -> None:
    if _ARGUS_DIR not in sys.path:
        sys.path.insert(0, _ARGUS_DIR)


def _strip_tags(html_text: str) -> str:
    """Crude HTML-to-plain fallback used only when html=True is passed without
    an explicit plain= alternative. Mail clients that can render HTML will see
    the HTML version; this just keeps text-only clients from getting a blob of
    markup."""
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n\n(This message is best viewed as HTML.)"


def send_email(
    to: list[str],
    subject: str,
    body: str,
    html: bool = False,
    plain: str | None = None,
) -> None:
    """Send an email to one or more recipients via the shared argus helper.

    Signature is kept backward-compatible:
      - html=False: `body` is plain text.
      - html=True : `body` is HTML; pass `plain=<text>` for a true plain
                    alternative, otherwise we synthesize one by stripping tags.
    """
    _ensure_argus_path()
    try:
        from notify_via_email import send_email as _argus_send_email
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import argus from {_ARGUS_DIR}. Check ARGUS_DIR or that "
            f"argus/notify_via_email.py exists. Underlying error: {exc}"
        ) from exc

    to_str = ", ".join(to)
    if html:
        plain_body = plain if plain is not None else _strip_tags(body)
        _argus_send_email(subject, plain_body, to=to_str, html=body)
    else:
        _argus_send_email(subject, body, to=to_str)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_report(target: date_cls | None = None) -> tuple[str, str, str]:
    """Return (subject, html_body, plain_body) for the given local date."""
    target = target or datetime.now(LOCAL_TZ).date()
    s = stats_for_date(target)
    weekday = target.strftime("%A")
    subject = (
        f"FocusMon | {weekday} {target.isoformat()} | "
        f"{s.running_n}/{s.total_completed} hours on Fomi"
    )

    # Plain text
    plain_lines = [
        f"FocusMon report for {weekday}, {target.isoformat()}",
        f"Work window: {hour_label(WORK_START_HOUR)}-{hour_label(WORK_END_HOUR)} ({LOCAL_TZ.key})",
        "",
        f"Running:     {s.running_n}",
        f"Not running: {s.not_running_n}",
        f"Unknown:     {s.unknown_n}",
        f"Missing:     {s.missing_n}  (Mac off / cron skipped)",
        f"Upcoming:    {s.upcoming_n}",
        "",
        f"Compliance:  {s.compliance_pct}% ({s.running_n} of {s.total_completed} completed checks)",
        "",
        "Hour-by-hour:",
    ]
    markers = {
        "running":     "[OK]   ",
        "not_running": "[OFF]  ",
        "unknown":     "[?]    ",
        "missing":     "[--]   ",
        "upcoming":    "[...]  ",
    }
    for slot in s.slots:
        plain_lines.append(f"  {markers[slot.status]} {slot.label:>5s}  {slot.note}")
    plain = "\n".join(plain_lines) + "\n"

    # HTML
    color = {
        "running":     "#1b8a3a",
        "not_running": "#c0392b",
        "unknown":     "#7f8c8d",
        "missing":     "#bdc3c7",
        "upcoming":    "#5dade2",
    }
    big_color = "#1b8a3a" if s.compliance_pct >= 70 else "#c0392b"
    rows = []
    for slot in s.slots:
        rows.append(
            f"<tr>"
            f"<td style='padding:4px 12px;'>{slot.label}</td>"
            f"<td style='padding:4px 12px;color:{color[slot.status]};font-weight:600;'>"
            f"{slot.status.replace('_', ' ')}</td>"
            f"<td style='padding:4px 12px;color:#555;'>{_html_escape(slot.note)}</td>"
            f"</tr>"
        )
    html = f"""\
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;color:#222;">
<h2 style="margin-bottom:4px;">FocusMon report</h2>
<p style="margin-top:0;color:#555;">{weekday}, {target.isoformat()} &middot; work window {hour_label(WORK_START_HOUR)}-{hour_label(WORK_END_HOUR)} {LOCAL_TZ.key}</p>

<div style="display:inline-block;background:#f4f6f8;padding:12px 18px;border-radius:8px;margin:8px 0;">
  <div style="font-size:32px;font-weight:700;color:{big_color};">{s.compliance_pct}%</div>
  <div style="color:#555;font-size:13px;">compliance &middot; {s.running_n} of {s.total_completed} completed checks showed Fomi running</div>
</div>

<p>
  Running: <b>{s.running_n}</b> &middot;
  Not running: <b>{s.not_running_n}</b> &middot;
  Unknown: <b>{s.unknown_n}</b> &middot;
  Missing: <b>{s.missing_n}</b> &middot;
  Upcoming: <b>{s.upcoming_n}</b>
</p>

<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;">
<thead><tr style="background:#eef0f2;">
<th style="padding:6px 12px;text-align:left;">Hour</th>
<th style="padding:6px 12px;text-align:left;">Status</th>
<th style="padding:6px 12px;text-align:left;">Note</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>

<p style="color:#888;font-size:11px;margin-top:18px;">
Missing hours typically mean the Mac was off / asleep when the hourly cron tried to fire.
</p>
</body></html>
"""
    return subject, html, plain


def send_report(target: date_cls | None = None, to: list[str] | None = None) -> None:
    subject, html, plain = build_report(target)
    recipients = to or [r.strip() for r in SMTP_TO.split(",") if r.strip()]
    send_email(recipients, subject, html, html=True, plain=plain)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send the FocusMon self-report by email.")
    p.add_argument("--date", help="Report date (YYYY-MM-DD, local time). Defaults to today.")
    p.add_argument("--to", help="Override recipient(s); comma-separated.")
    p.add_argument("--dry-run", action="store_true", help="Print the report instead of emailing.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    target = date_cls.fromisoformat(args.date) if args.date else datetime.now(LOCAL_TZ).date()
    subject, html, plain = build_report(target)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(plain)
        return 0

    recipients = (
        [r.strip() for r in args.to.split(",") if r.strip()]
        if args.to
        else [r.strip() for r in SMTP_TO.split(",") if r.strip()]
    )
    if not recipients:
        print("No recipients (set SMTP_TO in .env or pass --to).", file=sys.stderr)
        return 2

    send_email(recipients, subject, html, html=True)
    print(f"Sent: {subject} -> {', '.join(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
