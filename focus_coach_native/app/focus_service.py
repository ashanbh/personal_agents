#!/usr/bin/env python3
"""Focus Coach Native — v0 activity service (prototype).

Pipeline, all local, nothing leaves the machine:

    screencapture (native)  ->  cheap OS context (frontmost app + window title)
                                 + optional YOLO object pass
                            ->  a pluggable Backend (see backends.py)
                            ->  detailed activity readout (JSONL)
                                 + focusmon-format log line
                            ->  delete the frame

Backends (best-available per platform; pick with --backend):
    heuristic  Tier 3, no model, cross-platform, runs today (DEFAULT)
    ollama     dev-only local vision model (prompt iteration)
    apple      Tier 1 macOS Foundation Models (native app; stub here)
    onnx       Tier 2 Windows bundled FastVLM via ONNX (stub here)

Two outputs are written:
  1. Detailed readout    -> <activity-dir>/<YYYY-MM-DD>.jsonl  (every capture)
  2. focusmon log line   -> <log-dir>/<YYYY-MM-DD>.log         (throttled)
     Same format check_fomi.py writes, so the FocusMon coach pipeline reads it
     unchanged:
        <YYYY-MM-DD HH:MM:SS TZ> | running=<yes|no|unknown> [| focused=<yes|no>] | note=<text>

Throwaway-quality prototype. Capture is the native `screencapture` CLI; a real
menu-bar / tray app replaces this capture layer later.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

import backends as be

# ---------------------------------------------------------------------------
# Config / defaults
# ---------------------------------------------------------------------------

HOME = Path.home()
DEFAULT_LOG_DIR = HOME / "PROJ/ASHANBH/personal_agents/focusmon/logs"
DEFAULT_ACTIVITY_DIR = HOME / "PROJ/ASHANBH/personal_agents/focus_coach_native/data/activity"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "moondream"
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))


# ---------------------------------------------------------------------------
# Capture (native) + change detection
# ---------------------------------------------------------------------------

def capture_frame(path: Path) -> bool:
    """Grab the current screen silently to `path`. Returns True on success.

    macOS: `screencapture`. (Windows port: swap for a mss/PIL grab.)
    """
    try:
        subprocess.run(["screencapture", "-x", "-t", "png", str(path)],
                       check=True, capture_output=True, timeout=15)
        return path.exists() and path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"[capture] screencapture failed: {exc}", file=sys.stderr)
        return False


def avg_hash(path: Path) -> int:
    with Image.open(path) as im:
        pixels = list(im.convert("L").resize((8, 8)).tobytes())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            bits |= (1 << i)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Cheap OS context (frontmost app + window title). macOS via osascript.
# ---------------------------------------------------------------------------

def frontmost_app() -> str:
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to name of first process whose frontmost is true'],
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return ""


def frontmost_window_title() -> str:
    """Best-effort title of the frontmost window (needs Accessibility perm)."""
    script = (
        'tell application "System Events"\n'
        ' set p to first process whose frontmost is true\n'
        ' try\n'
        '  return name of front window of p\n'
        ' on error\n'
        '  return ""\n'
        ' end try\n'
        'end tell')
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Optional YOLO object pass
# ---------------------------------------------------------------------------

class Yolo:
    def __init__(self, model_name: str = "yolov8n.pt"):
        from ultralytics import YOLO
        self.model = YOLO(model_name)

    def detect(self, path: Path) -> list[str]:
        try:
            res = self.model(str(path), verbose=False)
            names = set()
            for r in res:
                for c in r.boxes.cls.tolist():
                    names.add(r.names[int(c)])
            return sorted(names)
        except Exception as exc:
            print(f"[yolo] detection failed: {exc}", file=sys.stderr)
            return []


# ---------------------------------------------------------------------------
# Map readout -> focusmon log line
# ---------------------------------------------------------------------------

def sanitize_note(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ").strip()


def focusmon_line(readout: dict, now: dt.datetime) -> str:
    ts = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    cat = readout.get("category", "unknown")
    note = sanitize_note(
        f"{readout.get('activity','')}: {readout.get('summary','')}".strip(": ").strip()
    )[:160] or "no note"
    if cat == "working":
        focused = "yes" if readout.get("focused", True) else "no"
        return f"{ts} | running=yes | focused={focused} | note={note}"
    if cat == "not_working":
        return f"{ts} | running=no | note={note}"
    return f"{ts} | running=unknown | note={note}"


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def append_jsonl(activity_dir: Path, now: dt.datetime, record: dict) -> None:
    activity_dir.mkdir(parents=True, exist_ok=True)
    with (activity_dir / f"{now.date().isoformat()}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_log(log_dir: Path, now: dt.datetime, line: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{now.date().isoformat()}.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def preflight_ollama(base_url: str, model: str) -> None:
    import requests
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        r.raise_for_status()
    except Exception:
        sys.exit(f"ERROR: Ollama not reachable at {base_url}. Start `ollama serve`.")
    models = [m.get("name", "").split(":")[0] for m in r.json().get("models", [])]
    if model.split(":")[0] not in models:
        sys.exit(f"ERROR: model '{model}' not pulled. Run `ollama pull {model}`.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args) -> int:
    if args.backend == "ollama" and not args.dry_run:
        preflight_ollama(args.ollama_url, args.model)

    backend = be.get_backend(args.backend, ollama_url=args.ollama_url, model=args.model)

    yolo = None
    if args.yolo:
        try:
            print("[init] loading YOLO (yolov8n)...", file=sys.stderr)
            yolo = Yolo()
        except Exception as exc:
            print(f"[init] YOLO unavailable ({exc}); continuing without it.", file=sys.stderr)

    log_dir = Path(args.log_dir).expanduser()
    activity_dir = Path(args.activity_dir).expanduser()
    last_hash = None
    last_readout = None
    last_log_write = 0.0
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    print(f"[run] backend={args.backend} interval={args.interval}s "
          f"log-interval={args.log_interval}s yolo={'on' if yolo else 'off'}. Ctrl-C to stop.",
          file=sys.stderr)

    while not stop["flag"]:
        cycle_start = time.time()
        now = dt.datetime.now(LOCAL_TZ)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            frame = Path(tf.name)
        try:
            if not capture_frame(frame):
                readout = be._empty_readout(activity="capture_failed")
                readout["frontmost_app"] = ""
                readout["yolo"] = []
            else:
                h = avg_hash(frame)
                unchanged = last_hash is not None and hamming(h, last_hash) <= 2
                last_hash = h
                app = frontmost_app()
                title = frontmost_window_title()
                objects = yolo.detect(frame) if yolo else []
                ctx = {"app": app, "title": title, "objects": objects}
                if unchanged and not args.always_classify and last_readout is not None:
                    # Screen barely changed — carry forward the last real verdict
                    # (reading a static doc is still "working"), just relabel it.
                    readout = {
                        "category": last_readout.get("category", "unknown"),
                        "focused": last_readout.get("focused", False),
                        "activity": "idle/unchanged",
                        "summary": last_readout.get("summary", ""),
                        "skipped": True,
                    }
                else:
                    readout = backend.classify(frame, ctx)
                    last_readout = readout
                readout["frontmost_app"] = app
                readout["window_title"] = title
                readout["yolo"] = objects
        finally:
            if args.keep_frames:
                print(f"[debug] kept frame {frame}", file=sys.stderr)
            else:
                frame.unlink(missing_ok=True)

        record = {"ts": now.isoformat(), "backend": args.backend, **readout}
        line = focusmon_line(readout, now)

        if args.dry_run:
            print(json.dumps(record, ensure_ascii=False))
            print("  -> " + line)
        else:
            append_jsonl(activity_dir, now, record)
            if time.time() - last_log_write >= args.log_interval:
                append_log(log_dir, now, line)
                last_log_write = time.time()
            print(f"[{now.strftime('%H:%M:%S')}] {record.get('activity','?')} "
                  f"({record.get('category','?')}) app={record.get('frontmost_app','')}",
                  file=sys.stderr)

        if args.once:
            break
        time.sleep(max(0, args.interval - (time.time() - cycle_start)))

    print("[run] stopped.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Focus Coach Native v0 activity service")
    p.add_argument("--backend", default="heuristic",
                   choices=["heuristic", "ollama", "apple", "onnx"],
                   help="Classifier backend (default heuristic: no model, runs today).")
    p.add_argument("--interval", type=float, default=15.0,
                   help="Seconds between captures (default 15).")
    p.add_argument("--log-interval", type=float, default=300.0,
                   help="Min seconds between focusmon log lines (default 300).")
    p.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="Ollama vision model when --backend ollama.")
    p.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    p.add_argument("--activity-dir", default=str(DEFAULT_ACTIVITY_DIR))
    p.add_argument("--yolo", dest="yolo", action="store_true", default=False,
                   help="Run the YOLO object pass (needs ultralytics).")
    p.add_argument("--no-yolo", dest="yolo", action="store_false",
                   help="Skip YOLO (default).")
    p.add_argument("--always-classify", action="store_true",
                   help="Classify even when the screen is unchanged.")
    p.add_argument("--once", action="store_true", help="One cycle then exit.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print readout + line to stdout; write nothing.")
    p.add_argument("--keep-frames", action="store_true",
                   help="Debug: don't delete captures.")
    return p


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
