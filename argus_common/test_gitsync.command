#!/bin/bash
# End-to-end test of the shanfomi gitsync LaunchAgent, including whether the
# SSH key is reachable from the launchd (not just interactive) context.
# Run:  bash ~/PROJ/ASHANBH/personal_agents/argus_common/test_gitsync.command
set +e

ARGUS=~/PROJ/ASHANBH/personal_agents/argus_common
PLIST="$ARGUS/launchd/ai.bittlebits.shanfomi.gitsync.plist"
LABEL=ai.bittlebits.shanfomi.gitsync
LA=~/Library/LaunchAgents/$LABEL.plist
OUT="$ARGUS/logs/gitsync.test.log"
mkdir -p "$ARGUS/logs"
exec > >(tee "$OUT") 2>&1

echo "==================== gitsync launchd test :: $(date) ===================="

echo; echo "--- 1. SSH key works in an interactive shell? ---"
ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 | head -3

echo; echo "--- 2. Install / reload the LaunchAgent ---"
mkdir -p ~/Library/LaunchAgents
ln -sf "$PLIST" "$LA"
launchctl bootout  gui/$(id -u)/$LABEL 2>/dev/null
launchctl bootstrap gui/$(id -u) "$LA" && echo "bootstrap OK" || echo "bootstrap FAILED"

echo; echo "--- 3. Kickstart — runs the job in the REAL launchd context ---"
launchctl kickstart -p gui/$(id -u)/$LABEL
sleep 7

echo; echo "--- 4. launchd service state (last exit code tells the story) ---"
launchctl print gui/$(id -u)/$LABEL 2>/dev/null | grep -iE 'state =|last exit code|pid =' | head

echo; echo "--- 5. sync log — commit/push result (and any SSH/auth error) ---"
tail -n 25 "$ARGUS/logs/gitsync.log" 2>&1

echo; echo "--- 6. launchd stdout/stderr ---"
tail -n 25 "$ARGUS/logs/gitsync.launchd.log" 2>&1

echo; echo "==================== done — results saved to $OUT ===================="
