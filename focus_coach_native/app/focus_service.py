"""Focus service entry point (stub).

The real loop (capture -> backend -> write log line, on an interval) lands in M1.
For now `main()` resolves config and prints a single well-formed status line so
`python -m app.focus_service` is runnable from a clean checkout.
"""

from __future__ import annotations

import sys

from app.config import Config


def main(argv: list[str] | None = None) -> int:
    """Resolve config and emit one status line. Returns a process exit code."""
    cfg = Config.from_env()
    # Skeleton output; replaced by the real log-writer contract in M0 step 2.
    print(
        f"focus_coach_native: backend={cfg.backend} "
        f"interval={cfg.interval_sec:g}s log={cfg.log_path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
