#!/bin/bash
# Double-clickable build + test runner for FomiForMe (M1).
# Writes everything to logs/build.log so the result can be read back remotely.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG="logs/build.log"
: > "$LOG"
exec > "$LOG" 2>&1
set -x

echo "=== ENVIRONMENT ==="
date
sw_vers || true
xcode-select -p || echo "NO_XCODE_CLT"
swift --version || { echo "NO_SWIFT"; echo "=== DONE ==="; exit 1; }

echo "=== BUILD ==="
cd app || { echo "NO_APP_DIR"; echo "=== DONE ==="; exit 1; }
swift build -c release
BUILD_RC=$?
echo "BUILD_RC=$BUILD_RC"
if [ "$BUILD_RC" -ne 0 ]; then
  echo "BUILD_FAILED"
  echo "=== DONE ==="
  exit 1
fi

echo "=== SWIFT TEST ==="
swift test
echo "SWIFT_TEST_RC=$?"

echo "=== DONE ==="
