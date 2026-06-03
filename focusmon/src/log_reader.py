"""Shared module for reading the FocusMon daily log and computing day stats.

Anything that needs to know "how is Amit doing today?" goes through here:
    - sendEmailReport.py (the compliance report)
    - attn_4Hourly.py (the twice-daily partner emails)

Log line format (written by the hourly cron job that runs check_fomi.py):

    <YYYY-MM-DD HH:MM:SS TZ> | running=<yes|no|unknown> | focused=<yes|no> | note=<one-line text>

    The `focused` field is optional (absent in older log lines). When
    `running=yes` and `focused=no`, the hour is treated as distracted
    (counted as not_running for compliance purposes).

This module deliberately knows nothing about email. It just reads files and
returns structured data.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "PROJ/ASHANBH/personal_agents/focusmon/logs")))
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))

WORK_START_HOUR = int(os.getenv("WORK_START_HOUR", "0"))   # inclusive
WORK_END_HOUR = int(os.getenv("WORK_END_HOUR", "23"))     # inclusive (11pm)
# Hour to exempt from the "missing = loss of focus" penalty (laptop off at lunch).
LUNCH_HOUR = int(os.getenv("LUNCH_HOUR", "12"))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    ts_local: datetime  # in LOCAL_TZ
    running: str        # "yes" | "no" | "unknown"
    focused: str        # "yes" | "no" — absent in old logs defaults to "yes"
    note: str
    raw: str


@dataclass
class HourSlot:
    hour: int               # 24h local hour
    label: str              # e.g. "10am"
    status: str             # "running" | "not_running" | "unknown" | "missing" | "lunch" | "upcoming"
    note: str
    ts_local: datetime | None
    checks_yes: int = 0
    checks_no: int = 0
    checks_unknown: int = 0
    check_sequence: list[str] = field(default_factory=list)  # ordered "yes"/"no"/"unknown"

    @property
    def checks_total(self) -> int:
        return self.checks_yes + self.checks_no + self.checks_unknown


@dataclass
class DayStats:
    target: date_cls
    slots: list[HourSlot]
    running_n: int
    not_running_n: int
    unknown_n: int
    missing_n: int        # no-data hours outside lunch — penalised as loss of focus
    lunch_n: int          # no-data lunch hour — excluded from compliance
    upcoming_n: int
    total_completed: int  # running + not_running + unknown + missing_n (missing penalises)
    compliance_pct: int   # round(100 * running_n / total_completed), 0 if no checks

    @property
    def offending_hours(self) -> list[HourSlot]:
        """Hours where Fomi was confirmed not running during work hours."""
        return [s for s in self.slots if s.status == "not_running"]

    @property
    def focused_hours(self) -> list[HourSlot]:
        return [s for s in self.slots if s.status == "running"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<tz>\S+)\s*\|\s*"
    r"running=(?P<running>yes|no|unknown)"
    r"(?:\s*\|\s*focused=(?P<focused>yes|no))?"
    r"\s*\|\s*note=(?P<note>.*)$",
    re.IGNORECASE,
)

_TZ_OFFSETS = {
    "UTC": "+00:00",
    "GMT": "+00:00",
    "PST": "-08:00",
    "PDT": "-07:00",
    "MST": "-07:00",
    "MDT": "-06:00",
    "CST": "-06:00",
    "CDT": "-05:00",
    "EST": "-05:00",
    "EDT": "-04:00",
}


def _parse_timestamp(ts: str, tz_label: str) -> datetime | None:
    try:
        naive = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    tz_upper = tz_label.upper()
    if tz_upper in _TZ_OFFSETS:
        offset_str = _TZ_OFFSETS[tz_upper]
        sign = 1 if offset_str.startswith("+") else -1
        hh, mm = offset_str[1:].split(":")
        tz = timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
        return naive.replace(tzinfo=tz)
    try:
        return naive.replace(tzinfo=ZoneInfo(tz_label))
    except Exception:
        return None


def parse_log_file(path: Path) -> list[LogEntry]:
    if not path.exists():
        return []
    entries: list[LogEntry] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        m = _LINE_RE.match(raw.strip())
        if not m:
            continue
        parsed_ts = _parse_timestamp(m.group("ts"), m.group("tz"))
        if parsed_ts is None:
            continue
        entries.append(
            LogEntry(
                ts_local=parsed_ts.astimezone(LOCAL_TZ),
                running=m.group("running").lower(),
                focused=m.group("focused").lower() if m.group("focused") else "yes",
                note=m.group("note").strip(),
                raw=raw,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def hour_label(h: int) -> str:
    if h == 0:
        return "12am"
    if h == 12:
        return "12pm"
    if h < 12:
        return f"{h}am"
    return f"{h - 12}pm"


def _effective(e: LogEntry) -> str:
    """Effective focus state: running=yes|focused=no counts as 'no' (distracted)."""
    if e.running == "yes" and e.focused == "no":
        return "no"
    return e.running


def _classify(entries: list[LogEntry], target: date_cls) -> list[HourSlot]:
    by_hour: dict[int, LogEntry] = {}
    hour_counts: dict[int, dict[str, int]] = {}
    hour_seqs: dict[int, list[tuple[datetime, str]]] = {}
    for e in entries:
        if e.ts_local.date() != target:
            continue
        h = e.ts_local.hour
        prior = by_hour.get(h)
        if prior is None or e.ts_local > prior.ts_local:
            by_hour[h] = e
        eff = _effective(e)
        c = hour_counts.setdefault(h, {"yes": 0, "no": 0, "unknown": 0})
        c[eff] = c.get(eff, 0) + 1
        hour_seqs.setdefault(h, []).append((e.ts_local, eff))

    slots: list[HourSlot] = []
    now_local = datetime.now(LOCAL_TZ)
    for h in range(WORK_START_HOUR, WORK_END_HOUR + 1):
        entry = by_hour.get(h)
        c = hour_counts.get(h, {"yes": 0, "no": 0, "unknown": 0})
        seq = [r for _, r in sorted(hour_seqs.get(h, []))]
        if entry:
            eff = _effective(entry)
            status = {"yes": "running", "no": "not_running", "unknown": "unknown"}[eff]
            note = entry.note
            if entry.running == "yes" and entry.focused == "no":
                note = f"distracted ({entry.note})" if entry.note else "distracted"
            slots.append(HourSlot(
                h, hour_label(h), status, note, entry.ts_local,
                checks_yes=c["yes"], checks_no=c["no"], checks_unknown=c["unknown"],
                check_sequence=seq,
            ))
        else:
            hour_dt = datetime(target.year, target.month, target.day, h, tzinfo=LOCAL_TZ)
            if hour_dt > now_local and target == now_local.date():
                slots.append(HourSlot(h, hour_label(h), "upcoming", "not yet checked", None))
            elif h == LUNCH_HOUR:
                slots.append(HourSlot(h, hour_label(h), "lunch", "lunch break (excluded)", None))
            else:
                slots.append(HourSlot(h, hour_label(h), "missing", "no check recorded", None))
    return slots


def stats_for_date(
    target: date_cls | None = None,
    log_dir: Path | None = None,
) -> DayStats:
    """Compute per-hour status + compliance for a given local date."""
    target = target or datetime.now(LOCAL_TZ).date()
    log_dir = log_dir or LOG_DIR
    log_path = log_dir / f"{target.isoformat()}.log"
    entries = parse_log_file(log_path)
    slots = _classify(entries, target)

    running_n = sum(1 for s in slots if s.status == "running")
    not_running_n = sum(1 for s in slots if s.status == "not_running")
    unknown_n = sum(1 for s in slots if s.status == "unknown")
    missing_n = sum(1 for s in slots if s.status == "missing")   # penalised
    lunch_n = sum(1 for s in slots if s.status == "lunch")       # excluded
    upcoming_n = sum(1 for s in slots if s.status == "upcoming")
    total_completed = running_n + not_running_n + unknown_n + missing_n
    compliance_pct = round(100 * running_n / total_completed) if total_completed else 0

    return DayStats(
        target=target,
        slots=slots,
        running_n=running_n,
        not_running_n=not_running_n,
        unknown_n=unknown_n,
        missing_n=missing_n,
        lunch_n=lunch_n,
        upcoming_n=upcoming_n,
        total_completed=total_completed,
        compliance_pct=compliance_pct,
    )
