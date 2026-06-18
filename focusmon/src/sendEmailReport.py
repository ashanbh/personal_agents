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
# (~/PROJ/ASHANBH/personal_agents/argus_common/notify_via_email.py). This module keeps
# its existing public API — `send_email(to, subject, body, html=False, plain=None)`
# — and delegates to argus for the actual SMTP work. The argus location can be
# overridden via the ARGUS_DIR env var if the project moves.

_ARGUS_DIR = os.environ.get(
    "ARGUS_DIR",
    os.path.expanduser("~/PROJ/ASHANBH/personal_agents/argus_common"),
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
            f"argus_common/notify_via_email.py exists. Underlying error: {exc}"
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

    # HTML — SwiftBar-style card
    weekday_abbr = target.strftime("%a")  # e.g. "Tue"
    date_str = target.strftime("%b %-d")   # e.g. "Jun 16"

    def _bar_color(pct: int) -> str:
        if pct >= 75:
            return "#4a7c59"   # green
        elif pct >= 25:
            return "#c8a96e"   # tan / yellow
        else:
            return "#b85c5c"   # muted red

    BAR_MAX_PX = 180
    DOTS = "· " * 12          # placeholder for inactive-hour rows

    hour_rows = []
    for slot in s.slots:
        seq = getattr(slot, "check_sequence", [])
        if slot.status == "upcoming":
            hour_rows.append(
                f"<tr>"
                f"<td style='color:#cccccc;font-size:13px;width:44px;"
                f"padding:3px 10px 3px 0;text-align:right;white-space:nowrap;'>{slot.label}</td>"
                f"<td style='padding:3px 6px;width:{BAR_MAX_PX}px;vertical-align:middle;'>"
                f"<span style='color:#dddddd;font-size:10px;letter-spacing:2px;'>{DOTS}</span></td>"
                f"<td style='width:38px;'></td>"
                f"</tr>"
            )
            continue

        if slot.status in ("missing", "lunch"):
            label_color = "#aaaaaa"
            bar_html = (
                f"<span style='color:#dddddd;font-size:10px;letter-spacing:2px;'>{DOTS}</span>"
            )
            pct_html = "<span style='color:#aaaaaa;font-size:12px;'>—</span>"
        else:
            if seq:
                pct = round(100 * slot.checks_yes / slot.checks_total) if slot.checks_total else 0
            else:
                pct = 100 if slot.status == "running" else 0
            label_color = _bar_color(pct)
            filled_px = max(round(BAR_MAX_PX * pct / 100), 0)
            empty_px = BAR_MAX_PX - filled_px
            bar_cells = ""
            if filled_px:
                bar_cells += (
                    f"<td style='background:{label_color};width:{filled_px}px;"
                    f"height:16px;'></td>"
                )
            if empty_px:
                bar_cells += (
                    f"<td style='background:#e8e8e8;width:{empty_px}px;height:16px;'></td>"
                )
            bar_html = (
                f"<table cellspacing='0' cellpadding='0' "
                f"style='border-collapse:collapse;width:{BAR_MAX_PX}px;'>"
                f"<tr>{bar_cells}</tr></table>"
            )
            pct_html = (
                f"<span style='color:{label_color};font-weight:700;"
                f"font-size:13px;'>{pct}%</span>"
            )

        hour_rows.append(
            f"<tr>"
            f"<td style='color:{label_color};font-size:13px;font-weight:600;width:44px;"
            f"padding:3px 10px 3px 0;text-align:right;white-space:nowrap;'>{slot.label}</td>"
            f"<td style='padding:3px 6px;width:{BAR_MAX_PX}px;vertical-align:middle;'>"
            f"{bar_html}</td>"
            f"<td style='padding:3px 0 3px 4px;white-space:nowrap;'>{pct_html}</td>"
            f"</tr>"
        )

    summary_color = "#4a7c59" if s.compliance_pct >= 50 else "#c0392b"
    html = f"""\
<html><body style="margin:0;padding:24px;background:#f0f0f0;font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Helvetica,sans-serif;">
<div style="max-width:340px;background:#ffffff;border-radius:12px;padding:16px 20px;box-shadow:0 2px 10px rgba(0,0,0,0.10);">

  <!-- header -->
  <div style="color:#999999;font-size:12px;margin-bottom:6px;">
    FocusMon daily &middot; {weekday_abbr} {date_str}
  </div>

  <!-- summary headline -->
  <div style="color:{summary_color};font-size:17px;font-weight:700;margin-bottom:12px;">
    {s.running_n} of {s.total_completed} goal hrs focused ({s.compliance_pct}%)
  </div>

  <hr style="border:none;border-top:1px solid #eeeeee;margin:0 0 10px 0;">

  <!-- hour-by-hour chart -->
  <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
    {''.join(hour_rows)}
  </table>

</div>
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
