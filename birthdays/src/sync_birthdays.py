#!/usr/bin/env python3
"""
sync_birthdays.py — pull the Birthdays tab from the Google Sheet and merge any
new/changed birthdays into data/birthdays.csv, then regenerate birthdays_clean.csv.

Deterministic, stdlib-only. Fetches the sheet's public CSV export (the sheet is
link-shared, so no auth needed).

Merge rules (conservative — never destructive):
  - Match rows by Name (case-insensitive, whitespace-trimmed).
  - For an existing person: update Birthday / Method / Phone Number ONLY when the
    sheet has a non-empty value that differs from the local one. A blank cell in
    the sheet never erases a local value.
  - A person in the sheet but not local is ADDED.
  - A person local but not in the sheet (e.g. the Amit/Mallika TEST rows) is KEPT
    untouched and never deleted.
  - Phone numbers are compared by digits only, so formatting differences alone
    don't count as a change.

Usage:
  python3 sync_birthdays.py            # apply changes (and regenerate clean file)
  python3 sync_birthdays.py --dry-run  # show what would change, write nothing
"""

import argparse
import csv
import io
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV = os.path.join(HERE, "..", "data", "birthdays.csv")
PREPROCESS = os.path.join(HERE, "preprocess.py")

SHEET_ID = os.environ.get("BIRTHDAYS_SHEET_ID", "1-hxmSnI8Fx18uX9P3bkr1xHxSwJhY6BIQ8h91HlUl8o")
GID = os.environ.get("BIRTHDAYS_SHEET_GID", "1258137395")  # the "Birthdays" tab
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

FIELDS = ["Name", "First Name", "Last Name", "Birthday", "Method", "Phone Number", "Template"]


def norm_name(s):
    return (s or "").strip().lower()


def clean_method(m):
    m = (m or "").strip().strip('"').strip()
    low = m.lower()
    if low == "imessage":
        return "iMessage"
    if low == "whatsapp":
        return "WhatsApp"
    if "family is fortune" in low:
        return "Family is Fortune"
    return m


def digits(p):
    return re.sub(r"\D", "", p or "")


def fetch_sheet_rows():
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text)))


def load_local():
    with open(LOCAL_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="Sync birthdays from the Google Sheet.")
    ap.add_argument("--dry-run", action="store_true", help="Show changes; write nothing.")
    args = ap.parse_args()

    try:
        sheet = fetch_sheet_rows()
    except Exception as e:
        print(f"ERROR fetching sheet: {e}", file=sys.stderr)
        return 1

    local = load_local()
    by_name = {norm_name(r.get("Name")): r for r in local}

    additions, updates = [], []

    for srow in sheet:
        name = (srow.get("Name") or "").strip()
        if not name:
            continue
        key = norm_name(name)
        s_first = (srow.get("First Name") or "").strip()
        s_last = (srow.get("Last Name") or "").strip()
        s_bday = (srow.get("Birthday") or "").strip()
        s_method = clean_method(srow.get("Method"))
        # The sheet's phone column is "Phone Number(s)" (may hold a comma-separated
        # list); older sheets used "Phone Number". Map either to the local column.
        s_phone = (srow.get("Phone Number(s)") or srow.get("Phone Number") or "").strip()
        s_template = (srow.get("Template") or "").strip()

        if key not in by_name:
            additions.append({
                "Name": name, "First Name": s_first, "Last Name": s_last,
                "Birthday": s_bday, "Method": s_method,
                "Phone Number": s_phone, "Template": s_template,
            })
            continue

        lrow = by_name[key]
        changed = []
        # Plain string fields: update when the sheet has a non-empty differing value.
        for label, col, val in (
            ("first name", "First Name", s_first),
            ("last name", "Last Name", s_last),
            ("birthday", "Birthday", s_bday),
            ("template", "Template", s_template),
        ):
            if val and val != (lrow.get(col) or "").strip():
                changed.append(f"{label} {lrow.get(col,'')!r}->{val!r}")
                lrow[col] = val
        # Method (normalized compare)
        if s_method and clean_method(lrow.get("Method")) != s_method:
            changed.append(f"method {lrow.get('Method','')!r}->{s_method!r}")
            lrow["Method"] = s_method
        # Phone (compare by digits)
        if s_phone and digits(s_phone) != digits(lrow.get("Phone Number")):
            changed.append(f"phone {lrow.get('Phone Number','')!r}->{s_phone!r}")
            lrow["Phone Number"] = s_phone
        if changed:
            updates.append((name, changed))

    # report
    print(f"Sheet rows: {len(sheet)}   Local rows: {len(local)}")
    print(f"Additions: {len(additions)}   Updates: {len(updates)}")
    for name, changed in updates:
        print(f"  ~ {name}: " + "; ".join(changed))
    for a in additions:
        print(f"  + {a['Name']}: {a['Birthday']} / {a['Method']} / {a['Phone Number']}")

    if not additions and not updates:
        print("Already in sync. Nothing to do.")
        return 0

    if args.dry_run:
        print("\n[dry-run] no files written.")
        return 0

    merged = local + additions
    with open(LOCAL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in merged:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"Wrote {LOCAL_CSV} ({len(merged)} rows).")

    # regenerate the clean file the sender uses
    res = subprocess.run([sys.executable, PREPROCESS])
    if res.returncode != 0:
        print("WARNING: preprocess.py failed; birthdays_clean.csv may be stale.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
