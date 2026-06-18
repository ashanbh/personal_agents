# Birthdays Agent — Context

## Purpose
A personal "birthday concierge." Each day it figures out whose birthday it is
and **reminds _you_ (Amit)** to send them a message. It is **remind-only**: it
never messages the birthday people itself. Manual sending exists but is opt-in.

## Source of truth
A Google Sheet (tab **"Birthdays"**, `gid=1258137395`) in
`Holiday Cards & Birthdays`. It is link-shared, so it's pulled with no auth via
the public CSV export:
`https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>`
(`SHEET_ID`/`GID` overridable via `BIRTHDAYS_SHEET_ID`/`BIRTHDAYS_SHEET_GID`).

### Sheet / CSV columns
`Name, First Name, Last Name, Birthday, Method, Phone Number(s), Template`
- **Birthday**: `MM/DD`.
- **Method**: `iMessage`, `WhatsApp`, or `"Family is Fortune"` (the last is a
  do-not-message marker — those rows are skipped).
- **Phone Number(s)**: one or more numbers, comma-separated (e.g. a shared
  family line). Multiple iMessage numbers → a single **group** iMessage.
- **Template**: per-row message; default `Happy Birthday ${First Name}`.
  Placeholders: `${First Name}`, `${Last Name}`, `${Name}`.

Locally the phone column is stored as **`Phone Number`** (sync maps it).

## Daily pipeline (`code/birthday_cron.sh`, via launchd at 11:00 local)
1. **`sync_birthdays.py`** — pull the sheet, merge new/changed rows into
   `data/birthdays.csv` (never deletes local-only rows like the TEST rows; blank
   sheet cells never erase local values), then regenerate `data/birthdays_clean.csv`.
2. **`send_birthday_messages.py --remind`** — print today's reminder (who /
   channel / numbers / rendered template). Empty output ⇒ no birthdays today.
3. **Relay the reminder to Amit** across channels (see below). Recipients are
   never contacted.
4. **`postprocess.py`** — Sunday-only: gzip every `logs/*.log` into
   `logs/archive/` and truncate. No-op other days.

## Files (`code/`)
- `sync_birthdays.py` — sheet → `birthdays.csv` merge (stdlib only).
- `preprocess.py` — `birthdays.csv` → `birthdays_clean.csv`: trims, normalizes
  Method, E.164-normalizes each comma-separated number, zero-pads `MM/DD`.
- `send_birthday_messages.py` — date-filters (today by default; `--all`),
  renders templates, and either reminds (`--remind`) or sends (`--send`, manual).
  Multi-number iMessage → `send_group_imessage`; WhatsApp uses the first number.
- `postprocess.py` — weekly log rotation.
- `birthday_cron.sh` — the launchd wrapper (location-independent; `cd`s to its
  own dir). REMIND-ONLY.
- `com.claudia.birthday.plist` — launchd LaunchAgent, daily **11:00** local.

## Data (`data/`)
- `birthdays.csv` — editable source (human-readable numbers).
- `birthdays_clean.csv` — generated; what the sender reads (E.164).
- `backup/` — original raw import, contacts export (.vcf), phone-match log.
  (`data/` and `logs/` are gitignored — they hold personal numbers.)

## Notifications (handled by the shared `../argus/` layer)
The wrapper relays the reminder to **Amit only** via:
- **Slack** (`notify_via_slack.py`) — needs the argus poetry venv.
- **Email** (`notify_via_email.py`) — needs the argus poetry venv.
- **Desktop banner** (`notify_via_desktop.py`) — stdlib; terminal-notifier or osascript.
- **iMessage to self** (`notify_via_imessage.py`) — stdlib; `IMESSAGE_TO`.
- **WhatsApp to self** (`notify_via_whatsapp.py`) — stdlib; `WHATSAPP_TO`.
Secrets/targets live in the repo-root `.env`.

## Monitoring (Argus)
A Cowork scheduled task **`argus-birthday-monitor`** runs **Wednesdays 3 PM**.
It runs `../argus/argus_birthdays/collect_status.py`, applies judgment per
`../argus/argus_birthdays/monitor_prompt.md`, and alerts via Slack+email **only**
if something is broken (stale runs, send/sync failures, missing files).

## Guardrails / known issues
- **Never sends to recipients** in the scheduled flow — remind-only by design.
- The `.venv` folders are platform-specific and gitignored — must be rebuilt
  with `poetry install` on each machine (a Linux-built venv won't run on macOS).
- Slack/email run only inside the argus poetry venv (their deps need Python
  ≥3.10); the other notifiers run under the system `python3` (kept 3.9-safe).
- `send_group_imessage` has hit AppleScript error **-1700** on some macOS
  versions; doesn't affect remind-only operation, but verify before any manual
  multi-number `--send`.
- The project must live **outside** `~/Desktop`, `~/Documents`, `~/Downloads`
  (macOS TCC blocks launchd from reading scripts there).
