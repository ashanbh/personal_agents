#!/bin/bash
# Double-clickable launcher for the built FomiForMe menu-bar app.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
RUNLOG="logs/run.log"
: > "$RUNLOG"
exec > "$RUNLOG" 2>&1
set -x

BIN="app/.build/release/FomiForMe"
if [ ! -x "$BIN" ]; then echo "NO_BINARY"; echo "=== DONE ==="; exit 1; fi

pkill -x FomiForMe 2>/dev/null || true
sleep 1
nohup "$BIN" > logs/app.log 2>&1 &
sleep 6

if pgrep -x FomiForMe > /dev/null; then echo "APP_RUNNING"; else echo "APP_NOT_RUNNING"; fi
echo "--- app.log ---"
cat logs/app.log 2>/dev/null
echo "--- store dir ---"
ls -la "$HOME/Library/Application Support/FomiForMe/" 2>/dev/null || echo "NO_STORE_DIR_YET"
echo "=== DONE ==="
