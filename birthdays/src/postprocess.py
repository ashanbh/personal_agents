#!/usr/bin/env python3
"""
postprocess.py — weekly log rotation for ALL logs in the logs/ folder.

Once a week, on Sunday (the first day of the week), back up every *.log
file in logs/ to a timestamped gzip under logs/archive/, then truncate
each to zero lines so the new week starts clean. On any other day it does
nothing. Intended to be called daily (e.g. from birthday_cron.sh).

Safety: each archive is written and verified on disk before its source log
is truncated, so a failure never loses a log. Empty logs are skipped. The
archive/ subdirectory itself is never touched.

Usage:
  python3 postprocess.py            # rotate only if today is Sunday
  python3 postprocess.py --force    # rotate now regardless of day
  python3 postprocess.py --dry-run  # show what would happen, change nothing
"""

import argparse
import datetime as dt
import glob
import gzip
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGS_DIR = os.path.join(HERE, "..", "logs")


def rotate_one(path: str, archive_dir: str, stamp: str, dry_run: bool):
    """Back up + truncate a single log file. Returns a status string."""
    if os.path.getsize(path) == 0:
        return f"  skip (empty): {os.path.basename(path)}"

    stem = os.path.basename(path)
    if stem.endswith(".log"):
        stem = stem[:-4]
    archive_path = os.path.join(archive_dir, f"{stem}-{stamp}.log.gz")

    if dry_run:
        return (f"  [dry-run] {os.path.basename(path)} "
                f"({os.path.getsize(path)} bytes) -> {archive_path}")

    os.makedirs(archive_dir, exist_ok=True)
    with open(path, "rb") as src, gzip.open(archive_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    if not (os.path.exists(archive_path) and os.path.getsize(archive_path) > 0):
        return f"  ERROR: archive failed for {os.path.basename(path)} — left intact"

    open(path, "w").close()
    return f"  rotated: {os.path.basename(path)} -> {os.path.basename(archive_path)}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly (Sunday) backup + reset of all logs.")
    ap.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR)
    ap.add_argument("--force", action="store_true",
                    help="Rotate now regardless of the day of week.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would happen without changing anything.")
    args = ap.parse_args()

    today = dt.date.today()
    is_sunday = today.weekday() == 6  # Mon=0 .. Sun=6
    if not (is_sunday or args.force):
        print(f"{today:%Y-%m-%d} ({today:%A}) is not Sunday — nothing to do "
              f"(use --force to rotate anyway).")
        return 0

    logs_dir = os.path.abspath(args.logs_dir)
    archive_dir = os.path.join(logs_dir, "archive")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    # All *.log files directly in logs/ (archive/ is a subdir, so it's excluded).
    log_files = sorted(glob.glob(os.path.join(logs_dir, "*.log")))
    if not log_files:
        print(f"No *.log files found in {logs_dir}.")
        return 0

    print(f"Rotating {len(log_files)} log file(s) in {logs_dir}:")
    for path in log_files:
        print(rotate_one(path, archive_dir, stamp, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
