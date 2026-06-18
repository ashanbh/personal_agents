#!/usr/bin/env python3
"""
fomi4me_db.py — read-only access to FomiForMe's local SQLite store.

Drop-in successor to argus/argus_focusmon/fomi_db.py (which reads fomilab's
DB): same snapshot-before-open pattern, similar daily_summary() shape, so the
argus_focusmon coach prompt can swap readers with minimal change.

DB path: $FOMI4ME_DB, else ~/Library/Application Support/FomiForMe/fomi4me.sqlite

Library entry points:
    sessions_for_date(date) -> list[dict]
    daily_summary(date)     -> dict
    hourly_grid(date)       -> {hour: {"work_s": int, "nonwork_s": int}}

CLI:
    python3 fomi4me_db.py [--date YYYY-MM-DD] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Los_Angeles"
TICK_S = 5  # must match Poller.tickIntervalS

PRIVATE_CATEGORIES = {"private-work", "private-nonwork"}
WORKISH = {"work", "private-work"}
NONWORKISH = {"nonwork", "private-nonwork"}


def db_path() -> Path:
    p = os.environ.get(
        "FOMI4ME_DB",
        "~/Library/Application Support/FomiForMe/fomi4me.sqlite",
    )
    return Path(os.path.expanduser(p))


def _snapshot_db() -> Path:
    """Copy main + WAL + SHM into a tmp dir so we never touch the live DB."""
    src_db = db_path()
    if not src_db.exists():
        raise FileNotFoundError(f"FomiForMe DB not found at {src_db}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="fomi4me-db-"))
    for ext in ("", "-wal", "-shm"):
        src = src_db.parent / f"{src_db.name}{ext}"
        if src.exists():
            shutil.copy(src, tmp_dir / f"{src_db.name}{ext}")
    return tmp_dir / src_db.name


def _day_bounds(target: date_cls, tz_name: str) -> tuple[float, float]:
    tz = ZoneInfo(tz_name)
    start = datetime(target.year, target.month, target.day, tzinfo=tz)
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def _query(sql: str, params: tuple):
    snap = _snapshot_db()
    try:
        conn = sqlite3.connect(str(snap))
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    finally:
        shutil.rmtree(snap.parent, ignore_errors=True)


def sessions_for_date(target: date_cls, local_tz: str = DEFAULT_TZ) -> list[dict]:
    t0, t1 = _day_bounds(target, local_tz)
    rows = _query(
        "SELECT start_ts, end_ts, work_s, nonwork_s, close_reason "
        "FROM sessions WHERE start_ts >= ? AND start_ts < ? ORDER BY start_ts",
        (t0, t1),
    )
    tz = ZoneInfo(local_tz)
    return [
        {
            "start_local": datetime.fromtimestamp(s, tz).isoformat(),
            "end_local": datetime.fromtimestamp(e, tz).isoformat(),
            "work_s": int(w),
            "nonwork_s": int(n),
            "close_reason": r,
        }
        for s, e, w, n, r in rows
    ]


def _category_seconds(target: date_cls, local_tz: str) -> dict:
    t0, t1 = _day_bounds(target, local_tz)
    rows = _query(
        "SELECT category, COUNT(*) FROM events WHERE ts >= ? AND ts < ? GROUP BY category",
        (t0, t1),
    )
    return {cat: int(n) * TICK_S for cat, n in rows}


def drift_events(target: date_cls, local_tz: str = DEFAULT_TZ) -> int:
    """Number of work→nonwork transitions in the day's tick stream."""
    t0, t1 = _day_bounds(target, local_tz)
    rows = _query(
        "SELECT category FROM events WHERE ts >= ? AND ts < ? ORDER BY ts", (t0, t1)
    )
    drifts, prev_workish = 0, False
    for (cat,) in rows:
        workish = cat in WORKISH
        nonworkish = cat in NONWORKISH
        if prev_workish and nonworkish:
            drifts += 1
        if workish or nonworkish:
            prev_workish = workish
    return drifts


