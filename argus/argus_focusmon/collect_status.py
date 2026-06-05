#!/usr/bin/env python3
"""
collect_status.py — read-only health report for the FocusMon stack.

Prints facts only; makes NO decisions and sends NO notifications. The
fomi-coach-morning Argus agent runs this, reads the report, and uses judgment
to decide what to email the user.

Outputs:
  - Project file presence (logs/, messages/, src/, .env)
  - Last 5 days of compliance stats (from focusmon/src/log_reader.stats_for_date)
  - Hour-by-hour breakdown for today and yesterday
  - Recent message-archive filenames (last 8)
  - Tail of focusmon/logs/cron.log

Usage:
  python3 collect_status.py
"""

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))                  # personal_agents
FOCUSMON = os.path.join(REPO, "focusmon")
SRC = os.path.join(FOCUSMON, "src")
LOGS = os.path.join(FOCUSMON, "logs")
MESSAGES = os.path.join(FOCUSMON, "messages")
ENV_FILE = os.path.join(FOCUSMON, ".env")
CRON_LOG = os.path.join(LOGS, "cron.log")

# Make focusmon's src importable so we can reuse log_reader.
if SRC not in sys.path:
    sys.path.insert(0, SRC)

HISTORY_DAYS = 5


def _print_files() -> None:
    for label, path in {
        "src/":        SRC,
        "logs/":       LOGS,
        "messages/":   MESSAGES,
        ".env":        ENV_FILE,
        "log_reader":  os.path.join(SRC, "log_reader.py"),
        "send_email":  os.path.join(SRC, "sendEmailReport.py"),
        "cron.log":    CRON_LOG,
    }.items():
        present = "OK" if os.path.exists(path) else "MISSING"
        print(f"file {label:<11}: {present}  ({path})")


def _print_stats():
    """Pull compliance for the last HISTORY_DAYS local days via log_reader."""
    try:
        from log_reader import stats_for_date, LOCAL_TZ  # type: ignore
    except Exception as e:
        print(f"log_reader import FAILED: {e}")
        return []

    today = dt.datetime.now(LOCAL_TZ).date()
    rows = []
    for i in range(HISTORY_DAYS - 1, -1, -1):
        d = today - dt.timedelta(days=i)
        try:
            s = stats_for_date(d)
        except Exception as e:
            print(f"stats_for_date({d}) FAILED: {e}")
            continue
        rows.append({
            "date": str(d),
            "weekday": d.strftime("%A"),
            "compliance_pct": s.compliance_pct,
            "focused": s.running_n,
            "observed": s.total_completed,
            "slots": [
                {"hour": sl.hour, "label": sl.label, "status": sl.status}
                for sl in s.slots
            ],
        })
    return rows


def _print_recent_messages():
    if not os.path.isdir(MESSAGES):
        print("messages/   : (directory missing)")
        return
    files = sorted(
        (f for f in os.listdir(MESSAGES) if f.endswith(".md")),
        reverse=True,
    )
    print(f"messages    : {len(files)} archives total")
    for f in files[:8]:
        size = os.path.getsize(os.path.join(MESSAGES, f))
        print(f"   • {f}  ({size}b)")


def _print_cron_tail(n: int = 20) -> None:
    if not os.path.exists(CRON_LOG):
        print("cron.log    : (no cron.log)")
        return
    with open(CRON_LOG, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print(f"cron.log    : {len(lines)} total lines, last {n}:")
    for ln in lines[-n:]:
        print(f"  {ln.rstrip()}")


def _print_fomi(local_tz: str = "America/Los_Angeles") -> None:
    """Print last 5 days of Fomi DB summary + today's session goals."""
    try:
        import fomi_db  # type: ignore
    except Exception as e:
        print(f"fomi_db import FAILED: {e}")
        return
    tz_today = dt.datetime.now(dt.timezone.utc).astimezone().date()
    rows = []
    for i in range(4, -1, -1):
        d = tz_today - dt.timedelta(days=i)
        try:
            rows.append(fomi_db.daily_summary(d, local_tz=local_tz))
        except FileNotFoundError as e:
            print(f"  Fomi DB not accessible: {e}")
            return
        except Exception as e:
            print(f"  fomi_db.daily_summary({d}) FAILED: {e}")
    print("Fomi DB — last 5 days:")
    for r in rows:
        print(
            f"   {r['date']}: {r['sessions_total']} sessions "
            f"({r['sessions_completed']} done / {r['sessions_incomplete']} stopped early)  "
            f"{r['focused_minutes']}m focused, {r['total_distractions']} distractions  "
            f"first={r['first_session_start_local'] or '—'}"
        )
    print()
    # Today's session goals — useful context for the coach
    today_sessions = []
    try:
        today_sessions = fomi_db.sessions_for_date(tz_today, local_tz=local_tz)
    except Exception:
        pass
    if today_sessions:
        print(f"Today's session goals ({len(today_sessions)}):")
        for s in today_sessions:
            mins = s.focused_s // 60
            end = s.updated_local.strftime("%H:%M") if s.updated_local else "—"
            print(f"   {s.start_local.strftime('%H:%M')}→{end}  "
                  f"{s.status:>10}  focus={mins}m  d={s.distractions}  | {s.name!r}")
    print()
    print("--- Fomi JSON (for the agent to parse) ---")
    print(json.dumps(rows, indent=2))


def main() -> int:
    now = dt.datetime.now()
    print(f"FOCUSMON STATUS  (generated {now:%Y-%m-%d %H:%M %Z})")
    print(f"repo: {REPO}")
    print("-" * 70)

    _print_files()
    print("-" * 70)

    rows = _print_stats()
    if rows:
        print("compliance over last 5 days (notch detector):")
        for r in rows:
            print(
                f"   {r['date']} ({r['weekday'][:3]}): "
                f"{r['compliance_pct']:>3}%   {r['focused']}/{r['observed']} focused/observed"
            )
        print()
        print("--- notch JSON (for the agent to parse) ---")
        print(json.dumps(rows, indent=2))
    print("-" * 70)

    _print_fomi()
    print("-" * 70)

    _print_recent_messages()
    print("-" * 70)

    _print_cron_tail()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
