#!/bin/bash
# Assemble a double-clickable FomiForMe.app from the SwiftPM build.
# Output: dist/FomiForMe.app  (menu-bar agent app, no Dock icon).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG="logs/make_app.log"
: > "$LOG"
exec > "$LOG" 2>&1
set -x

APP_NAME="FomiForMe"
BUNDLE_ID="ai.bittlebits.fomi4me"
APP="dist/$APP_NAME.app"

# 1. Build release binary.
( cd app && swift build -c release ) || { echo "BUILD_FAILED"; echo "=== DONE ==="; exit 1; }
BIN="app/.build/release/$APP_NAME"
[ -x "$BIN" ] || { echo "NO_BINARY at $BIN"; echo "=== DONE ==="; exit 1; }

# 2. Fresh .app skeleton.
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# 3. Executable.
cp "$BIN" "$APP/Contents/MacOS/$APP_NAME"
chmod +x "$APP/Contents/MacOS/$APP_NAME"

# 4. SwiftPM resource bundle (carries Rules/*.json so Bundle.module resolves).
#    NOTE: app/.build/release is a SYMLINK on macOS; use a glob (which follows
#    the symlink) rather than `find` (which won't descend a symlinked start
#    point without -L), or Contents/Resources ends up empty and rules won't load.
RESBUNDLE=$(ls -d app/.build/release/*_FomiCore.bundle 2>/dev/null | head -1)
if [ -n "$RESBUNDLE" ] && [ -e "$RESBUNDLE" ]; then
  cp -R "$RESBUNDLE" "$APP/Contents/Resources/"
  echo "Copied resource bundle: $RESBUNDLE"
else
  echo "WARN: FomiCore resource bundle not found — persona rules will fail to load"
fi

# 4b. Verify the bundle actually landed; abort loudly if not (rules are required).
if ! ls -d "$APP/Contents/Resources/"*_FomiCore.bundle >/dev/null 2>&1; then
  echo "ERROR: resource bundle missing from app — rules would fail at runtime"
  echo "=== DONE ==="
  exit 1
fi

# 5. Info.plist — LSUIElement makes it a menu-bar agent (no Dock icon).
#    NSAppleEventsUsageDescription is required because the app reads the active
#    browser tab's URL (metadata only) via Apple Events.
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>FomiForMe</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key>
  <string>FomiForMe reads the active browser tab's web address (not its content) to tell work from distraction.</string>
  <key>NSHumanReadableCopyright</key><string>BittleBits</string>
</dict>
</plist>
PLIST

# 6. Ad-hoc codesign so Gatekeeper launches it without a "damaged" warning.
codesign --force --deep --sign - "$APP" 2>/dev/null || echo "codesign skipped (non-fatal)"

echo "APP_BUILT at $(pwd)/$APP"
ls -la "$APP/Contents" "$APP/Contents/MacOS" "$APP/Contents/Resources"
echo "=== DONE ==="
