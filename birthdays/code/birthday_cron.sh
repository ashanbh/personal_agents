#!/bin/bash
#
# birthday_cron.sh — wrapper invoked by launchd (or cron) to send today's
# birthday messages. Location-independent: it cd's to its own dir and uses
# relative ../data and ../logs paths.
#
# Scheduled via the launchd agent code/com.claudia.birthday.plist (6:00 AM).
#
# NOTE (macOS): the project must live OUTSIDE TCC-protected folders
# (~/Desktop, ~/Documents, ~/Downloads) or launchd can't even read this script
# ("Operation not permitted"). It now lives under ~/PROJ/... which is fine.
# Sending also requires Automation (Messages/WhatsApp) + Accessibility grants.
#
cd "$(dirname "$0")" || exit 1

# Live mode: uses the real contact list. Only people whose birthday is TODAY
# get a message (the sender filters by date by default).
CSV="../data/birthdays_clean.csv"
LOG="../logs/cron.log"
mkdir -p ../logs

echo "===== cron run $(date) =====" >> "$LOG"
/usr/bin/python3 send_birthday_messages.py --csv "$CSV" --send >> "$LOG" 2>&1
