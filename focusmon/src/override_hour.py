"""override_hour.py — Rewrite existing log lines for a given hour in-place.

Usage (positional args, designed for SwiftBar bash= invocation):
    override_hour.py <YYYY-MM-DD> <hour-int> <yes|no|clear>

    yes   — rewrite every line in that hour to running=yes focused=yes
    no    — rewrite every line in that hour to running=no  focused=no
    clear — restore original running/focused values from sidecar

Existing lines are mutated in-place (running= and focused= only).
Original values are stored in a sidecar YYYY-MM-DD.overrides.json so that
log_reader.py always sees standard-format lines.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date as date_cls
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "PROJ/ASHANBH/personal_agents/focusmon/logs")))
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2}")
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+)\s*\|\s*"
    r"running=(?P<running>yes|no|unknown)"
    r"(?:\s*\|\s*focused=(?P<focused>yes|no))?"
    r"\s*\|\s*note=(?P<note>.*)$",
    re.IGNORECASE,
)


def _line_hour(line: str, date: date_cls) -> int | None:
    m = _TS_RE.match(line.strip())
    if not m or m.group(1) != date.isoformat():
        return None
    return int(m.group(2))


def _sidecar_path(date: date_cls) -> Path:
    return LOG_DIR / f"{date.isoformat()}.overrides.json"


def _load_sidecar(date: date_cls) -> dict:
    p = _sidecar_path(date)
    return json.loads(p.read_text()) if p.exists() else {}


def _save_sidecar(date: date_cls, data: dict) -> None:
    p = _sidecar_path(date)
    if data:
        p.write_text(json.dumps(data, indent=2))
    elif p.exists():
        p.unlink()


def set_override(date: date_cls, hour: int, status: str) -> None:
    log_path = LOG_DIR / f"{date.isoformat()}.log"
    if not log_path.exists():
        print(f"No log file for {date} — nothing to override.", file=sys.stderr)
        return

    lines = log_path.read_text(encoding="utf-8").splitlines()
    sidecar = _load_sidecar(date)
    originals = {}  # line_index -> {"running": ..., "focused": ...}

    patched, count = [], 0
    for i, l in enumerate(lines):
        if _line_hour(l, date) == hour:
            m = _LINE_RE.match(l.strip())
            if m:
                # Only save original if not already overridden
                key = str(i)
                if key not in sidecar.get(str(hour), {}):
                    originals[key] = {
                        "running": m.group("running"),
                        "focused": m.group("focused") or "yes",
                    }
                focused = "yes" if status == "yes" else "no"
                patched.append(
                    f"{m.group('ts')} | running={status} | focused={focused} | note={m.group('note').strip()}"
                )
                count += 1
                continue
        patched.append(l)

    # Merge originals into sidecar (don't overwrite existing originals for this hour)
    hour_key = str(hour)
    if originals:
        existing = sidecar.setdefault(hour_key, {})
        for k, v in originals.items():
            existing.setdefault(k, v)

    log_path.write_text("\n".join(patched) + "\n", encoding="utf-8")
    _save_sidecar(date, sidecar)
    print(f"Override set: {date} hour {hour:02d}:00 → running={status} ({count} lines patched)")


def clear_override(date: date_cls, hour: int) -> None:
    log_path = LOG_DIR / f"{date.isoformat()}.log"
    if not log_path.exists():
        print("No log file found — nothing to clear.")
        return

    sidecar = _load_sidecar(date)
    hour_key = str(hour)
    originals = sidecar.get(hour_key, {})
    if not originals:
        print(f"No override found for {date} hour {hour:02d}:00.")
        return

    lines = log_path.read_text(encoding="utf-8").splitlines()
    restored, count = [], 0
    for i, l in enumerate(lines):
        key = str(i)
        if _line_hour(l, date) == hour and key in originals:
            m = _LINE_RE.match(l.strip())
            if m:
                orig = originals[key]
                restored.append(
                    f"{m.group('ts')} | running={orig['running']} | focused={orig['focused']} | note={m.group('note').strip()}"
                )
                count += 1
                continue
        restored.append(l)

    log_path.write_text("\n".join(restored) + "\n", encoding="utf-8")
    del sidecar[hour_key]
    _save_sidecar(date, sidecar)
    print(f"Override cleared: {date} hour {hour:02d}:00 ({count} lines restored)")


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: override_hour.py <YYYY-MM-DD> <hour> <yes|no|clear>",
            file=sys.stderr,
        )
        return 1

    _, date_str, hour_str, action = sys.argv
    try:
        date = date_cls.fromisoformat(date_str)
        hour = int(hour_str)
    except ValueError as exc:
        print(f"Bad argument: {exc}", file=sys.stderr)
        return 1

    if action == "clear":
        clear_override(date, hour)
    elif action in ("yes", "no"):
        set_override(date, hour, action)
    else:
        print(f"Unknown action '{action}'. Use yes, no, or clear.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
import re
import sys
from datetime import date as date_cls
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "PROJ/ASHANBH/personal_agents/focusmon/logs")))
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))

OVERRIDE_TAG = "overridden"

# Matches a well-formed log line, capturing each field group.
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2}")
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+)\s*\|\s*"
    r"running=(?P<running>yes|no|unknown)"
    r"(?:\s*\|\s*focused=(?P<focused>yes|no))?"
    r"(?:\s*\|\s*orig=(?P<orig>[^|]+))?"
    r"\s*\|\s*note=(?P<note>.*)$",
    re.IGNORECASE,
)


def _line_hour(line: str, date: date_cls) -> int | None:
    """Return the hour (0-23) if this log line belongs to date, else None."""
    m = _TS_RE.match(line.strip())
    if not m:
        return None
    if m.group(1) != date.isoformat():
        return None
    return int(m.group(2))


def _patch_line(line: str, status: str) -> str:
    """Rewrite running= and focused= in a log line, preserving orig= for clear."""
    m = _LINE_RE.match(line.strip())
    if not m:
        return line  # unrecognised format — leave untouched
    orig_running = m.group("running")
    orig_focused = m.group("focused") or "yes"
    orig_field = m.group("orig") or f"{orig_running},{orig_focused}"
    note = m.group("note").strip()
    focused = "yes" if status == "yes" else "no"
    return (
        f"{m.group('ts')} | running={status} | focused={focused}"
        f" | orig={orig_field} | note={note}"
    )


def _restore_line(line: str) -> str:
    """Restore a previously patched line to its original running/focused values."""
    m = _LINE_RE.match(line.strip())
    if not m or not m.group("orig"):
        return line
    orig_parts = m.group("orig").split(",")
    orig_running = orig_parts[0].strip()
    orig_focused = orig_parts[1].strip() if len(orig_parts) > 1 else "yes"
    note = m.group("note").strip()
    return f"{m.group('ts')} | running={orig_running} | focused={orig_focused} | note={note}"


def set_override(date: date_cls, hour: int, status: str) -> None:
    log_path = LOG_DIR / f"{date.isoformat()}.log"
    if not log_path.exists():
        print(f"No log file for {date} — nothing to override.", file=sys.stderr)
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    patched, count = [], 0
    for l in lines:
        if _line_hour(l, date) == hour:
            patched.append(_patch_line(l, status))
            count += 1
        else:
            patched.append(l)
    log_path.write_text("\n".join(patched) + "\n", encoding="utf-8")
    print(f"Override set: {date} hour {hour:02d}:00 → running={status} ({count} lines patched)")


def clear_override(date: date_cls, hour: int) -> None:
    log_path = LOG_DIR / f"{date.isoformat()}.log"
    if not log_path.exists():
        print("No log file found — nothing to clear.")
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    restored, count = [], 0
    for l in lines:
        m = _LINE_RE.match(l.strip()) if _line_hour(l, date) == hour else None
        if m and m.group("orig"):
            restored.append(_restore_line(l))
            count += 1
        else:
            restored.append(l)
    if count == 0:
        print(f"No override found for {date} hour {hour:02d}:00.")
    else:
        log_path.write_text("\n".join(restored) + "\n", encoding="utf-8")
        print(f"Override cleared: {date} hour {hour:02d}:00 ({count} lines restored)")


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: override_hour.py <YYYY-MM-DD> <hour> <yes|no|clear>",
            file=sys.stderr,
        )
        return 1

    _, date_str, hour_str, action = sys.argv
    try:
        date = date_cls.fromisoformat(date_str)
        hour = int(hour_str)
    except ValueError as exc:
        print(f"Bad argument: {exc}", file=sys.stderr)
        return 1

    if action == "clear":
        clear_override(date, hour)
    elif action in ("yes", "no"):
        set_override(date, hour, action)
    else:
        print(f"Unknown action '{action}'. Use yes, no, or clear.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
