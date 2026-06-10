#!/usr/bin/env python3
"""
digest_builder.py — build (and optionally send) the daily accountability digest.

INTERIM Python implementation (DESIGN.md §3: productized path is the
notification web-services gateway; this script is its reference spec).

Sanitization contract (§3.5): the digest is rendered from daily_summary()
AGGREGATES through a fixed template. No free-form LLM text, no app names,
no domains, no titles. assert_sanitized() enforces this before any send.

Review mode (§6 Q4): while DIGEST_REVIEW_MODE=1 (default), the digest goes
ONLY to REVIEW_RECIPIENT — partners never see anything until you flip it.

Every outbound copy is archived verbatim to data/egress/ (§2.5).

Usage:
    python3 digest_builder.py [--date YYYY-MM-DD] [--send] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date as date_cls, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import fomi4me_db  # noqa: E402

DEFAULT_TZ = fomi4me_db.DEFAULT_TZ


def load_env(path: Path) -> dict:
    env: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def config() -> dict:
    env = {**load_env(REPO / ".env"), **os.environ}
    return {
        "partners": [e.strip() for e in env.get("PARTNER_EMAILS", "").split(",") if e.strip()],
        "review_mode": env.get("DIGEST_REVIEW_MODE", "1") != "0",
        "review_recipient": env.get("REVIEW_RECIPIENT", ""),
        "argus_dir": Path(os.path.expanduser(env.get(
            "ARGUS_DIR", "~/PROJ/ASHANBH/personal_agents/argus"))),
        "smtp_env": Path(os.path.expanduser(env.get(
            "SMTP_ENV", "~/PROJ/ASHANBH/personal_agents/focusmon/.env"))),
    }


def _hm(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


def build(summary: dict) -> tuple[str, str, str]:
    """Fixed-schema render of aggregates -> (subject, plain, html)."""
    d = summary
    subject = f"Focus digest {d['date']}: {_hm(d['focused_minutes'])} focused"
    classes = ", ".join(d["top_nonwork_classes"]) or "—"
    lines = [
        f"Focus digest for {d['date']}",
        "",
        f"Focused:        {_hm(d['focused_minutes'])}"
        f" (best streak {_hm(d['best_session_minutes'])})",
        f"Non-work:       {_hm(d['nonwork_minutes'])}",
        f"Drift events:   {d['drift_events']}",
        f"Sessions:       {d['sessions_total']}"
        + (f" ({d['first_session_start_local']}–{d['last_session_end_local']})"
           if d["first_session_start_local"] else ""),
        f"Top distraction classes: {classes}",
        "",
        "Automated, category-level digest from FomiForMe. No sites, apps, or",
        "content are ever included. Sent with the subject's consent.",
    ]
    plain = "\n".join(lines)

    rows = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;color:#888;">{k}</td>'
        f'<td style="padding:2px 0;"><b>{v}</b></td></tr>'
        for k, v in [
            ("Focused", f"{_hm(d['focused_minutes'])} (best streak {_hm(d['best_session_minutes'])})"),
            ("Non-work", _hm(d["nonwork_minutes"])),
            ("Drift events", d["drift_events"]),
            ("Sessions", d["sessions_total"]),
            ("Top distraction classes", classes),
        ]
    )
    html = (
        f'<div style="font-family:sans-serif;font-size:14px;color:#333;">'
        f"<h3 style=\"margin:0 0 10px;\">Focus digest — {d['date']}</h3>"
        f"<table style=\"border-collapse:collapse;\">{rows}</table>"
        f'<p style="color:#999;font-size:11px;margin-top:14px;">Automated, '
        f"category-level digest from FomiForMe. No sites, apps, or content are "
        f"ever included. Sent with the subject's consent.</p></div>"
    )
    return subject, plain, html


# Patterns that must never appear in partner-facing text.
_FORBIDDEN = [
    re.compile(r"https?://", re.I),
    re.compile(r"\b[\w.-]+\.(com|net|org|tv|io|co|ai|gov|edu)\b", re.I),
    re.compile(r"\bprivate-(work|nonwork)\b", re.I),
]


def assert_sanitized(*texts: str) -> None:
    for text in texts:
        for pat in _FORBIDDEN:
            m = pat.search(text)
            if m:
                raise ValueError(f"Sanitizer violation: {m.group(0)!r} in digest")


def send(subject: str, plain: str, html: str, cfg: dict) -> list[str]:
    sys.path.insert(0, str(cfg["argus_dir"]))
    from notify_via_email import send_email  # reuses argus SMTP setup

    for k, v in load_env(cfg["smtp_env"]).items():
        os.environ.setdefault(k, v)

    if cfg["review_mode"]:
        recipients = [cfg["review_recipient"]] if cfg["review_recipient"] else []
        if not recipients:
            raise RuntimeError("Review mode on but REVIEW_RECIPIENT not set")
    else:
        recipients = cfg["partners"]
        if not recipients:
            raise RuntimeError("No PARTNER_EMAILS configured")

    send_email(subject, plain, to=",".join(recipients), html=html)
    return recipients


def archive(date_str: str, subject: str, plain: str, html: str, recipients: list[str]) -> Path:
    egress = REPO / "data" / "egress"
    egress.mkdir(parents=True, exist_ok=True)
    path = egress / f"{date_str}-digest.txt"
    stamp = datetime.now().isoformat(timespec="seconds")
    path.write_text(
        f"sent_at: {stamp}\nrecipients: {', '.join(recipients) or '(not sent)'}\n"
        f"subject: {subject}\n\n{plain}\n\n--- html ---\n{html}\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build/send the daily focus digest.")
    p.add_argument("--date", help="Local YYYY-MM-DD (default today).")
    p.add_argument("--tz", default=DEFAULT_TZ)
    p.add_argument("--send", action="store_true", help="Actually send email.")
    args = p.parse_args(argv)

    tz = ZoneInfo(args.tz)
    target = date_cls.fromisoformat(args.date) if args.date else datetime.now(tz).date()
    cfg = config()

    summary = fomi4me_db.daily_summary(target, args.tz)
    subject, plain, html = build(summary)
    assert_sanitized(subject, plain)  # html contains no identifiers either; plain is the canary

    recipients: list[str] = []
    if args.send:
        recipients = send(subject, plain, html, cfg)
        mode = "REVIEW (self only)" if cfg["review_mode"] else "partners"
        print(f"Sent to {recipients} [{mode}]")
    else:
        print(plain)

    path = archive(str(target), subject, plain, html, recipients)
    print(f"Egress copy: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
