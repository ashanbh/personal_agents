"""Runtime configuration for the focus service.

All values are overridable via environment variables so the native shell (or a
dev) can tune behaviour without code changes. Kept dependency-free (stdlib only)
so it imports cleanly on any platform.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Environment variable names (single source of truth).
ENV_INTERVAL = "FOCUS_INTERVAL_SEC"
ENV_LOG_PATH = "FOCUS_LOG_PATH"
ENV_BACKEND = "FOCUS_BACKEND"

# Defaults.
DEFAULT_INTERVAL_SEC = 30.0
DEFAULT_BACKEND = "heuristic"  # tier-3 fallback; always available.


def _default_log_path() -> Path:
    """Default activity log location (under the user's home, not the repo)."""
    return Path.home() / ".focus_coach" / "activity.log"


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration."""

    interval_sec: float = DEFAULT_INTERVAL_SEC
    log_path: Path = None  # type: ignore[assignment]  # set in __post_init__ analogue
    backend: str = DEFAULT_BACKEND

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> "Config":
        """Build a Config from environment variables (process env by default)."""
        env = os.environ if env is None else env

        raw_interval = env.get(ENV_INTERVAL)
        try:
            interval = float(raw_interval) if raw_interval else DEFAULT_INTERVAL_SEC
        except ValueError:
            interval = DEFAULT_INTERVAL_SEC
        if interval <= 0:
            interval = DEFAULT_INTERVAL_SEC

        log_path = Path(env.get(ENV_LOG_PATH) or _default_log_path())
        backend = env.get(ENV_BACKEND) or DEFAULT_BACKEND

        return Config(interval_sec=interval, log_path=log_path, backend=backend)