# Sanitization contract (DESIGN.md §3.5): partners see coarse CLASSES, never
# app names, domains, or titles. Unmapped → "other". Private buckets are
# excluded entirely here and contribute only to the non-work total.
_NONWORK_CLASS = {
    "youtube.com": "video", "netflix.com": "streaming", "hulu.com": "streaming",
    "disneyplus.com": "streaming", "twitch.tv": "streaming",
    "instagram.com": "social video", "tiktok.com": "social video",
    "facebook.com": "social", "x.com": "social", "twitter.com": "social",
    "reddit.com": "social", "9gag.com": "memes", "buzzfeed.com": "news/entertainment",
    "espn.com": "sports", "Music": "music", "Spotify": "music", "TV": "streaming",
    "News": "news/entertainment", "Photos": "photos",
}


def top_nonwork_classes(target: date_cls, local_tz: str = DEFAULT_TZ, k: int = 3) -> list[str]:
    """Top coarse non-work classes for the digest (no identifiers, ever)."""
    t0, t1 = _day_bounds(target, local_tz)
    rows = _query(
        "SELECT COALESCE(domain, app_name, 'other'), COUNT(*) FROM events "
        "WHERE ts >= ? AND ts < ? AND category = 'nonwork' "
        "GROUP BY 1 ORDER BY 2 DESC",
        (t0, t1),
    )
    counts: dict[str, int] = {}
    for name, n in rows:
        cls = _NONWORK_CLASS.get(name, "other")
        counts[cls] = counts.get(cls, 0) + int(n)
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [cls for cls, _ in ranked[:k]]


def hourly_grid(target: date_cls, local_tz: str = DEFAULT_TZ) -> dict:
    t0, t1 = _day_bounds(target, local_tz)
    rows = _query(
        "SELECT ts, category FROM events WHERE ts >= ? AND ts < ?", (t0, t1)
    )
    tz = ZoneInfo(local_tz)
    grid: dict[int, dict] = {}
    for ts, cat in rows:
        h = datetime.fromtimestamp(ts, tz).hour
        cell = grid.setdefault(h, {"work_s": 0, "nonwork_s": 0})
        if cat in WORKISH:
            cell["work_s"] += TICK_S
        elif cat in NONWORKISH:
            cell["nonwork_s"] += TICK_S
    return grid


def daily_summary(target: date_cls, local_tz: str = DEFAULT_TZ) -> dict:
    """Compact, digest-ready summary. Contains ONLY aggregates (DESIGN.md §3.5)."""
    cats = _category_seconds(target, local_tz)
    ss = sessions_for_date(target, local_tz)
    work_s = sum(v for k, v in cats.items() if k in WORKISH)
    nonwork_s = sum(v for k, v in cats.items() if k in NONWORKISH)
    best = max((s["work_s"] for s in ss), default=0)
    return {
        "date": str(target),
        "sessions_total": len(ss),
        "focused_minutes": round(work_s / 60, 1),
        "nonwork_minutes": round(nonwork_s / 60, 1),
        "best_session_minutes": round(best / 60, 1),
        "drift_events": drift_events(target, local_tz),
        "top_nonwork_classes": top_nonwork_classes(target, local_tz),
        "first_session_start_local": ss[0]["start_local"][11:16] if ss else None,
        "last_session_end_local": ss[-1]["end_local"][11:16] if ss else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read FomiForMe's local history.")
    p.add_argument("--date", help="Local YYYY-MM-DD (default today).")
    p.add_argument("--tz", default=DEFAULT_TZ)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    tz = ZoneInfo(args.tz)
    target = date_cls.fromisoformat(args.date) if args.date else datetime.now(tz).date()
    summary = daily_summary(target, args.tz)
    if args.json:
        print(json.dumps({"summary": summary,
                          "sessions": sessions_for_date(target, args.tz)}, indent=2))
        return 0
    print(f"FomiForMe summary for {target} ({args.tz}):")
    for k, v in summary.items():
        print(f"  {k:<28} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
