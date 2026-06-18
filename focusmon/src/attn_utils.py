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


def _bar_color(pct: int) -> str:
    """Map a focus-% to the SwiftBar card colour palette."""
    if pct >= 75:
        return "#4a7c59"
    elif pct >= 25:
        return "#c8a96e"
    else:
        return "#b85c5c"


_BAR_MAX_PX = 180
_DOTS = "· " * 12


def swiftbar_card_html(
    header: str,
    headline: str,
    headline_color: str,
    slots: list,
    extra_html: str = "",
    footer_html: str = "",
    card_width: int = 360,
) -> str:
    """Render the SwiftBar-style card HTML used by all outbound FocusMon emails.

    Parameters
    ----------
    header:          Small grey subtitle line ("FocusMon daily · Tue Jun 16").
    headline:        Bold coloured summary line.
    headline_color:  CSS colour for the headline text.
    slots:           List of HourSlot objects from log_reader.
    extra_html:      Optional HTML injected between the headline and the chart.
    footer_html:     Optional HTML appended at the bottom of the card.
    card_width:      Max-width of the card in pixels.
    """
    hour_rows = []
    for slot in slots:
        seq = getattr(slot, "check_sequence", [])
        if slot.status == "upcoming":
            hour_rows.append(
                f"<tr>"
                f"<td style='color:#cccccc;font-size:13px;width:44px;"
                f"padding:3px 10px 3px 0;text-align:right;white-space:nowrap;'>{slot.label}</td>"
                f"<td style='padding:3px 6px;width:{_BAR_MAX_PX}px;vertical-align:middle;'>"
                f"<span style='color:#dddddd;font-size:10px;letter-spacing:2px;'>{_DOTS}</span></td>"
                f"<td style='width:38px;'></td>"
                f"</tr>"
            )
            continue

        if slot.status in ("missing", "lunch"):
            label_color = "#aaaaaa"
            bar_html = (
                f"<span style='color:#dddddd;font-size:10px;letter-spacing:2px;'>{_DOTS}</span>"
            )
            pct_html = "<span style='color:#aaaaaa;font-size:12px;'>—</span>"
        else:
            if seq:
                pct = round(100 * slot.checks_yes / slot.checks_total) if slot.checks_total else 0
            else:
                pct = 100 if slot.status == "running" else 0
            label_color = _bar_color(pct)
            filled_px = max(round(_BAR_MAX_PX * pct / 100), 0)
            empty_px = _BAR_MAX_PX - filled_px
            bar_cells = ""
            if filled_px:
                bar_cells += (
                    f"<td style='background:{label_color};width:{filled_px}px;"
                    f"height:16px;'></td>"
                )
            if empty_px:
                bar_cells += (
                    f"<td style='background:#e8e8e8;width:{empty_px}px;height:16px;'></td>"
                )
            bar_html = (
                f"<table cellspacing='0' cellpadding='0' "
                f"style='border-collapse:collapse;width:{_BAR_MAX_PX}px;'>"
                f"<tr>{bar_cells}</tr></table>"
            )
            pct_html = (
                f"<span style='color:{label_color};font-weight:700;"
                f"font-size:13px;'>{pct}%</span>"
            )

        hour_rows.append(
            f"<tr>"
            f"<td style='color:{label_color};font-size:13px;font-weight:600;width:44px;"
            f"padding:3px 10px 3px 0;text-align:right;white-space:nowrap;'>{slot.label}</td>"
            f"<td style='padding:3px 6px;width:{_BAR_MAX_PX}px;vertical-align:middle;'>"
            f"{bar_html}</td>"
            f"<td style='padding:3px 0 3px 4px;white-space:nowrap;'>{pct_html}</td>"
            f"</tr>"
        )

    chart = (
        "<table cellspacing='0' cellpadding='0' style='border-collapse:collapse;'>"
        + "".join(hour_rows)
        + "</table>"
    )

    extra_section = f"\n  {extra_html}\n" if extra_html else ""
    footer_section = (
        f"\n  <hr style='border:none;border-top:1px solid #eeeeee;margin:10px 0;'>\n"
        f"  {footer_html}\n"
        if footer_html else ""
    )

    return f"""\
<html><body style="margin:0;padding:24px;background:#f0f0f0;font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Helvetica,sans-serif;">
<div style="max-width:{card_width}px;background:#ffffff;border-radius:12px;padding:16px 20px;box-shadow:0 2px 10px rgba(0,0,0,0.10);">

  <!-- header -->
  <div style="color:#999999;font-size:12px;margin-bottom:6px;">{header}</div>

  <!-- headline -->
  <div style="color:{headline_color};font-size:17px;font-weight:700;margin-bottom:12px;">{headline}</div>

  <hr style="border:none;border-top:1px solid #eeeeee;margin:0 0 10px 0;">{extra_section}
  <!-- chart -->
  {chart}{footer_section}
</div>
</body></html>
"""


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
