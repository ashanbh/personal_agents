#!/bin/bash
# M1 build + test + launch, fully logged for remote verification.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
exec > logs/build.log 2>&1
set -x
date
sw_vers
xcode-select -p || echo "NO_XCODE_CLT"
swift --version

cd app || exit 1
swift build -c release || { echo "BUILD_FAILED"; exit 1; }
swift test || echo "SWIFT_TESTS_FAILED"
cd ..

python3 -m pytest tests/ -q -p no:cacheprovider || echo "PYTEST_UNAVAILABLE_OR_FAILED"

pkill -x FomiForMe 2>/dev/null
sleep 1
nohup ./app/.build/release/FomiForMe > logs/app.log 2>&1 &
sleep 8
if pgrep -x FomiForMe > /dev/null; then echo "APP_RUNNING"; else echo "APP_NOT_RUNNING"; fi
ls -la "$HOME/Library/Application Support/FomiForMe/" 2>/dev/null
echo "DONE_M1_DEMO"
