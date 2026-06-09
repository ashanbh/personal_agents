"""Activity log-line writer.

Formats a :class:`~app.backends.Decision` into the project's output contract and
appends it to a log file. Kept stdlib-only so it imports cleanly everywhere.

Output contract (downstream coach depends on this exact shape)::

    running=yes|no|unknown [| focused=yes|no] | note=...

The ``focused`` field is omitted entirely when the backend has no opinion
(``Decision.focused is None``). Field order is fixed: ``running`` first,
optional ``focused`` next, ``note`` last.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.backends import Decision

_VALID_RUNNING = ("yes", "no", "unknown")
_VALID_FOCUSED = ("yes", "no")


def format_line(decision: Decision) -> str:
    """Render a :class:`Decision` as a single contract-compliant log line.

    Raises:
        ValueError: if ``running`` or ``focused`` carries an out-of-contract value.
    """
    running = decision.running
    if running not in _VALID_RUNNING:
        raise ValueError(
            f"running must be one of {_VALID_RUNNING}, got {running!r}"
        )

    parts = [f"running={running}"]

    focused = decision.focused
    if focused is not None:
        if focused not in _VALID_FOCUSED:
            raise ValueError(
                f"focused must be one of {_VALID_FOCUSED} or None, got {focused!r}"
            )
        parts.append(f"focused={focused}")

    # Keep notes single-line so the contract stays one record per line.
    note = (decision.note or "").replace("\n", " ").replace("\r", " ")
    parts.append(f"note={note}")

    return " | ".join(parts)


def write_line(decision: Decision, log_path: Path, newline: str = "\n") -> str:
    """Append the formatted line for ``decision`` to ``log_path``.

    Creates the parent directory if needed. Returns the line that was written
    (without the trailing newline) so callers can log/echo it.
    """
    line = format_line(decision)
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + newline)
    return line
