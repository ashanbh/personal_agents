"""Python-native check for whether Fomi is actively monitoring.

The signal we want is the small "notch indicator" Fomi places at the top of the
screen during an active focus session — when that overlay is gone, Fomi isn't
actually doing anything, even if Fomi.app happens to be open.

We detect it by enumerating on-screen windows via Quartz (no screenshot, no LLM
interpretation). Any window owned by Fomi that is positioned in the top strip of
the screen and is small enough to be a HUD/notch overlay counts as "actively
monitoring".

Usage:

    # Production: detect, log to ~/PROJ/ASHANBH/personal_agents/focusmon/logs/<date>.log,
    # and send a Slack alert if not actively monitoring.
    poetry run python check_fomi.py

    # See every Fomi window with its bounds and which ones match the notch rule.
    # Run this WITH Fomi actively monitoring to confirm the thresholds, then
    # again WITHOUT an active session to see the difference.
    poetry run python check_fomi.py --inspect

    # Detect only — don't write to the log file or send a Slack alert.
    poetry run python check_fomi.py --no-log --no-slack

Tunable thresholds live in .env (NOTCH_* keys) or fall back to the defaults
below. The defaults are educated guesses for the notch-style overlay Fomi shows
on Apple Silicon MacBooks; if --inspect tells us the real bounds, edit .env to
match.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "PROJ/ASHANBH/personal_agents/focusmon/logs")))
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))

# Detection signal: Fomi places a full-screen transparent overlay window at a
# Window Server layer ABOVE the menu bar (which lives at layer 24) and renders
# the green-dot notch pill inside it. The overlay only exists during an active
# focus session, so its presence is the "actively monitoring" signal.
#
# Reference layer values on macOS:
#   0   = normal application windows
#   24  = menu bar
#   27  = where Fomi's notch overlay was observed
# A safe threshold is "strictly above the menu bar".
ACTIVE_LAYER_MIN = int(os.getenv("FOMI_ACTIVE_LAYER_MIN", "25"))

# Legacy thresholds for the older "small notch-shaped window" heuristic. Kept
# only so an older Fomi build that uses that pattern would still be detected.
NOTCH_Y_MAX = float(os.getenv("NOTCH_Y_MAX", "10"))
NOTCH_H_MAX = float(os.getenv("NOTCH_H_MAX", "60"))
NOTCH_W_MIN = float(os.getenv("NOTCH_W_MIN", "80"))
NOTCH_W_MAX = float(os.getenv("NOTCH_W_MAX", "800"))

# Names Quartz reports for the Fomi process. If pyobjc shows something different
# in --inspect mode, add it here.
FOMI_OWNER_NAMES = {"Fomi", "fomi", "Fomi Lab", "FomiLab"}


# ---------------------------------------------------------------------------
# Quartz import (macOS only)
# ---------------------------------------------------------------------------


def _import_quartz():
    try:
        from Quartz import (  # type: ignore
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionAll,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError as exc:
        print(
            "[check_fomi] pyobjc-framework-Quartz is required. From the src "
            "directory, run:\n    poetry install\n"
            f"Underlying error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return {
        "CGWindowListCopyWindowInfo": CGWindowListCopyWindowInfo,
        "kCGNullWindowID": kCGNullWindowID,
        "kCGWindowListExcludeDesktopElements": kCGWindowListExcludeDesktopElements,
        "kCGWindowListOptionAll": kCGWindowListOptionAll,
        "kCGWindowListOptionOnScreenOnly": kCGWindowListOptionOnScreenOnly,
    }


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _is_fomi(w: dict[str, Any]) -> bool:
    """Match Fomi by owner name (case-insensitive substring) OR bundle id hints."""
    owner = (w.get("kCGWindowOwnerName") or "").lower()
    if "fomi" in owner:
        return True
    if owner in {n.lower() for n in FOMI_OWNER_NAMES}:
        return True
    return False


def list_windows(*, include_offscreen: bool = False) -> list[dict[str, Any]]:
    """Return all windows. With include_offscreen=True, also lists windows that
    aren't currently rendered (off-screen, on other Spaces, system layers)."""
    q = _import_quartz()
    if include_offscreen:
        options = q["kCGWindowListOptionAll"]
    else:
        options = q["kCGWindowListOptionOnScreenOnly"] | q["kCGWindowListExcludeDesktopElements"]
    return q["CGWindowListCopyWindowInfo"](options, q["kCGNullWindowID"]) or []


def list_fomi_windows(*, include_offscreen: bool = False) -> list[dict[str, Any]]:
    """Return the window dicts owned by Fomi (on-screen by default)."""
    return [w for w in list_windows(include_offscreen=include_offscreen) if _is_fomi(w)]


