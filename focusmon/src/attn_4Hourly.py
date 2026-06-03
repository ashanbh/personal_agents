"""Twice-daily accountability email.

This is the partner-facing email. It always fires (good days and bad), but the
tone scales with how the day is going:

    win        compliance_pct >= 90        celebrate, positive reinforcement
    on_track   threshold <= pct < 90       brief check-in, keep going
    struggling pct < threshold (default 70) honest ask for a check-in

Recipients come from ACCOUNTABILITY_RECIPIENTS in .env (comma-separated). The
sender authenticates as SMTP_USER (using only the first comma-token if a list).

Usage:
    poetry run python attn_4Hourly.py                # send now
    poetry run python attn_4Hourly.py --period midday
    poetry run python attn_4Hourly.py --dry-run
    poetry run python attn_4Hourly.py --force-tone struggling --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_cls, datetime
from pathlib import Path

from dotenv import load_dotenv

from log_reader import (
    DayStats,
    LOCAL_TZ,
    LOG_DIR,
    WORK_END_HOUR,
    WORK_START_HOUR,
    hour_label,
    stats_for_date,
)
from sendEmailReport import send_email
from attn_utils import (
    SUBJECT_NAME,
    ACCOUNTABILITY_RECIPIENTS,
    all_hours_table_html,
    plain_bar,
    write_message_log,
)

load_dotenv()
# Tone cutoffs (inclusive lower bound).
WIN_THRESHOLD = int(os.getenv("ACCOUNTABILITY_WIN_THRESHOLD", "90"))
OK_THRESHOLD = int(os.getenv("ACCOUNTABILITY_THRESHOLD_PCT", "70"))

# Focus goals per period.
MIDDAY_FOCUS_GOAL_HOURS = int(os.getenv("MIDDAY_FOCUS_GOAL_HOURS", "4"))
DAILY_FOCUS_GOAL_HOURS = int(os.getenv("DAILY_FOCUS_GOAL_HOURS", "6"))  # reused for evening


# ---------------------------------------------------------------------------
# Tone selection
# ---------------------------------------------------------------------------


def select_tone(goal_pct: int, has_data: bool) -> str:
    if not has_data:
        # No data yet — treat as on_track so partners get a benign first-check-in.
        return "on_track"
    if goal_pct >= WIN_THRESHOLD:
        return "win"
    if goal_pct >= OK_THRESHOLD:
        return "on_track"
    return "struggling"


# ---------------------------------------------------------------------------
# Period detection (midday vs evening) — for the subject line phrasing
# ---------------------------------------------------------------------------


def infer_period() -> str:
    """Return 'midday' or 'evening' based on the current local hour."""
    hour = datetime.now(LOCAL_TZ).hour
    return "evening" if hour >= 16 else "midday"


def period_phrase(period: str) -> str:
    """The adverbial phrase: 'this morning' / 'today'."""
    return "this morning" if period == "midday" else "today"


def period_word(period: str) -> str:
    """The noun form: 'morning' / 'day'."""
    return "morning" if period == "midday" else "day"


# ---------------------------------------------------------------------------
# Email content
# ---------------------------------------------------------------------------


def build_email(
    stats: DayStats,
    tone: str,
    period: str,
    name: str = SUBJECT_NAME,
) -> tuple[str, str, str]:
    """Return (subject, html_body, plain_body)."""
    when = period_phrase(period)        # "this morning" / "today"
    word = period_word(period)          # "morning" / "day"
    focused = stats.running_n
    counted = stats.total_completed
    weekday = stats.target.strftime("%A")
    period_goal = MIDDAY_FOCUS_GOAL_HOURS if period == "midday" else DAILY_FOCUS_GOAL_HOURS
    pct = min(100, round(100 * focused / period_goal)) if period_goal else 0

    # --- Subject + opener tuned to tone ---
    if tone == "win":
        subject = f"Focus win: {name} at {pct}% {when}"
        emoji = "&#127881;"  # party popper
        headline = f"Strong {word} for {name}."
        body_intro = (
            f"{focused} of {period_goal} goal hours focused &mdash; {pct}% of the {word}ly target. "
            f"Positive reinforcement is a real lever for ADHD &mdash; "
            f"if you have a sec, dropping {name} a quick high-five would land."
        )
        accent = "#1b8a3a"
        cta = "Send a kudos &raquo;"
    elif tone == "on_track":
        subject = f"Focus check-in: {name} at {pct}% {when}"
        emoji = "&#9989;"  # checkmark
        headline = f"{name} is holding steady {when}."
        body_intro = (
            f"{focused} of {period_goal} goal hours focused ({pct}% of target). "
            f"Sharing as a transparency ping &mdash; no action needed, but a "
            f'"keep going" text never hurts.'
        )
        accent = "#5dade2"
        cta = "Optional: send a quick \"nice\""
    else:  # struggling
        subject = f"Focus check-in: {name} at {pct}% {when} — could use a nudge"
        emoji = "&#129309;"  # handshake
        headline = f"{name} is having a tough {word}."
        body_intro = (
            f"Only {focused} of {period_goal} goal hours focused so far ({pct}% of target). "
            f"This is the kind of moment a friendly check-in can change the trajectory of."
        )
        accent = "#c0392b"
        cta = "Send a check-in"

    # --- Detail table: full hour-by-hour for all tones ---
    hours_table = all_hours_table_html(stats.slots)
    detail_html = ""
    if hours_table:
        detail_html = (
            f"<p style='margin-top:16px;color:#555;font-size:13px;font-weight:600;'>"
            f"Hour by hour &mdash; {focused} of {period_goal} goal hrs focused ({pct}%)</p>"
            + hours_table
        )

    html = f"""\
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;color:#222;max-width:560px;">
<p style="font-size:14px;color:#666;margin-bottom:2px;">FocusMon &middot; {weekday} {stats.target.isoformat()} ({period})</p>
<h2 style="margin:4px 0 8px 0;">{emoji} {headline}</h2>

