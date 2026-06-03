"""Shared utilities for attn_4Hourly.py and attn_daily.py.

Anything used by more than one attention/reporting script lives here:
  - Common env-var config (SUBJECT_NAME, ACCOUNTABILITY_RECIPIENTS)
  - HTML block-bar renderer
  - Full hour-by-hour HTML table
  - Plain-text bar helper
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

SUBJECT_NAME: str = os.getenv("SUBJECT_NAME", "Amit")

ACCOUNTABILITY_RECIPIENTS: str = os.getenv(
    "ACCOUNTABILITY_RECIPIENTS",
    os.getenv("SMTP_TO", ""),
)

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

_SLOT_COLOR = {
    "running":     "#1b8a3a",
    "not_running": "#c0392b",
    "unknown":     "#7f8c8d",
    "missing":     "#c0392b",   # penalised — same red as not_running
    "lunch":       "#aaaaaa",
}

_SLOT_LABEL = {
    "running":     "focused",
    "not_running": "drifted",
    "unknown":     "unknown",
    "missing":     "no data (counts as drifted)",
    "lunch":       "lunch break",
}


def block_bar_html(seq: list[str]) -> str:
    """Coloured Unicode block bar for one hour's ordered check sequence.

    Each element of *seq* is "yes", "no", or "unknown".
    Returns a string of <span> elements suitable for embedding in HTML.
    """
    return "".join(
        "<span style='color:#1b8a3a;'>&#9608;</span>" if r == "yes"
        else "<span style='color:#c0392b;'>&#9608;</span>" if r == "no"
        else "<span style='color:#7f8c8d;'>&#9617;</span>"
        for r in seq
    )


def all_hours_table_html(slots: list) -> str:
    """HTML table covering all completed work-window hours (skips upcoming).

    Multi-check hours (5-min cron) show a coloured block bar + %.
    Single-check hours show a plain "focused" / "drifted" label.
    """
    rows = []
    for s in slots:
        if s.status == "upcoming":
            continue
        seq = getattr(s, "check_sequence", [])
        if len(seq) > 1:
            total = s.checks_total
            pct_val = round(100 * s.checks_yes / total) if total else 0
            color = "#1b8a3a" if pct_val >= 50 else ("#e67e22" if pct_val > 0 else "#c0392b")
            cell = (
                f"<span style='font-family:monospace;letter-spacing:1px;font-size:14px;'>"
                f"{block_bar_html(seq)}</span>"
                f"&nbsp;<span style='color:{color};font-weight:600;'>{pct_val}%</span>"
            )
        else:
            color = _SLOT_COLOR.get(s.status, "#888")
            cell = _SLOT_LABEL.get(s.status, s.status)
        rows.append(
            f"<tr>"
            f"<td style='padding:4px 18px 4px 0;color:#555;font-size:13px;'>{s.label}</td>"
            f"<td style='padding:4px 0;color:{color};font-weight:600;font-size:13px;'>{cell}</td>"
            f"</tr>"
        )
    if not rows:
        return ""
    return (
        "<table cellspacing='0' cellpadding='0' "
        "style='border-collapse:collapse;margin-top:6px;'>"
        + "".join(rows)
        + "</table>"
    )


_PLAIN_MARKERS = {
    "running":     "[ok ]",
    "not_running": "[off]",
    "unknown":     "[?  ]",
    "missing":     "[off] (no data)",
    "lunch":       "[--]  lunch",
}


def plain_bar(s) -> str:
    """Plain-text bar + % for one HourSlot, used in the text/plain email part.

    Multi-check:  [####........] 33%
    Single-check: [ok ] / [off] / etc.
    """
    seq = getattr(s, "check_sequence", [])
    if len(seq) > 1:
        bar = "".join("#" if r == "yes" else "." for r in seq)
        pct_val = round(100 * s.checks_yes / s.checks_total) if s.checks_total else 0
        return f"[{bar}] {pct_val:>3}%"
    return _PLAIN_MARKERS.get(s.status, "     ")


# ---------------------------------------------------------------------------
# Message log
# ---------------------------------------------------------------------------

MESSAGES_DIR = Path(__file__).parent.parent / "messages"


def write_message_log(filename: str, subject: str, plain_body: str) -> None:
    """Write a Markdown log of an outgoing email to ../messages/<filename>.

    The file is created (or overwritten) regardless of whether the email is
    sent or --dry-run; it serves as a persistent record of every generated
    message.
    """
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = MESSAGES_DIR / filename
    path.write_text(f"# {subject}\n\n{plain_body}", encoding="utf-8")
    print(f"Logged: {path}")
