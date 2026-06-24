#!/bin/bash
# auto_git_sync.sh — unattended commit+push of ONE project subfolder.
#
# Wraps git_sync.py, which stages ONLY the named path (never `git add -A`) and
# no-ops when there's nothing to commit — so this is safe to run on a timer:
# it commits+pushes only when that folder actually changed, and pushes nothing
# when it's clean.
#
# Usage:
#   bash auto_git_sync.sh [TARGET_DIR]
# TARGET_DIR defaults to the shanfomi_fable project.
#
# The sync's OWN log is written under argus_common/logs/ (gitignored) — never
# inside the synced folder — so logging can't create a self-triggering change.
#
# git_sync.py is stdlib-only, so this runs under /usr/bin/python3 with no venv.
# Pushing uses your existing git credentials (SSH key in the keychain/agent);
# it fails with a clear message if none are available (e.g. a sandbox).

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HOME/PROJ/ASHANBH/personal_agents/shanfomi_fable}"

LOG_DIR="$HERE/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/gitsync.log"

MSG="$(basename "$TARGET"): auto-sync $(date '+%Y-%m-%d %H:%M:%S')"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') :: $TARGET ==="
  /usr/bin/python3 "$HERE/git_sync.py" "$TARGET" -m "$MSG"
  echo "exit=$?"
} >> "$LOG" 2>&1
