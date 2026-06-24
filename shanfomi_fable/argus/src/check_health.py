#!/usr/bin/env python3
"""
check_health.py — Argus health checks for FomiForMe (see argus/ARGUS.md).

Checks: app process alive, DB freshness, digest sent today, privacy invariant.
Prints a JSON report; exit 0 = healthy, 1 = problems found.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # shanfomi_fable root (argus/, data/, logs/ are shared here)


def _current_src() -> Path:
    """Locate the active version's src/. Code is versioned (v_YYYYMMDD_HHMMSS/);
    data/, argus/, logs/ stay shared at the repo root. Prefer the `current`
    symlink, else the newest v_* dir, else a flat src/ (pre-versioning layout)."""
    cur = REPO / "current" / "src"
    if cur.exists():
        return cur
    versions = sorted(REPO.glob("v_*/src"))
    if versions:
        return versions[-1]
    return REPO / "src"


sys.path.insert(0, str(_current_src()))

import fomi4me_db  # noqa: E402


def app_running() -> bool:
    return subprocess.run(["pgrep", "-x", "FomiForMe"],
                          capture_output=True).returncode == 0


def _snapshot_query(sql: str, params: tuple = ()):
    src_db = fomi4me_db.db_path()
    if not src_db.exists():
        return None
    tmp = Path(tempfile.mkdtemp(prefix="argus-fomi4me-"))
    try:
        for ext in ("", "-wal", "-shm"):
            s = src_db.parent / f"{src_db.name}{ext}"
            if s.exists():
                shutil.copy(s, tmp / f"{src_db.name}{ext}")
        conn = sqlite3.connect(str(tmp / src_db.name))
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def db_fresh(max_age_s: int = 600) -> tuple[bool, float | None]:
    rows = _snapshot_query("SELECT MAX(ts) FROM events")
    if not rows or rows[0][0] is None:
        return False, None
    age = time.time() - rows[0][0]
    return age <= max_age_s, round(age, 1)


def digest_sent_today() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    return (REPO / "data" / "egress" / f"{today}-digest.txt").exists()


def privacy_violations() -> int:
    rows = _snapshot_query(
        "SELECT COUNT(*) FROM events WHERE category LIKE 'private-%' "
        "AND (bundle_id IS NOT NULL OR app_name IS NOT NULL OR domain IS NOT NULL)"
    )
    return int(rows[0][0]) if rows else 0


def main() -> int:
    fresh, age = db_fresh()
    report = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "app_running": app_running(),
        "db_fresh": fresh,
        "db_age_s": age,
        "digest_sent_today": digest_sent_today(),
        "privacy_violations": privacy_violations(),
    }
    # Digest check only meaningful after 18:05 local.
    now = datetime.now()
    digest_due = now.hour > 18 or (now.hour == 18 and now.minute >= 5)
    problems = []
    if not report["app_running"]:
        problems.append("app not running")
    if not report["db_fresh"]:
        problems.append("db stale or missing")
    if digest_due and not report["digest_sent_today"]:
        problems.append("digest not sent")
    if report["privacy_violations"] > 0:
        problems.append("SEV1: privacy invariant violated")
    report["problems"] = problems

    print(json.dumps(report, indent=2))
    log = REPO / "argus" / "logs" / "health.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{report['checked_at']} {'OK' if not problems else '; '.join(problems)}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
