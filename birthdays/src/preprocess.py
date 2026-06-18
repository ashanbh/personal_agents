#!/usr/bin/env python3
"""
preprocess.py

Cleans the raw birthdays CSV into a normalized file that send_birthday_messages.py
can consume reliably.

Cleaning rules:
  - Name:    trimmed of surrounding whitespace.
  - Method:  normalized to one of "iMessage", "WhatsApp", "Family is Fortune"
             (case-insensitive; stray wrapping quotes removed).
  - Phone:   normalized to E.164 ("+" + country code + digits), e.g. +19252195955.
             Blank stays blank.
  - Birthday: kept as MM/DD, zero-padded.

Usage:
  python3 preprocess.py                      # data/birthdays.csv -> data/birthdays_clean.csv
  python3 preprocess.py --output data/foo.csv
"""

import argparse
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IN = os.path.join(HERE, "..", "data", "birthdays.csv")
DEFAULT_OUT = os.path.join(HERE, "..", "data", "birthdays_clean.csv")

FIELDS = ["Name", "First Name", "Last Name", "Birthday", "Method", "Phone Number", "Template"]


def clean_name(name: str) -> str:
    return (name or "").strip()


def clean_method(method: str) -> str:
    m = (method or "").strip().strip('"').strip().lower()
    if m == "imessage":
        return "iMessage"
    if m == "whatsapp":
        return "WhatsApp"
    if "family is fortune" in m:
        return "Family is Fortune"
    return (method or "").strip().strip('"').strip()  # leave anything unexpected as-is


def to_e164(phone: str) -> str:
    """Normalize one or more comma-separated numbers to E.164, rejoined with ', '.

    A cell may contain multiple numbers (e.g. a shared family line), so each is
    normalized independently rather than fusing all digits into one number.
    """
    out = []
    for part in (phone or "").split(","):
        d = re.sub(r"\D", "", part)
        if d:
            out.append("+" + d)
    return ", ".join(out)


def clean_birthday(b: str) -> str:
    b = (b or "").strip()
    m = re.match(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$", b)
    if not m:
        return b
    return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean the birthdays CSV.")
    ap.add_argument("--input", default=DEFAULT_IN)
    ap.add_argument("--output", default=DEFAULT_OUT)
    args = ap.parse_args()

    # Absolute paths are used as-is; RELATIVE paths resolve against the agent
    # root (birthdays/), not the current dir — so `--output data/foo.csv` always
    # lands in birthdays/data/ no matter where you run the script from.
    agent_root = os.path.abspath(os.path.join(HERE, ".."))
    in_path = args.input if os.path.isabs(args.input) else os.path.join(agent_root, args.input)
    out_path = args.output if os.path.isabs(args.output) else os.path.join(agent_root, args.output)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cleaned, fixed = [], 0
    for r in rows:
        before = (r.get("Phone Number") or "").strip()
        row = {
            "Name": clean_name(r.get("Name")),
            "First Name": (r.get("First Name") or "").strip(),
            "Last Name": (r.get("Last Name") or "").strip(),
            "Birthday": clean_birthday(r.get("Birthday")),
            "Method": clean_method(r.get("Method")),
            "Phone Number": to_e164(r.get("Phone Number")),
            "Template": (r.get("Template") or "").strip(),
        }
        if before and before != row["Phone Number"]:
            fixed += 1
        cleaned.append(row)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(cleaned)

    print(f"Cleaned {len(rows)} rows -> {out_path}")
    print(f"  phone numbers reformatted: {fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
