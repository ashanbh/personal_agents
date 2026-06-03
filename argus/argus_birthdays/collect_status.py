#!/usr/bin/env python3
"""
collect_status.py — read-only health report for the birthday-message job.

Prints facts only; it makes NO decisions and sends NO notifications. The Argus
agent runs this, reads the report, and uses judgment to decide whether to alert.

Outputs: file presence, last run time + age, FAILED lines in the last 7 days,
the birthday launchd stderr, and a tail of run.log.

Usage:
  python3 collect_status.py
"""

import datetime as dt
import glob
import gzip
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))           # personal_agents
BIRTHDAYS = os.path.join(REPO, "birthdays")
B_CODE = os.path.join(BIRTHDAYS, "code")
B_DATA = os.path.join(BIRTHDAYS, "data")
B_LOGS = os.path.join(BIRTHDAYS, "logs")
RUN_LOG = os.path.join(B_LOGS, "run.log")
B_ARCHIVE = os.path.join(B_LOGS, "archive")
LD_ERR = os.path.join(B_LOGS, "launchd.err.log")

RECENT_DAYS = 7
HEADER_RE = re.compile(r"(?m)^(=====.*?=====)\s*$")


def parse_header_date(header: str):
    s = header.strip().strip("=").strip()
    s = re.sub(r"^(?:cron\s+)?run\s+", "", s).strip()
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    s2 = re.sub(r"\s+[A-Za-z]{2,5}\s+(\d{4})$", r" \1", s)
    s2 = " ".join(s2.split())
    for fmt in ("%a %b %d %H:%M:%S %Y", "%b %d %H:%M:%S %Y"):
        try:
            return dt.datetime.strptime(s2, fmt)
        except ValueError:
            continue
    return None


def run_blocks(text):
    parts = HEADER_RE.split(text)
    out = []
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((parse_header_date(header), header + body))
    return out


def gather_text():
    chunks = []
    if os.path.exists(RUN_LOG):
        chunks.append(open(RUN_LOG, encoding="utf-8", errors="replace").read())
    archives = sorted(glob.glob(os.path.join(B_ARCHIVE, "run-*.log.gz")))
    if archives and (dt.datetime.now().timestamp() - os.path.getmtime(archives[-1])) < 9 * 86400:
        try:
            chunks.append(gzip.open(archives[-1], "rt", encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    return "\n".join(chunks)


def main():
    now = dt.datetime.now()
    print(f"BIRTHDAY JOB STATUS  (generated {now:%Y-%m-%d %H:%M %Z})")
    print(f"repo: {REPO}")
    print("-" * 60)

    # files
    for label, path in {
        "sender": os.path.join(B_CODE, "send_birthday_messages.py"),
        "data CSV": os.path.join(B_DATA, "birthdays_clean.csv"),
        "wrapper": os.path.join(B_CODE, "birthday_cron.sh"),
    }.items():
        print(f"file {label:<9}: {'OK' if os.path.exists(path) else 'MISSING'}  ({path})")

    text = gather_text()
    blocks = run_blocks(text)
    dated = [d for d, _ in blocks if d]

    # last run
    if not os.path.exists(RUN_LOG):
        print("last run    : NO run.log FOUND")
    elif not dated:
        print("last run    : run.log present but no parseable run entries")
    else:
        latest = max(dated)
        age_h = (now - latest).total_seconds() / 3600
        print(f"last run    : {latest:%Y-%m-%d %H:%M}  ({age_h/24:.1f} days ago)")

    # failures in recent window
    cutoff = now - dt.timedelta(days=RECENT_DAYS)
    fails = []
    for when, body in blocks:
        if when is None or when >= cutoff:
            for line in body.splitlines():
                if (any(t in line for t in ("FAILED", "ERROR", "Traceback"))
                        or "error:" in line.lower()):
                    fails.append(line.strip())
    print(f"failures(<{RECENT_DAYS}d): {len(fails)}")
    for ln in fails[:8]:
        print(f"   • {ln}")
    if len(fails) > 8:
        print(f"   …and {len(fails) - 8} more")

    # launchd stderr
    if os.path.exists(LD_ERR) and os.path.getsize(LD_ERR) > 0:
        first = open(LD_ERR, encoding="utf-8", errors="replace").readline().strip()
        print(f"launchd.err : NON-EMPTY -> {first}")
    else:
        print("launchd.err : empty")

    # tail
    print("-" * 60)
    print("run.log tail (last 20 lines):")
    if os.path.exists(RUN_LOG):
        lines = open(RUN_LOG, encoding="utf-8", errors="replace").read().splitlines()
        for ln in lines[-20:]:
            print(f"  {ln}")
    else:
        print("  (no run.log)")


if __name__ == "__main__":
    main()