<div style="display:inline-block;background:#f4f6f8;padding:10px 16px;border-radius:8px;margin:6px 0;">
  <span style="font-size:28px;font-weight:700;color:{accent};">{pct}%</span>
  <span style="color:#555;font-size:13px;margin-left:8px;">{focused} of {period_goal} goal hrs</span>
</div>

<p style="font-size:14px;line-height:1.5;">{body_intro}</p>

<p style="font-size:13px;color:#888;font-style:italic;margin-top:4px;">{cta}</p>

{detail_html}

<hr style="border:none;border-top:1px solid #eee;margin:18px 0 8px 0;">
<p style="color:#888;font-size:11px;">
You're on this list because {name} set you up as an accountability partner.
This is an automated message from {name}'s focus monitor. To opt out, just ask {name}.
</p>
</body></html>
"""

    plain_lines = [
        f"FocusMon -- {weekday} {stats.target.isoformat()} ({period})",
        "",
        headline.replace("&mdash;", "--"),
        f"Focused: {focused} of {period_goal} goal hrs  |  {pct}%",
        "",
        body_intro
            .replace("&mdash;", "--")
            .replace("&raquo;", ">>")
            .replace("&quot;", '"')
            .replace("\\\"", '"'),
        "",
    ]
    plain_lines.append("Hour by hour:")
    for s in stats.slots:
        if s.status != "upcoming":
            plain_lines.append(f"  {s.label:<5} {plain_bar(s)}")
    plain_lines.append("")
    plain_lines.append(f"-- {name}'s focus monitor")
    plain = "\n".join(plain_lines) + "\n"

    return subject, html, plain


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Terminal display (ANSI colours – dry-run only)
# ---------------------------------------------------------------------------

_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_GREEN   = "\033[32m"
_BGREEN  = "\033[92m"
_RED     = "\033[91m"
_YELLOW  = "\033[93m"
_CYAN    = "\033[96m"
_WHITE   = "\033[97m"
_BG_GREEN  = "\033[42m"
_BG_RED    = "\033[41m"
_BG_YELLOW = "\033[43m"


def _pct_color(pct_val: int) -> str:
    if pct_val >= 75:
        return _BGREEN
    if pct_val >= 40:
        return _YELLOW
    return _RED


def _colored_bar(s) -> str:
    seq = getattr(s, "check_sequence", [])
    if len(seq) > 1:
        bar = "".join(
            f"{_BGREEN}#{_RESET}" if r == "yes" else f"{_DIM}.{_RESET}"
            for r in seq
        )
        pct_val = round(100 * s.checks_yes / s.checks_total) if s.checks_total else 0
        color = _pct_color(pct_val)
        return f"[{bar}] {color}{_BOLD}{pct_val:>3}%{_RESET}"
    markers = {
        "running":     f"{_BGREEN}[ok ]{_RESET}",
        "not_running": f"{_DIM}[off]{_RESET}",
        "unknown":     f"{_YELLOW}[?  ]{_RESET}",
        "missing":     f"{_DIM}[off] (no data){_RESET}",
        "lunch":       f"{_DIM}[--]  lunch{_RESET}",
    }
    return markers.get(s.status, "     ")


def print_terminal_report(
    stats: DayStats, subject: str, tone: str, period: str,
    recipients: str, focused: int, period_goal: int, goal_pct: int,
) -> None:
    weekday = stats.target.strftime("%A")

    tone_color = {
        "win":        _BGREEN,
        "on_track":   _CYAN,
        "struggling": _RED,
    }.get(tone, _WHITE)
    pct_bg = {
        "win":        _BG_GREEN,
        "on_track":   _BG_YELLOW,
        "struggling": _BG_RED,
    }.get(tone, "")

    period_label = "midday" if period == "midday" else "evening"

    print(f"{_CYAN}{_BOLD}FocusMon  ·  {weekday} {stats.target.isoformat()} ({period_label}){_RESET}")
    print(f"{_DIM}Tone: {tone}  ·  Recipients: {recipients}{_RESET}")
    print(f"{_DIM}Subject: {subject}{_RESET}")
    print()

    pct_display = f" {goal_pct}% "
    print(
        f"  {_BOLD}Focused:{_RESET} {_WHITE}{_BOLD}{focused} hrs{_RESET}"
        f"  {_DIM}of{_RESET}  {period_goal} goal hrs"
        f"  {_DIM}|{_RESET}"
        f"  {pct_bg}{_BOLD}{_WHITE}{pct_display}{_RESET}"
    )
    print()
    print(f"{_BOLD}Hour by hour:{_RESET}")
    for s in stats.slots:
        if s.status != "upcoming":
            print(f"  {_DIM}{s.label:<5}{_RESET} {_colored_bar(s)}")
    print()
    print(f"{_DIM}-- {SUBJECT_NAME}'s focus monitor{_RESET}")


# ---------------------------------------------------------------------------
# SwiftBar output
# ---------------------------------------------------------------------------

_SB_COLORS = {
    "win":        "#1b8a3a",
    "on_track":   "#2471a3",
    "struggling": "#c0392b",
}
_SB_ICONS = {
    "win":        "✅",
    "on_track":   "📊",
    "struggling": "⚠️",
}


def _sb_bar(s) -> str:
    """Compact SwiftBar-safe bar for one slot."""
    seq = getattr(s, "check_sequence", [])
    if len(seq) > 1:
        bar = "".join("█" if r == "yes" else "░" for r in seq)
        pct_val = round(100 * s.checks_yes / s.checks_total) if s.checks_total else 0
        return bar, pct_val
    labels = {
        "running":     ("█", 100),
        "not_running": ("░", 0),
        "unknown":     ("?", -1),
        "missing":     ("-", -1),
        "lunch":       ("~", -1),
    }
    return labels.get(s.status, ("-", -1))


def print_swiftbar(stats, tone: str, period: str, focused: int,
                   period_goal: int, goal_pct: int) -> None:
    weekday = stats.target.strftime("%a")  # Mon, Tue …
    color = _SB_COLORS.get(tone, "#555555")
    icon  = _SB_ICONS.get(tone, "📊")

    # --- Menu bar title (one line) ---
    print(f"{icon} {focused}h / {period_goal}h  {goal_pct}% | color={color} font=Menlo-Bold size=13")
    print("---")

    # --- Subheader ---
    period_label = "morning" if period == "midday" else "day"
    print(f"FocusMon · {weekday} {stats.target.isoformat()} ({period_label}) | font=Menlo size=12 color=#888888")
    print(f"{focused} of {period_goal} goal hrs focused ({goal_pct}%) | font=Menlo-Bold size=13 color={color}")
    print("---")

    # --- Hour-by-hour ---
    for s in stats.slots:
        if s.status == "upcoming":
            continue
        result = _sb_bar(s)
        if isinstance(result, tuple):
            bar, pct_val = result
        else:
            bar, pct_val = result, -1

        if pct_val < 0:
            row_color = "#aaaaaa"
            pct_str = "    "
        elif pct_val >= 75:
            row_color = "#1b8a3a"
            pct_str = f"{pct_val:>3}%"
        elif pct_val >= 40:
            row_color = "#d68910"
            pct_str = f"{pct_val:>3}%"
        else:
            row_color = "#c0392b"
            pct_str = f"{pct_val:>3}%"

        print(f"{s.label:<5} {bar} {pct_str} | font=Menlo size=12 color={row_color}")

    print("---")
    print("Refresh | refresh=true")
    print(f"Open log | bash=open param1=~/PROJ/ASHANBH/personal_agents/focusmon/messages/ terminal=false")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Twice-daily accountability email.")
    p.add_argument("--date", help="Local date YYYY-MM-DD. Defaults to today.")
    p.add_argument(
        "--period",
        choices=["midday", "evening"],
        help="Force the period phrasing. Defaults to inferring from current hour.",
    )
    p.add_argument(
        "--force-tone",
        choices=["win", "on_track", "struggling"],
        help="Force a tone for testing instead of computing from stats.",
    )
    p.add_argument("--to", help="Override recipient(s); comma-separated.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the email instead of sending.",
    )
    p.add_argument(
        "--swiftbar",
        action="store_true",
        help="Output in SwiftBar plugin format (menu bar + dropdown).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    target = date_cls.fromisoformat(args.date) if args.date else datetime.now(LOCAL_TZ).date()
    stats = stats_for_date(target)

    period = args.period or infer_period()
    period_goal = MIDDAY_FOCUS_GOAL_HOURS if period == "midday" else DAILY_FOCUS_GOAL_HOURS
    goal_pct = min(100, round(100 * stats.running_n / period_goal)) if period_goal else 0
    tone = args.force_tone or select_tone(goal_pct, has_data=stats.total_completed > 0)
    subject, html, plain = build_email(stats, tone, period)

    if not args.swiftbar:
        write_message_log(f"{target.isoformat()}-{period}.md", subject, plain)

    if args.dry_run:
        print_terminal_report(
            stats, subject, tone, period,
            recipients=args.to or ACCOUNTABILITY_RECIPIENTS,
            focused=stats.running_n,
            period_goal=period_goal,
            goal_pct=goal_pct,
        )
        return 0

    if args.swiftbar:
        print_swiftbar(
            stats, tone, period,
            focused=stats.running_n,
            period_goal=period_goal,
            goal_pct=goal_pct,
        )
        return 0

    recipients = [
        r.strip()
        for r in (args.to or ACCOUNTABILITY_RECIPIENTS).split(",")
        if r.strip()
    ]
    if not recipients:
        print(
            "No ACCOUNTABILITY_RECIPIENTS configured. Set it in .env or pass --to.",
            file=sys.stderr,
        )
        return 2

    send_email(recipients, subject, html, html=True)
    print(f"Sent ({tone}, {period}): {subject} -> {', '.join(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