def fomi_process_running() -> tuple[bool, str]:
    """Cheap fallback: is the Fomi process alive at all (via pgrep)?"""
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-lf", "-i", "fomi"],
            capture_output=True, text=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"pgrep failed: {exc}"
    if result.returncode == 0 and result.stdout.strip():
        first = result.stdout.strip().splitlines()[0]
        return True, f"pgrep found Fomi process: {first[:120]}"
    return False, "pgrep did not find any Fomi process"


def _bounds(w: dict[str, Any]) -> tuple[float, float, float, float]:
    b = w.get("kCGWindowBounds") or {}
    return (
        float(b.get("X", 0)),
        float(b.get("Y", 0)),
        float(b.get("Width", 0)),
        float(b.get("Height", 0)),
    )


def is_active_overlay(w: dict[str, Any]) -> bool:
    """Primary signal: a Fomi window on-screen at a layer above the menu bar.

    Fomi creates a full-screen transparent layer-27 window during active focus
    sessions and renders the green-dot pill inside it. When no session is
    active, this window does not exist.
    """
    if not w.get("kCGWindowIsOnscreen"):
        return False
    layer = w.get("kCGWindowLayer", 0)
    return layer >= ACTIVE_LAYER_MIN


def is_notch_indicator(w: dict[str, Any]) -> bool:
    """Legacy / fallback signal: small window near the top of the screen."""
    if not w.get("kCGWindowIsOnscreen"):
        return False
    _, y, width, height = _bounds(w)
    return (
        y <= NOTCH_Y_MAX
        and height <= NOTCH_H_MAX
        and NOTCH_W_MIN <= width <= NOTCH_W_MAX
    )


def _describe(w: dict[str, Any]) -> str:
    x, y, width, height = _bounds(w)
    return f"{int(width)}x{int(height)}@{int(x)},{int(y)} layer={w.get('kCGWindowLayer')}"


def detect() -> tuple[bool, bool, str]:
    """Return (actively_monitoring, focused, short_note).

    actively_monitoring=True means Fomi has an active session overlay.
    focused=False means the distraction splat is showing (2+ full-screen
    overlays on-screen simultaneously); the user is running but not focused.
    """
    wins = list_fomi_windows()
    if not wins:
        # No on-screen Fomi windows — could still mean the app is running but idle.
        proc_alive, _ = fomi_process_running()
        if proc_alive:
            return False, False, "Fomi process running but no on-screen windows (no active session)"
        return False, False, "Fomi not running"

    overlays = [w for w in wins if is_active_overlay(w)]
    if overlays:
        # Two or more full-screen overlays = distraction splat is on screen.
        focused = len(overlays) < 2
        layers = ", ".join(str(w.get("kCGWindowLayer")) for w in overlays)
        note = (
            f"distraction splat showing ({len(overlays)} overlays, layers {layers})"
            if not focused
            else f"active overlay present ({_describe(overlays[0])})"
        )
        return True, focused, note

    # Older Fomi builds may use a small notch-shaped window instead of a layered
    # full-screen overlay. Keep that path as a fallback.
    notch = next((w for w in wins if is_notch_indicator(w)), None)
    if notch is not None:
        return True, True, f"notch indicator window present ({_describe(notch)})"

    sizes = ", ".join(_describe(w) for w in wins)
    return False, False, f"Fomi open but no active overlay; on-screen windows: {sizes}"


# ---------------------------------------------------------------------------
# Inspect mode (for tuning thresholds)
# ---------------------------------------------------------------------------


def _dump_window(prefix: str, w: dict[str, Any]) -> None:
    x, y, width, height = _bounds(w)
    layer = w.get("kCGWindowLayer")
    alpha = w.get("kCGWindowAlpha")
    sharing = w.get("kCGWindowSharingState")
    on_screen = w.get("kCGWindowIsOnscreen")
    pid = w.get("kCGWindowOwnerPID")
    owner = w.get("kCGWindowOwnerName")
    title = w.get("kCGWindowName") or "(no title / hidden)"
    markers = []
    if is_active_overlay(w):
        markers.append("<<< ACTIVE OVERLAY")
    if is_notch_indicator(w):
        markers.append("<<< NOTCH FALLBACK")
    marker = "  " + "  ".join(markers) if markers else ""
    print(
        f"  {prefix}{int(width)}x{int(height)} @ ({int(x)},{int(y)})  "
        f"layer={layer}  alpha={alpha}  sharing={sharing}  onscreen={on_screen}  "
        f"pid={pid}  owner={owner!r}  title={title!r}{marker}"
    )


