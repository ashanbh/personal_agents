"""Focus service entry point.

The real capture loop (capture -> backend -> write log line, on an interval)
lands in M1. For now `main()` resolves config and emits one well-formed log line
via the M0 log-writer contract, so `python -m app.focus_service` is runnable
from a clean checkout and proves the output shape end-to-end.
"""

from __future__ import annotations

import sys

from app.backends import Decision
from app.config import Config
from app.logwriter import format_line, write_line


def main(argv: list[str] | None = None) -> int:
    """Resolve config, write one contract line, and echo it. Returns exit code."""
    cfg = Config.from_env()
    # No real classifier yet (M1); emit an honest "unknown" status line.
    decision = Decision(running="unknown", note="service skeleton; no classifier yet")
    write_line(decision, cfg.log_path)
    print(format_line(decision))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
