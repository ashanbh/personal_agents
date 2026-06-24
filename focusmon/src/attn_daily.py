"""Daily focus-goal check — runs at 3am, reviews the previous workday.

Sends one email to ACCOUNTABILITY_RECIPIENTS summarising whether yesterday hit
the focus goal (default: DAILY_FOCUS_GOAL_HOURS = 6 hours out of the 10am-7pm
work window).

An hour counts as "focused" if:
  - There is exactly one check and it was yes, OR
  - There are multiple checks and the majority (>50%) were yes.

Usage:
    poetry run python attn_daily.py               # yesterday's report (dry-run by default)
    poetry run python attn_daily.py --date 2026-05-29
    poetry run python attn_daily.py --live        # actually sends the email
    poetry run python attn_daily.py --to me@example.com --live
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_cls, datetime, timedelta

from dotenv import load_dotenv

from log_reader import (
    DayStats,
    LOCAL_TZ,
    stats_for_date,
)
from sendEmailReport import send_email
from attn_utils import (
    SUBJECT_NAME,
    ACCOUNTABILITY_RECIPIENTS,
    swiftbar_card_html,
    plain_bar,
    write_message_log,
)

load_dotenv()

DAILY_FOCUS_GOAL_HOURS = int(os.getenv("DAILY_FOCUS_GOAL_HOURS", "6"))


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def count_focused_hours(stats: DayStats) -> int:
    """Hours where the majority of checks (or the single check) showed Fomi running."""
    n = 0
    for s in stats.slots:
        if s.checks_total > 1:
            if s.checks_yes > s.checks_no:
                n += 1
        elif s.status == "running":
            n += 1
    return n


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def build_email(stats: DayStats, name: str = SUBJECT_NAME) -> tuple[str, str, str]:
    """Return (subject, html_body, plain_body)."""
    focused = count_focused_hours(stats)
    goal = DAILY_FOCUS_GOAL_HOURS
    goal_met = focused >= goal
    pct = round(100 * focused / goal) if goal else 0
    shortfall = max(0, goal - focused)
    weekday = stats.target.strftime("%A")

    if goal_met:
        emoji = "&#9989;"   # ✅
        subject = f"Daily goal met: {name} — {focused} focused hrs on {weekday}"
        headline = f"{name} hit the {goal}-hour goal."
        body_intro = (
            f"{focused} of {stats.total_completed} observed hours were focused "
            f"({pct}%) &mdash; at or above the {goal}-hour daily target. "
            f"Worth a quick high-five."
        )
        accent = "#1b8a3a"
    else:
        emoji = "&#128202;"  # 📊
        subject = f"Daily recap: {name} — {focused}/{goal} goal hrs on {weekday}"
        headline = f"{name} fell short of the daily goal."
        body_intro = (
            f"{focused} of {stats.total_completed} observed hours were focused "
            f"({pct}%). The target is {goal} hours &mdash; "
            f"{shortfall} hour{'s' if shortfall != 1 else ''} short."
        )
        accent = "#c0392b"

    extra_html = (
        f"<p style='font-size:14px;line-height:1.5;color:#333;margin:0 0 12px 0;'>{body_intro}</p>"
    )
    footer_html = (
        f"<p style='color:#aaaaaa;font-size:11px;margin:0;'>"
        f"You're receiving this because {name} set you up as an accountability partner. "
        f"To opt out, just ask {name}.</p>"
    )
    html = swiftbar_card_html(
        header=f"FocusMon daily &middot; {weekday} {stats.target.isoformat()}",
        headline=f"{emoji} {headline}",
        headline_color=accent,
        slots=stats.slots,
        extra_html=extra_html,
        footer_html=footer_html,
        card_width=480,
    )

    # Plain text
    plain_lines = [
        f"FocusMon daily -- {weekday} {stats.target.isoformat()}",
        "",
        headline,
        f"Focused: {focused} hrs  |  Goal: {goal} hrs  |  {pct}%",
        "",
        body_intro.replace("&mdash;", "--"),
        "",
        "Hour by hour:",
    ]
    for s in stats.slots:
        if s.status != "upcoming":
            plain_lines.append(f"  {s.label:<5} {plain_bar(s)}")
    plain_lines += ["", f"-- {name}'s focus monitor"]
    plain = "\n".join(plain_lines) + "\n"

    return subject, html, plain


# ---------------------------------------------------------------------------
# Terminal display (ANSI colours – dry-run only, not used in email/log)
# ---------------------------------------------------------------------------

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[32m"
_BGREEN = "\033[92m"  # bright green
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_WHITE  = "\033[97m"
_BG_GREEN = "\033[42m"
_BG_RED   = "\033[41m"


def _pct_color(pct_val: int) -> str:
    if pct_val >= 75:
        return _BGREEN
    if pct_val >= 40:
        return _YELLOW
    return _RED


def _colored_bar(s) -> str:
    """ANSI-coloured version of plain_bar for terminal output."""
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


def print_terminal_report(stats: DayStats, subject: str, plain: str,
                          recipients: str, focused: int, goal: int, pct: int,
                          goal_met: bool) -> None:
    weekday = stats.target.strftime("%A")

    header_color = _GREEN if goal_met else _RED
    pct_bg = _BG_GREEN if goal_met else _BG_RED
    headline = (
        f"{SUBJECT_NAME} hit the {goal}-hour goal." if goal_met
        else f"{SUBJECT_NAME} fell short of the daily goal."
    )

    print(f"{_CYAN}{_BOLD}FocusMon daily  ·  {weekday} {stats.target.isoformat()}{_RESET}")
    print(f"{_DIM}Recipients: {recipients}{_RESET}")
    print(f"{_DIM}Subject:    {subject}{_RESET}")
    print()
    print(f"{header_color}{_BOLD}{headline}{_RESET}")
    print()
    # Prominent summary line
    pct_display = f" {pct}% "
    print(
        f"  {_BOLD}Focused:{_RESET} {_WHITE}{_BOLD}{focused} hrs{_RESET}"
        f"  {_DIM}|{_RESET}"
        f"  {_BOLD}Goal:{_RESET} {goal} hrs"
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


def print_swiftbar_daily(stats: DayStats, focused: int, goal: int, pct: int, goal_met: bool) -> None:
    import os as _os
    weekday = stats.target.strftime("%a")
    color  = "#1b8a3a" if goal_met else "#c0392b"
    icon   = "✅" if goal_met else "📊"

    override_script = _os.path.expanduser(
        "~/PROJ/ASHANBH/personal_agents/swiftbar/focusmon_override.sh"
    )
    date_str = stats.target.isoformat()

    print(f"{icon} {focused}h / {goal}h  {pct}% | color={color} font=Menlo-Bold size=13")
    print("---")
    print(f"FocusMon daily · {weekday} {stats.target.isoformat()} | font=Menlo size=12 color=#888888")
    print(f"{focused} of {goal} goal hrs focused ({pct}%) | font=Menlo-Bold size=13 color={color}")
    print("---")

    for s in stats.slots:
        if s.status == "upcoming":
            continue
        seq = getattr(s, "check_sequence", [])
        if len(seq) > 1:
            bar = "".join("█" if r == "yes" else "░" for r in seq)
            pct_val = round(100 * s.checks_yes / s.checks_total) if s.checks_total else 0
        elif s.status == "running":
            bar, pct_val = "█", 100
        else:
            bar, pct_val = "░", 0

        if s.status in ("missing", "unknown"):
            row_color, pct_str = "#aaaaaa", "    "
        elif pct_val >= 75:
            row_color, pct_str = "#1b8a3a", f"{pct_val:>3}%"
        elif pct_val >= 40:
            row_color, pct_str = "#d68910", f"{pct_val:>3}%"
        else:
            row_color, pct_str = "#c0392b", f"{pct_val:>3}%"

        print(f"{s.label:<5} {bar} {pct_str} | font=Menlo size=12 color={row_color}")
        # Sub-menu: override options for this hour
        print(f"-- ✅ Mark {s.label} as focused | bash={override_script} param1={date_str} param2={s.hour} param3=yes terminal=false refresh=true")
        print(f"-- ❌ Mark {s.label} as not focused | bash={override_script} param1={date_str} param2={s.hour} param3=no terminal=false refresh=true")
        print(f"-- ↩ Clear override for {s.label} | bash={override_script} param1={date_str} param2={s.hour} param3=clear terminal=false refresh=true")

    print("---")
    print("Refresh | refresh=true")
    print("Open logs | bash=open param1=~/PROJ/ASHANBH/personal_agents/focusmon/messages/ terminal=false")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily focus-goal email (reviews yesterday).")
    p.add_argument("--date", help="Date to report on (YYYY-MM-DD). Defaults to today.")
    p.add_argument("--yesterday", action="store_true", help="Report on yesterday.")
    p.add_argument("--today", action="store_true", help="Report on today.")
    p.add_argument("--tomorrow", action="store_true", help="Report on tomorrow.")
    p.add_argument("--to", help="Override recipients; comma-separated.")
    p.add_argument("--live", action="store_true", help="Actually send the email (default is dry-run).")
    p.add_argument("--swiftbar", action="store_true", help="Output in SwiftBar plugin format.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    today = datetime.now(LOCAL_TZ).date()
    if args.date:
        target = date_cls.fromisoformat(args.date)
    elif args.yesterday:
        target = today - timedelta(days=1)
    elif args.today:
        target = today
    elif args.tomorrow:
        target = today + timedelta(days=1)
    else:
        target = today

    stats = stats_for_date(target)
    subject, html, plain = build_email(stats)
    focused = count_focused_hours(stats)
    goal_met = focused >= DAILY_FOCUS_GOAL_HOURS
    pct = round(100 * focused / DAILY_FOCUS_GOAL_HOURS) if DAILY_FOCUS_GOAL_HOURS else 0

    if args.swiftbar:
        print_swiftbar_daily(stats, focused, DAILY_FOCUS_GOAL_HOURS, pct, goal_met)
        return 0

    write_message_log(f"{target.isoformat()}-daily.md", subject, plain)

    if not args.live:
        print_terminal_report(
            stats, subject, plain,
            recipients=args.to or ACCOUNTABILITY_RECIPIENTS,
            focused=focused,
            goal=DAILY_FOCUS_GOAL_HOURS,
            pct=pct,
            goal_met=goal_met,
        )
        return 0

    recipients = [
        r.strip() for r in (args.to or ACCOUNTABILITY_RECIPIENTS).split(",") if r.strip()
    ]
    if not recipients:
        print("No ACCOUNTABILITY_RECIPIENTS configured. Set it in .env or pass --to.", file=sys.stderr)
        return 2

    send_email(recipients, subject, html, html=True, plain=plain)
    print(f"Sent: {subject} -> {', '.join(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
