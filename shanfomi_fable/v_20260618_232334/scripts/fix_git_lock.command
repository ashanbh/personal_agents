#!/bin/bash
# Safely clear a stale .git/index.lock: only removes it if no git process is running.
REPO="$HOME/PROJ/ASHANBH/personal_agents"
LOG="$REPO/shanfomi_fable/logs/git_lock.log"
mkdir -p "$(dirname "$LOG")"
: > "$LOG"
exec > "$LOG" 2>&1
set -x

LOCK="$REPO/.git/index.lock"
echo "--- git processes ---"
GITPROCS=$(pgrep -fl '[g]it' || true)
echo "${GITPROCS:-none}"

ls -la "$LOCK" 2>/dev/null || { echo "NO_LOCK"; echo "=== DONE ==="; exit 0; }

if [ -n "$GITPROCS" ]; then
  echo "GIT_RUNNING — not removing lock. Close the other git process first."
  echo "=== DONE ==="
  exit 1
fi

rm -f "$LOCK" && echo "LOCK_REMOVED"
echo "--- git status ---"
git -C "$REPO" status --short --branch
echo "=== DONE ==="
