#!/bin/bash
#
# birthday_cron.sh — wrapper invoked by launchd (or cron) each morning.
# REMIND-ONLY MODE: it does NOT send any iMessage/WhatsApp itself. It figures
# out whose birthday is today and reminds YOU via Slack + email (using the
# argus_common notifiers) so you can send the messages personally.
# (Manual sending is still available: `python3 send_birthday_messages.py --send`.)
#
# Scheduled via the launchd agent src/launchd/com.claudia.birthday.plist (11:00 AM).
#
# NOTE (macOS): the project must live OUTSIDE TCC-protected folders
# (~/Desktop, ~/Documents, ~/Downloads) or launchd can't even read this script
# ("Operation not permitted"). It lives under ~/PROJ/... which is fine.
#
cd "$(dirname "$0")" || exit 1

CSV="../data/birthdays_clean.csv"
LOG="../logs/run.log"
ARGUS="$(cd ../../argus_common && pwd)"
mkdir -p ../logs

echo "===== run $(date) =====" >> "$LOG"

# 1. Refresh birthdays from the Google Sheet (also regenerates the clean file).
#    If the fetch fails, we proceed with the last-known clean file.
/usr/bin/python3 sync_birthdays.py >> "$LOG" 2>&1

# 2. Build today's reminder (empty output = no birthdays today).
REMIND="$(/usr/bin/python3 send_birthday_messages.py --csv "$CSV" --remind 2>> "$LOG")"

# 3. Relay the reminder to Amit via Slack + email — never message recipients.
if [ -n "$REMIND" ]; then
    echo "$REMIND" >> "$LOG"
    # Slack/email need requests+dotenv (the argus_common poetry venv). Verify the venv
    # actually works (a Linux-built .venv won't run on macOS); else try poetry.
    export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
    if "$ARGUS/.venv/bin/python" -c "import requests, dotenv" >/dev/null 2>&1; then
        run_argus() { "$ARGUS/.venv/bin/python" "$@"; }
    elif command -v poetry >/dev/null 2>&1; then
        run_argus() { (cd "$ARGUS" && poetry run python "$@"); }
    else
        echo "WARNING: no working argus_common venv and poetry not found — Slack/email skipped. Run: cd $ARGUS && POETRY_VIRTUALENVS_IN_PROJECT=true poetry install" >> "$LOG"
        run_argus() { :; }
    fi
    run_argus "$ARGUS/notify_via_slack.py" "$REMIND" >> "$LOG" 2>&1
    run_argus "$ARGUS/notify_via_email.py" --subject "🎂 Birthday reminders today" "$REMIND" >> "$LOG" 2>&1
    # Native macOS banner (stdlib-only, no venv/credentials needed).
    /usr/bin/python3 "$ARGUS/notify_via_desktop.py" --title "🎂 Birthday reminders today" --sound Glass "$REMIND" >> "$LOG" 2>&1
    # Self-notifications: iMessage + WhatsApp to YOUR OWN number (IMESSAGE_TO /
    # WHATSAPP_TO in the repo .env). Recipients are never messaged by this job.
    /usr/bin/python3 "$ARGUS/notify_via_imessage.py" "$REMIND" >> "$LOG" 2>&1
    /usr/bin/python3 "$ARGUS/notify_via_whatsapp.py" "$REMIND" >> "$LOG" 2>&1
else
    echo "No birthdays today — no reminder needed." >> "$LOG"
fi

# 4. Weekly log rotation: backs up + clears all logs on Sundays, no-op otherwise.
/usr/bin/python3 postprocess.py >> "$LOG" 2>&1
