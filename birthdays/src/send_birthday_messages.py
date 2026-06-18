#!/usr/bin/env python3
"""
send_birthday_messages.py

Sends a "Happy Birthday, <name>!" message to people in birthdays.csv.

- Only rows whose Method is "iMessage" or "Whatsapp" are processed.
  ("Family is Fortune" rows and rows with a blank phone number are skipped.)
- iMessage rows are sent through the macOS Messages app (AppleScript).
- Whatsapp rows are sent through the WhatsApp desktop app via the
  whatsapp:// URL scheme, then a synthetic Return to hit Send.

SAFETY: by default this runs in DRY-RUN mode and sends nothing — it just
prints what it WOULD do. Add --send to actually transmit.

Requirements (one-time macOS setup):
  - Messages app signed in to iMessage.
  - WhatsApp desktop app installed and logged in.
  - For WhatsApp auto-send: System Settings > Privacy & Security >
    Accessibility must allow whoever runs this (Terminal, etc.) to send
    keystrokes. Without it the message is typed but not sent.

Setup (once, from the project root ~/Desktop/claudia/birthdays):
  poetry install            # creates the virtualenv

Usage (run from the code/ directory; by default only messages TODAY's birthdays):
  poetry run python send_birthday_messages.py                              # dry run, today
  poetry run python send_birthday_messages.py --send                       # send to today's birthdays
  poetry run python send_birthday_messages.py --csv ../data/birthdays_test.csv --send  # self-test (Amit)
  poetry run python send_birthday_messages.py --all                        # dry run, everyone
  poetry run python send_birthday_messages.py --all --send                 # send to everyone
  poetry run python send_birthday_messages.py --channel imessage --send    # only iMessage rows
"""

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "..", "data", "birthdays_clean.csv")

ALLOWED_METHODS = {"imessage", "whatsapp"}


def first_name(full: str) -> str:
    full = (full or "").strip()
    return full.split()[0] if full else full


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def imessage_address(phone: str) -> str:
    """+countrycode and digits, e.g. +12137840260."""
    d = digits_only(phone)
    return "+" + d if d else ""


def whatsapp_number(phone: str) -> str:
    """Digits incl. country code, no +, e.g. 919619710378."""
    return digits_only(phone)


