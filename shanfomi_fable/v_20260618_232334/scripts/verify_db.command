#!/bin/bash
# Confirms the running app is polling: dumps event counts + schema from the store.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
VLOG="logs/verify.log"
: > "$VLOG"
exec > "$VLOG" 2>&1
set -x

DB="$HOME/Library/Application Support/FomiForMe/fomi4me.sqlite"
echo "pgrep:"; pgrep -x FomiForMe || echo "NOT_RUNNING"
echo "--- tables ---"
sqlite3 "$DB" ".tables"
echo "--- event count ---"
sqlite3 "$DB" "SELECT COUNT(*) AS events FROM events;"
echo "--- by category ---"
sqlite3 "$DB" "SELECT category, COUNT(*) FROM events GROUP BY category;"
echo "--- last 5 events (ts, bundle, app, domain, category, tier) ---"
sqlite3 -header "$DB" "SELECT datetime(ts,'unixepoch','localtime') t, bundle_id, app_name, domain, category, tier FROM events ORDER BY ts DESC LIMIT 5;"
echo "--- PRIVACY AUDIT: private-* rows that leaked identifiers (must be 0) ---"
sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE category LIKE 'private-%' AND (bundle_id IS NOT NULL OR app_name IS NOT NULL OR domain IS NOT NULL);"
echo "=== DONE ==="