def inspect() -> int:
    print("=" * 70)
    print("Step 1: process check (pgrep -lf -i fomi)")
    print("=" * 70)
    proc_alive, proc_note = fomi_process_running()
    print(f"  Fomi process alive: {proc_alive}")
    print(f"  {proc_note}")
    print()

    print("=" * 70)
    print("Step 2: on-screen windows owned by Fomi")
    print(
        f"  Active overlay rule: on-screen AND layer >= {ACTIVE_LAYER_MIN}"
    )
    print(
        f"  Notch fallback: on-screen AND Y<={NOTCH_Y_MAX}, H<={NOTCH_H_MAX}, "
        f"W in [{NOTCH_W_MIN}, {NOTCH_W_MAX}]"
    )
    print("=" * 70)
    onscreen = list_fomi_windows(include_offscreen=False)
    print(f"  Found {len(onscreen)} on-screen Fomi window(s).")
    for i, w in enumerate(onscreen, 1):
        _dump_window(f"[{i}] ", w)
    print()

    print("=" * 70)
    print("Step 3: ALL windows owned by Fomi (incl. offscreen & system layers)")
    print("=" * 70)
    all_fomi = list_fomi_windows(include_offscreen=True)
    print(f"  Found {len(all_fomi)} Fomi window(s) total.")
    for i, w in enumerate(all_fomi, 1):
        _dump_window(f"[{i}] ", w)
    print()

    print("=" * 70)
    print("Step 4: any window owned by a process whose name contains 'fomi'")
    print("        (case-insensitive, includes ALL listing modes)")
    print("=" * 70)
    # In case Fomi's helper has a different process name (e.g. a XPC helper)
    all_wins = list_windows(include_offscreen=True)
    fomi_like = [
        w for w in all_wins
        if "fomi" in ((w.get("kCGWindowOwnerName") or "").lower())
    ]
    print(f"  Found {len(fomi_like)} window(s) with 'fomi' in owner name.")
    for i, w in enumerate(fomi_like, 1):
        _dump_window(f"[{i}] ", w)
    print()

    print("=" * 70)
    print("Step 5: top 20 windows by Y position (smallest Y = topmost)")
    print("        — the notch overlay would be Y near 0 if Quartz can see it")
    print("=" * 70)
    by_y = sorted(all_wins, key=lambda w: _bounds(w)[1])
    for i, w in enumerate(by_y[:20], 1):
        _dump_window(f"[{i}] ", w)
    print()

    actively, focused, note = detect()
    print(f"Final verdict from detect(): actively_monitoring={actively} focused={focused} ({note})")
    print()
    print("Interpretation guide:")
    print(" - If step 2 has zero windows AND step 4 has zero, Fomi's overlay is")
    print("   hidden from CGWindowListCopyWindowInfo entirely (likely")
    print("   kCGWindowSharingNone). Window-enumeration detection can't be used.")
    print(" - If step 4 finds a window that step 2 missed, just relax the")
    print("   filter in list_fomi_windows to use include_offscreen=True.")
    print(" - If only step 1 says Fomi is running, fallback to process-based")
    print("   detection (less precise — can't tell active session from app open).")
    return 0


# ---------------------------------------------------------------------------
# Production entry point
# ---------------------------------------------------------------------------


def _write_log(line: str, now: dt.datetime) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{now.date().isoformat()}.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return log_path


def _fire_slack(text: str) -> None:
    # Imported lazily so --inspect doesn't load .env Slack config.
    try:
        import slack_alert
    except ImportError as exc:
        print(f"[check_fomi] could not import slack_alert: {exc}", file=sys.stderr)
        return
    slack_alert.send_slack(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Dump every Fomi window with bounds and exit (use this to tune thresholds).",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Skip appending to the daily log file.",
    )
    parser.add_argument(
        "--no-slack",
        action="store_true",
        help="Skip firing a Slack alert even if Fomi is not actively monitoring.",
    )
    args = parser.parse_args(argv)

    if args.inspect:
        return inspect()

    active, focused, note = detect()
    now = dt.datetime.now(LOCAL_TZ)
    ts = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    if active:
        focused_val = "yes" if focused else "no"
        line = f"{ts} | running=yes | focused={focused_val} | note={note}"
    else:
        line = f"{ts} | running=no | note={note}"
    print(line)

    if not args.no_log:
        path = _write_log(line, now)
        print(f"appended to {path}", file=sys.stderr)

    if not active and not args.no_slack:
        _fire_slack(f"FocusMon: Fomi is NOT actively monitoring at {ts} — {note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