def send_imessage(address: str, message: str) -> None:
    # Try the classic "buddy of service" form; if that errors (common on recent
    # macOS), fall back to "participant of account". Surface the real error.
    script = (
        'on run {addr, msg}\n'
        '  tell application "Messages"\n'
        '    try\n'
        '      set svc to 1st service whose service type = iMessage\n'
        '      send msg to buddy addr of svc\n'
        '    on error errMsg number errNum\n'
        '      set acct to 1st account whose service type = iMessage\n'
        '      send msg to participant addr of acct\n'
        '    end try\n'
        '  end tell\n'
        'end run'
    )
    res = subprocess.run(["osascript", "-e", script, address, message],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")


def send_group_imessage(addresses: list, message: str) -> None:
    """Send a single iMessage to a group chat with all given addresses."""
    # Build participant list and create/reuse a group chat, then send.
    # argv layout: addr1, addr2, ..., addrN, message
    build_parts = (
        'on run argv\n'
        '  set msg to last item of argv\n'
        '  tell application "Messages"\n'
        '    set acct to 1st account whose service type = iMessage\n'
        '    set parts to {}\n'
        '    repeat with i from 1 to (count of argv) - 1\n'
        '      set end of parts to participant (item i of argv) of acct\n'
        '    end repeat\n'
        '    set theChat to make new chat with properties {participants: parts}\n'
        '    send msg to theChat\n'
        '  end tell\n'
        'end run'
    )
    res = subprocess.run(["osascript", "-e", build_parts, *addresses, message],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")


def send_whatsapp(number: str, message: str, send_delay: float = 4.0) -> None:
    # Literal spaces/punctuation in the text param (WhatsApp desktop does not
    # decode %20, so we pass the message verbatim — subprocess list form means
    # no shell, so spaces are safe).
    url = f"whatsapp://send?phone={number}&text={message}"
    subprocess.run(["open", url], check=True)
    time.sleep(send_delay)
    press_return = (
        'tell application "WhatsApp" to activate\n'
        'delay 1\n'
        'tell application "System Events" to keystroke return'
    )
    res = subprocess.run(["osascript", "-e", press_return],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "osascript failed (no detail)")


def is_today(birthday: str) -> bool:
    """birthday is MM/DD; compare to today's month/day."""
    birthday = (birthday or "").strip()
    if not birthday:
        return False
    try:
        m, d = birthday.split("/")
        today = dt.date.today()
        return int(m) == today.month and int(d) == today.day
    except ValueError:
        return False


def load_rows(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_phone = (row.get("Phone Number") or "").strip()
            phones = [p.strip() for p in raw_phone.split(",") if p.strip()]
            yield {
                "name": (row.get("Name") or "").strip(),
                "birthday": (row.get("Birthday") or "").strip(),
                "method": (row.get("Method") or "").strip(),
                "phones": phones,
            }


def main() -> int:
    ap = argparse.ArgumentParser(description="Send birthday iMessages / WhatsApps.")
    ap.add_argument("--csv", default=DEFAULT_CSV, help="Path to birthdays.csv")
    ap.add_argument("--send", action="store_true",
                    help="Actually send. Without this flag it's a dry run.")
    ap.add_argument("--all", action="store_true",
                    help="Message everyone regardless of date. "
                         "Default behavior is to only message people whose birthday is TODAY.")
    ap.add_argument("--channel", choices=["imessage", "whatsapp", "all"],
                    default="all", help="Limit to one channel.")
    ap.add_argument("--delay", type=float, default=4.0,
                    help="Seconds to wait for WhatsApp to load before pressing Send.")
    args = ap.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    mode = "SEND" if args.send else "DRY-RUN"
    only_today = not args.all
    print(f"[{mode}] reading {csv_path}")
    if only_today:
        print(f"[{mode}] only messaging birthdays on {dt.date.today():%m/%d} "
              f"(use --all to override)")
    else:
        print(f"[{mode}] --all: messaging everyone regardless of date")
    print("-" * 60)

    sent = skipped = 0
    for row in load_rows(csv_path):
        method = row["method"].lower()
        name, phones = row["name"], row["phones"]

        if method not in ALLOWED_METHODS:
            skipped += 1
            continue
        if args.channel != "all" and method != args.channel:
            continue
        if only_today and not is_today(row["birthday"]):
            continue
        if not phones:
            print(f"  SKIP  {name:<20} ({row['method']}) — no phone number")
            skipped += 1
            continue

        message = f"Happy Birthday, {first_name(name)}!"

        if method == "imessage":
            addrs = [imessage_address(p) for p in phones]
            phones_str = ", ".join(addrs)
            if len(addrs) > 1:
                print(f"  iGRP  {name:<20} [{phones_str}] :: {message}")
            else:
                print(f"  iMSG  {name:<20} {addrs[0]:<16} :: {message}")
            if args.send:
                try:
                    if len(addrs) > 1:
                        send_group_imessage(addrs, message)
                    else:
                        send_imessage(addrs[0], message)
                    sent += 1
                except Exception as e:
                    print(f"        FAILED ({name}): {e}", file=sys.stderr)
        else:  # whatsapp
            num = whatsapp_number(phones[0])
            print(f"  WAPP  {name:<20} {num:<16} :: {message}")
            if args.send:
                try:
                    send_whatsapp(num, message, send_delay=args.delay)
                    sent += 1
                    time.sleep(2)  # let WhatsApp settle between sends
                except Exception as e:
                    print(f"        FAILED ({name}): {e}", file=sys.stderr)

    print("-" * 60)
    if args.send:
        print(f"Done. Sent {sent}, skipped {skipped}.")
    else:
        print(f"Dry run complete. Would send to the rows above. "
              f"Re-run with --send to actually send. (skipped {skipped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
