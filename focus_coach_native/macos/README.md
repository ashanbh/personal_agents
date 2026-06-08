# FocusCapture (native macOS)

The seed of the native app: capture the main display on a timer with
**ScreenCaptureKit**, then discard the frame. Pure Swift, no dependencies, tiny.
This grows into the shipped menu-bar app (capture → Core ML classifier → log).

Requires macOS 14+ (uses `SCScreenshotManager`).

## Run

```bash
cd ~/PROJ/ASHANBH/personal_agents/focus_coach_native/macos

swift run FocusCapture --once --keep      # one capture, save it, print the path
swift run FocusCapture                     # loop every 5s, discard each frame
swift run FocusCapture --interval 10 --keep --out ~/Desktop/frames
```

First run triggers the macOS **Screen Recording** permission prompt (attributed
to your terminal). Approve it in System Settings → Privacy & Security → Screen
Recording, then run again.

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--interval <sec>` | 5 | Seconds between captures |
| `--once` | off | Capture once and exit |
| `--keep` | off | Keep the PNG (default: delete immediately) |
| `--out <dir>` | temp dir | Where frames are written |

## Notes

- Default behavior **deletes each frame right after writing it** — the
  "nothing is stored" promise, enforced at the capture layer.
- This is a SwiftPM CLI for now so it's quick to iterate. The real app wraps the
  same capture in a menu-bar `NSApplication` with a login item; that needs an
  `Info.plist` with `NSScreenCaptureUsageDescription` and code signing.
- Next: feed the captured `CGImage` to a Core ML classifier instead of saving.
