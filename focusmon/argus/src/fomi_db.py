#!/usr/bin/env python3
"""
fomi_db.py — read-only access to Fomi's local SQLite history.

Fomi (macOS focus app, bundle id `ai.fomilab.app`) writes a row to a
Core-Data-backed SQLite at:

    ~/Library/Containers/ai.fomilab.app/Data/
        Library/Application Support/Fomi/Fomi.sqlite

…once a session ends (completed or stopped early). In-flight sessions are NOT
in the file; only finalised rows appear. We snapshot the .sqlite + WAL + SHM
into a tmp dir before opening so we can never corrupt Fomi's live data.

Library entry points:
    sessions_for_date(date)  -> list[FomiSession]
    sessions_since(when)     -> list[FomiSession]
    daily_summary(date)      -> dict (small, ready for the coach agent)

CLI:
    python3 fomi_db.py             # today's summary + sessions
    python3 fomi_db.py --date 2026-06-02
    python3 fomi_db.py --since 2026-05-30
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FOMI_DB = Path(os.path.expanduser(
    "~/Library/Containers/ai.fomilab.app/Data/"
    "Library/Application Support/Fomi/Fomi.sqlite"
))

# Core Data stores TIMESTAMP as seconds since 2001-01-01 UTC.
CD_EPOCH = 978307200
DEFAULT_TZ = "America/Los_Angeles"


@dataclass
class FomiSession:
    start_local: datetime          # ZSESSIONDATE
    updated_local: datetime | None  # ZUPDATEDAT — often a more honest "end" than start+run_s
    planned_s: int                  # ZSESSIONDURATION (typically 1500 = 25 min)
    focused_s: int                  # ZFOCUSDURATION
    ran_s: int                      # ZRUNDURATION (wall clock incl. paused time — be skeptical)
    distractions: int               # ZDISTRACTIONCOUNT
    distracted_s: int               # ZDISTRACTIONDURATION
    time_to_first_distraction_s: int  # ZTIMETOFIRSTDISTRACTION
    status: str                     # 'completed' | 'incomplete'
    name: str                       # ZSESSIONNAME — the goal the user typed

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_local"] = self.start_local.isoformat()
        d["updated_local"] = self.updated_local.isoformat() if self.updated_local else None
        return d


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _snapshot_db() -> Path:
    """Copy main + WAL + SHM into a fresh tmp dir, return the snapshot path."""
    if not FOMI_DB.exists():
        raise FileNotFoundError(f"Fomi DB not found at {FOMI_DB}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="argus-fomi-db-"))
    for ext in ("", "-wal", "-shm"):
        src = FOMI_DB.parent / f"{FOMI_DB.name}{ext}"
        if src.exists():
            shutil.copy(src, tmp_dir / f"{FOMI_DB.name}{ext}")
    return tmp_dir / FOMI_DB.name


def _to_local(z: float | None, tz: ZoneInfo) -> datetime | None:
    if z is None:
        return None
    return datetime.fromtimestamp(z + CD_EPOCH, tz=timezone.utc).astimezone(tz)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sessions_since(
    when: datetime | date_cls | None = None,
    local_tz: str = DEFAULT_TZ,
) -> list[FomiSession]:
    """All Fomi sessions with ZSESSIONDATE >= `when`, oldest-first.

    `when=None` returns every session in the DB.
    A bare `date` is treated as midnight local on that day.
    """
    tz = ZoneInfo(local_tz)
    if isinstance(when, date_cls) and not isinstance(when, datetime):
        when = datetime(when.year, when.month, when.day, tzinfo=tz)

    snap = _snapshot_db()
    try:
        conn = sqlite3.connect(str(snap))
        c = conn.cursor()
        c.execute("""
            SELECT ZSESSIONDATE, ZUPDATEDAT, ZSESSIONDURATION,
                   ZFOCUSDURATION, ZRUNDURATION, ZDISTRACTIONCOUNT,
                   ZDISTRACTIONDURATION, ZTIMETOFIRSTDISTRACTION,
                   ZSTATUS, ZSESSIONNAME
              FROM ZSESSIONRECORDENTITY
             ORDER BY ZSESSIONDATE
        """)
        rows: list[FomiSession] = []
        for sd, up, plan, focus, run, dc, dd, ttfd, status, name in c.fetchall():
            if sd is None:
                continue
            start = _to_local(sd, tz)
            if when and start < when:
                continue
            rows.append(FomiSession(
                start_local=start,
                updated_local=_to_local(up, tz),
                planned_s=int(plan or 0),
                focused_s=int(focus or 0),
                ran_s=int(run or 0),
                distractions=int(dc or 0),
                distracted_s=int(dd or 0),
                time_to_first_distraction_s=int(ttfd or 0),
                status=str(status or ""),
                name=str(name or ""),
            ))
        return rows
    finally:
        try:
            shutil.rmtree(snap.parent)
        except OSError:
            pass


def sessions_for_date(
    target: date_cls,
    local_tz: str = DEFAULT_TZ,
) -> list[FomiSession]:
    """Sessions whose start_local falls on `target`'s local date."""
    tz = ZoneInfo(local_tz)
    day_start = datetime(target.year, target.month, target.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    out = []
    for s in sessions_since(day_start, local_tz=local_tz):
        if s.start_local < day_end:
            out.append(s)
    return out


def daily_summary(
    target: date_cls,
    local_tz: str = DEFAULT_TZ,
) -> dict:
    """Compact summary the coach agent can read at a glance."""
    ss = sessions_for_date(target, local_tz=local_tz)
    focused_min = round(sum(s.focused_s for s in ss) / 60, 1)
    completed = sum(1 for s in ss if s.status == "completed")
    incomplete = sum(1 for s in ss if s.status == "incomplete")
    distractions_total = sum(s.distractions for s in ss)
    first = ss[0].start_local.strftime("%H:%M") if ss else None
    last_update = ss[-1].updated_local.strftime("%H:%M") if ss and ss[-1].updated_local else None
    return {
        "date": str(target),
        "sessions_total": len(ss),
        "sessions_completed": completed,
        "sessions_incomplete": incomplete,
        "focused_minutes": focused_min,
        "total_distractions": distractions_total,
        "first_session_start_local": first,
        "last_session_update_local": last_update,
        "session_goals": [s.name for s in ss],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read Fomi's session history.")
    p.add_argument("--date", help="Local YYYY-MM-DD to summarise. Defaults to today.")
    p.add_argument("--since", help="Local YYYY-MM-DD; list every session at/after this date.")
    p.add_argument("--tz", default=DEFAULT_TZ, help="IANA timezone (default America/Los_Angeles).")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human text.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    tz = ZoneInfo(args.tz)
    today = datetime.now(tz).date()

    if args.since:
        d = date_cls.fromisoformat(args.since)
        ss = sessions_since(d, local_tz=args.tz)
        if args.json:
            print(json.dumps([s.to_dict() for s in ss], indent=2))
            return 0
        print(f"{len(ss)} sessions since {d}:")
        for s in ss:
            mins = s.focused_s // 60
            print(f"  {s.start_local:%Y-%m-%d %H:%M}  ({s.status:>10})  "
                  f"focus={mins}m d={s.distractions}  | {s.name!r}")
        return 0

    target = date_cls.fromisoformat(args.date) if args.date else today
    summary = daily_summary(target, local_tz=args.tz)
    if args.json:
        print(json.dumps({
            "summary": summary,
            "sessions": [s.to_dict() for s in sessions_for_date(target, local_tz=args.tz)],
        }, indent=2))
        return 0

    print(f"Fomi summary for {target} ({args.tz}):")
    for k, v in summary.items():
        print(f"  {k:<28} {v}")
    print()
    print("Sessions:")
    for s in sessions_for_date(target, local_tz=args.tz):
        mins = s.focused_s // 60
        end_label = s.updated_local.strftime("%H:%M") if s.updated_local else "—"
        print(f"  {s.start_local.strftime('%H:%M')}→{end_label}  "
              f"{s.status:>10}  focus={mins}m  d={s.distractions}  | {s.name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
